"""
數據獲取模組 - 統一管理所有外部 API 呼叫
"""
import io
import re
import time
import hashlib
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple, Any, Callable

import chardet
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

from config import (
    HEADERS, REQUEST_TIMEOUT, URLS, SUPPORTED_ETFS,
    DEFAULT_RANKING_LIMIT, TECH_SECTORS
)


# =============================================================================
# 記憶體快取機制
# =============================================================================

_memory_cache: Dict[str, Tuple[float, Any]] = {}


def memory_cache(ttl_seconds: int = 300):
    """
    記憶體快取裝飾器

    Args:
        ttl_seconds: 快取存活時間 (秒)，預設 5 分鐘

    Usage:
        @memory_cache(ttl_seconds=300)
        def get_data(param):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 產生快取 key
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

            # 檢查快取
            if cache_key in _memory_cache:
                cached_time, cached_result = _memory_cache[cache_key]
                if time.time() - cached_time < ttl_seconds:
                    print(f"[Cache HIT] {func.__name__}")
                    return cached_result

            # 執行函數並快取結果
            result = func(*args, **kwargs)
            _memory_cache[cache_key] = (time.time(), result)
            print(f"[Cache MISS] {func.__name__} - cached for {ttl_seconds}s")

            return result
        return wrapper
    return decorator


def clear_memory_cache():
    """清除所有記憶體快取"""
    global _memory_cache
    _memory_cache.clear()
    print("[Cache] All memory cache cleared")


class DataFetchError(Exception):
    """數據獲取錯誤"""
    pass


def safe_request(url: str, verify: bool = True, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """
    安全的 HTTP 請求封裝
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=verify)
        resp.raise_for_status()
        return resp
    except requests.exceptions.Timeout:
        print(f"Request timeout: {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {url}, Error: {e}")
        return None


def detect_encoding(content: bytes) -> str:
    """偵測內容編碼"""
    result = chardet.detect(content)
    return result.get('encoding') or 'utf-8'


# =============================================================================
# 市場指標
# =============================================================================

def fetch_vix_us() -> Dict[str, Any]:
    """獲取美國 VIX 指數"""
    try:
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty and len(vix) >= 2:
            curr = vix["Close"].iloc[-1]
            prev = vix["Close"].iloc[-2]
            return {"val": round(curr, 2), "delta": round(curr - prev, 2)}
    except Exception as e:
        print(f"VIX fetch error: {e}")
    return {"val": "-", "delta": 0}


def fetch_twii() -> Dict[str, Any]:
    """獲取台股加權指數及均線狀態"""
    try:
        twii = yf.Ticker("^TWII").history(period="3mo")
        if not twii.empty:
            curr = twii["Close"].iloc[-1]
            ma20 = twii["Close"].tail(20).mean()
            ma60 = twii["Close"].tail(60).mean()

            status_parts = []
            status_parts.append("站上月線" if curr > ma20 else "跌破月線")
            status_parts.append("站上季線" if curr > ma60 else "跌破季線")

            return {
                "val": int(curr),
                "status": " | ".join(status_parts),
                "price": curr
            }
    except Exception as e:
        print(f"TWII fetch error: {e}")
    return {"val": "-", "status": "-", "price": 0}


def fetch_vixtwn_stockq() -> Dict[str, Optional[float]]:
    """從 StockQ 獲取 VIXTWN"""
    resp = safe_request(URLS["stockq_vix"], timeout=10)
    if not resp:
        return {"val": None}

    try:
        dfs = pd.read_html(io.StringIO(resp.text))
        for df in dfs:
            if df.shape[1] >= 2 and df.shape[0] >= 1:
                for col in range(df.shape[1]):
                    for row in range(df.shape[0]):
                        val = df.iloc[row, col]
                        try:
                            v_float = float(val)
                            # VIX 合理區間: 10 ~ 100
                            if 10 < v_float < 100:
                                return {"val": v_float}
                        except (ValueError, TypeError):
                            continue
    except Exception as e:
        print(f"VIXTWN parse error: {e}")

    return {"val": None}


def get_all_market_indicators() -> Dict[str, Any]:
    """
    並行獲取所有市場指標
    """
    indicators = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_vix_us): "VIX",
            executor.submit(fetch_twii): "TWII",
            executor.submit(fetch_vixtwn_stockq): "VIXTWN",
        }

        for future in as_completed(futures):
            key = futures[future]
            try:
                indicators[key] = future.result()
            except Exception as e:
                print(f"Error fetching {key}: {e}")
                indicators[key] = {"val": "-"}

    return indicators


# =============================================================================
# 股票數據
# =============================================================================

def fetch_taifex_rankings(limit: int = DEFAULT_RANKING_LIMIT) -> pd.DataFrame:
    """獲取期交所市值排名"""
    resp = safe_request(URLS["taifex_ranking"])
    if not resp:
        return pd.DataFrame()

    try:
        encoding = detect_encoding(resp.content)
        html_text = resp.content.decode(encoding, errors="ignore")
        soup = BeautifulSoup(html_text, "lxml")

        rows = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            rank, code, name = None, None, None
            texts = [td.get_text(strip=True) for td in tds]

            for s in texts:
                if rank is None and re.fullmatch(r"\d+", s):
                    rank = int(s)
                elif rank and not code and re.fullmatch(r"\d{4}", s):
                    code = s
                elif rank and code and not name and not re.fullmatch(r"\d+", s):
                    name = s
                    break

            if rank and code and name:
                rows.append({"排名": rank, "股票代碼": code, "股票名稱": name})

        if rows:
            return pd.DataFrame(rows).sort_values("排名").head(limit)

        # Fallback: 使用 pandas read_html
        dfs = pd.read_html(io.StringIO(html_text), flavor=["lxml", "html5lib"])
        for df in dfs:
            cols = "".join([str(c) for c in df.columns])
            if "排名" in cols and ("名稱" in cols or "代號" in cols):
                df.columns = [str(c).replace(" ", "") for c in df.columns]
                col_map = {}
                for c in df.columns:
                    if "排名" in c:
                        col_map[c] = "排名"
                    elif "代" in c:
                        col_map[c] = "股票代碼"
                    elif "名" in c:
                        col_map[c] = "股票名稱"

                df = df.rename(columns=col_map)
                df = df[pd.to_numeric(df["排名"], errors='coerce').notnull()]
                df["排名"] = df["排名"].astype(int)
                df["股票代碼"] = df["股票代碼"].astype(str).str.extract(r'(\d{4})')[0]
                return df.sort_values("排名").head(limit)

    except Exception as e:
        print(f"TAIFEX ranking parse error: {e}")

    return pd.DataFrame()


def fetch_msci_list() -> List[str]:
    """獲取 MSCI 成分股列表"""
    resp = safe_request(URLS["msci_list"], verify=False)
    if not resp:
        return []

    try:
        encoding = detect_encoding(resp.content)
        html_text = resp.content.decode(encoding, errors="ignore")

        # 優先從 JavaScript 中提取
        codes = set(re.findall(r"Link2Stk\('(\d{4})'\)", html_text))

        if not codes:
            # Fallback: 從頁面文本提取
            soup = BeautifulSoup(html_text, "lxml")
            codes = set(re.findall(r"\b(\d{4})\b", soup.get_text()))

        return sorted(list(codes))

    except Exception as e:
        print(f"MSCI list parse error: {e}")

    return []


def fetch_etf_holdings(etf_code: str) -> List[str]:
    """獲取 ETF 持股名單"""
    url = URLS["etf_holdings"].format(etf_code=etf_code)

    time.sleep(0.3)  # Rate limiting
    resp = safe_request(url, verify=False)
    if not resp:
        return []

    try:
        resp.encoding = resp.apparent_encoding or "utf-8"
        dfs = pd.read_html(io.StringIO(resp.text), flavor="lxml")

        names = []
        for df in dfs:
            cols = [str(c[-1] if isinstance(df.columns, pd.MultiIndex) else c).strip()
                   for c in df.columns]
            df.columns = cols

            target_col = next((c for c in cols if "名稱" in c), None)
            if target_col:
                names.extend(df[target_col].astype(str).str.strip().tolist())

        return list(set([n for n in names if n not in ['nan', '']]))

    except Exception as e:
        print(f"ETF holdings parse error for {etf_code}: {e}")

    return []


def fetch_all_etf_holdings() -> Dict[str, Set[str]]:
    """並行獲取所有 ETF 持股"""
    holdings = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_etf_holdings, etf): etf
            for etf in SUPPORTED_ETFS
        }

        for future in as_completed(futures):
            etf = futures[future]
            try:
                holdings[etf] = set(future.result())
            except Exception as e:
                print(f"Error fetching {etf} holdings: {e}")
                holdings[etf] = set()

    return holdings


# =============================================================================
# yfinance 批量查詢
# =============================================================================

def _get_yf_tickers(codes: List[str]) -> yf.Tickers:
    """建立 yfinance Tickers 物件"""
    tickers_str = " ".join([f"{c}.TW" for c in codes])
    return yf.Tickers(tickers_str)


@memory_cache(ttl_seconds=300)  # 5 分鐘快取
def get_stock_info_batch(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    批量獲取股票即時資訊 (價格、漲跌、成交量)
    快取 5 分鐘，Tab 1/2/4 重複查詢時直接使用快取
    """
    if not codes:
        return {}

    result = {}
    default_info = {
        "現價": "-", "漲跌": "-", "量能": "-", "成交值": "-",
        "raw_vol": 0, "raw_change": 0, "raw_turnover": 0, "raw_price": 0
    }

    try:
        tickers = _get_yf_tickers(codes)

        for code in codes:
            try:
                ticker = tickers.tickers.get(f"{code}.TW")
                if not ticker:
                    result[code] = default_info.copy()
                    continue

                hist = ticker.history(period="5d")
                if hist.empty:
                    result[code] = default_info.copy()
                    continue

                curr_price = hist["Close"].iloc[-1]
                prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else curr_price
                vol = hist["Volume"].iloc[-1]
                avg_vol = hist["Volume"].mean()
                turnover = curr_price * vol

                # 格式化成交值
                if turnover > 100_000_000:
                    turnover_str = f"{turnover / 100_000_000:.1f}億"
                else:
                    turnover_str = f"{turnover / 10_000:.0f}萬"

                change_pct = ((curr_price - prev_price) / prev_price) * 100

                # 量能狀態
                if vol > avg_vol * 2 and vol > 1000:
                    vol_status = "🔥爆量"
                elif vol < avg_vol * 0.6:
                    vol_status = "💧縮量"
                else:
                    vol_status = "➖正常"

                result[code] = {
                    "現價": f"{curr_price:.2f}",
                    "漲跌": f"{change_pct:+.2f}%",
                    "量能": f"{int(vol/1000)}張 ({vol_status})",
                    "成交值": turnover_str,
                    "raw_vol": vol,
                    "raw_change": change_pct,
                    "raw_turnover": turnover,
                    "raw_price": curr_price
                }

            except Exception as e:
                print(f"Error processing {code}: {e}")
                result[code] = default_info.copy()

    except Exception as e:
        print(f"Batch stock info error: {e}")
        for code in codes:
            result[code] = default_info.copy()

    return result


def _fetch_single_dividend_yield(code: str) -> Tuple[str, float]:
    """獲取單一股票殖利率 (供並行查詢使用)"""
    try:
        ticker = yf.Ticker(f"{code}.TW")
        info = ticker.info
        dy = info.get('trailingAnnualDividendYield')

        if dy is None:
            dy = info.get('dividendYield')
            # 修正異常值
            if dy and dy > 0.2:
                dy = 0

        return (code, (dy * 100) if dy else 0)
    except Exception:
        return (code, 0)


@memory_cache(ttl_seconds=86400)  # 24 小時快取
def get_dividend_yield_batch(codes: List[str]) -> Dict[str, float]:
    """
    批量獲取殖利率 (並行優化版)
    使用 ThreadPoolExecutor 並行查詢，效能提升 5-10 倍
    快取 24 小時，殖利率資料變動不頻繁
    """
    if not codes:
        return {}

    result = {}

    try:
        # 使用 ThreadPoolExecutor 並行查詢 (max_workers=10)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(_fetch_single_dividend_yield, code): code
                for code in codes
            }

            for future in as_completed(futures):
                try:
                    code, dy = future.result()
                    result[code] = dy
                except Exception:
                    code = futures[future]
                    result[code] = 0

    except Exception as e:
        print(f"Dividend yield batch error: {e}")
        for code in codes:
            result[code] = 0

    return result


def get_sector_batch(codes: List[str]) -> Dict[str, str]:
    """批量獲取產業分類"""
    if not codes:
        return {}

    result = {}

    try:
        tickers = _get_yf_tickers(codes)

        for code in codes:
            try:
                ticker = tickers.tickers.get(f"{code}.TW")
                if ticker:
                    result[code] = ticker.info.get('sector', 'Unknown')
                else:
                    result[code] = 'Unknown'
            except Exception:
                result[code] = 'Unknown'

    except Exception as e:
        print(f"Sector batch error: {e}")
        for code in codes:
            result[code] = 'Unknown'

    return result


def get_market_cap_batch(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """批量獲取市值和權重"""
    if not codes:
        return {}

    mcap_data = {}

    try:
        tickers = _get_yf_tickers(codes)

        for code in codes:
            try:
                ticker = tickers.tickers.get(f"{code}.TW")
                if ticker:
                    mcap = ticker.fast_info.market_cap
                    mcap_data[code] = mcap if mcap else 0
                else:
                    mcap_data[code] = 0
            except Exception:
                mcap_data[code] = 0

    except Exception as e:
        print(f"Market cap batch error: {e}")
        for code in codes:
            mcap_data[code] = 0

    total = sum(mcap_data.values())
    result = {}

    for code, mcap in mcap_data.items():
        weight = (mcap / total * 100) if total > 0 else 0
        result[code] = {
            "市值": f"{mcap / 100_000_000:.0f}億",
            "權重": f"{weight:.2f}%",
            "raw_mcap": mcap
        }

    return result
