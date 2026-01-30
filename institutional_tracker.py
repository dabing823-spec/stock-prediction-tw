"""
法人籌碼追蹤器 - 自動從期交所抓取法人期貨/選擇權部位
Institutional Position Tracker - Auto-fetch from TAIFEX
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from functools import wraps
import hashlib
import time

# 簡易快取
_inst_cache: Dict[str, Tuple[float, any]] = {}

def inst_cache(ttl_seconds: int = 600):
    """快取裝飾器，預設10分鐘"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}_{args}_{kwargs}"
            cache_key = hashlib.md5(key.encode()).hexdigest()

            if cache_key in _inst_cache:
                cached_time, cached_value = _inst_cache[cache_key]
                if time.time() - cached_time < ttl_seconds:
                    return cached_value

            result = func(*args, **kwargs)
            _inst_cache[cache_key] = (time.time(), result)
            return result
        return wrapper
    return decorator


@dataclass
class FuturesPosition:
    """期貨部位資料"""
    product: str           # 商品名稱
    foreign_long: int      # 外資多單
    foreign_short: int     # 外資空單
    foreign_net: int       # 外資淨部位
    dealer_long: int       # 自營商多單
    dealer_short: int      # 自營商空單
    dealer_net: int        # 自營商淨部位
    trust_long: int        # 投信多單
    trust_short: int       # 投信空單
    trust_net: int         # 投信淨部位
    date: str              # 日期


@dataclass
class OptionsPosition:
    """選擇權部位資料"""
    call_foreign_long: int
    call_foreign_short: int
    call_foreign_net: int
    put_foreign_long: int
    put_foreign_short: int
    put_foreign_net: int
    call_dealer_long: int
    call_dealer_short: int
    call_dealer_net: int
    put_dealer_long: int
    put_dealer_short: int
    put_dealer_net: int
    pc_ratio: float        # Put/Call Ratio
    date: str


@dataclass
class InstitutionalSignal:
    """綜合籌碼訊號"""
    signal: str            # "bullish", "bearish", "neutral"
    color: str             # "green", "red", "yellow"
    emoji: str             # 🟢🔴🟡
    strength: int          # 1-5 強度
    summary: str           # 文字摘要
    details: List[str]     # 詳細說明
    futures_position: Optional[FuturesPosition]
    options_position: Optional[OptionsPosition]
    date: str


def parse_number(s: str) -> int:
    """解析數字，處理逗號和負號"""
    if not s or s == '-':
        return 0
    try:
        return int(s.replace(',', '').replace(' ', ''))
    except:
        return 0


@inst_cache(ttl_seconds=600)
def fetch_futures_positions(date: Optional[str] = None) -> Optional[FuturesPosition]:
    """
    從期交所抓取三大法人期貨部位
    https://www.taifex.com.tw/cht/3/futContractsDate
    """
    if date is None:
        # 使用最近交易日
        date = get_latest_trading_date()

    url = "https://www.taifex.com.tw/cht/3/futContractsDateDown"

    # 格式化日期 YYYY/MM/DD
    formatted_date = date.replace('-', '/')

    params = {
        'queryDate': formatted_date,
        'commodityId': 'TXF'  # 台指期
    }

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.taifex.com.tw/cht/3/futContractsDate'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        # 嘗試解析 CSV
        lines = response.text.strip().split('\n')

        # 尋找台指期的資料
        foreign_net = 0
        dealer_net = 0
        trust_net = 0
        foreign_long = 0
        foreign_short = 0
        dealer_long = 0
        dealer_short = 0
        trust_long = 0
        trust_short = 0

        for line in lines:
            cols = line.split(',')
            if len(cols) < 10:
                continue

            # 期交所格式：契約,身份別,多方口數,多方金額,空方口數,空方金額,淨額口數,淨額金額
            identity = cols[1].strip() if len(cols) > 1 else ""

            if '外資' in identity or 'Foreign' in identity:
                foreign_long = parse_number(cols[2]) if len(cols) > 2 else 0
                foreign_short = parse_number(cols[4]) if len(cols) > 4 else 0
                foreign_net = parse_number(cols[6]) if len(cols) > 6 else 0
            elif '自營商' in identity or 'Dealer' in identity:
                dealer_long = parse_number(cols[2]) if len(cols) > 2 else 0
                dealer_short = parse_number(cols[4]) if len(cols) > 4 else 0
                dealer_net = parse_number(cols[6]) if len(cols) > 6 else 0
            elif '投信' in identity or 'Trust' in identity:
                trust_long = parse_number(cols[2]) if len(cols) > 2 else 0
                trust_short = parse_number(cols[4]) if len(cols) > 4 else 0
                trust_net = parse_number(cols[6]) if len(cols) > 6 else 0

        return FuturesPosition(
            product="台指期",
            foreign_long=foreign_long,
            foreign_short=foreign_short,
            foreign_net=foreign_net,
            dealer_long=dealer_long,
            dealer_short=dealer_short,
            dealer_net=dealer_net,
            trust_long=trust_long,
            trust_short=trust_short,
            trust_net=trust_net,
            date=date
        )

    except Exception as e:
        print(f"抓取期貨資料失敗: {e}")
        return None


@inst_cache(ttl_seconds=600)
def fetch_options_positions(date: Optional[str] = None) -> Optional[OptionsPosition]:
    """
    從期交所抓取三大法人選擇權部位
    https://www.taifex.com.tw/cht/3/callsAndPutsDateDown
    """
    if date is None:
        date = get_latest_trading_date()

    url = "https://www.taifex.com.tw/cht/3/callsAndPutsDateDown"
    formatted_date = date.replace('-', '/')

    params = {
        'queryDate': formatted_date,
        'commodityId': 'TXO'  # 台指選擇權
    }

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.taifex.com.tw/cht/3/callsAndPutsDate'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        lines = response.text.strip().split('\n')

        # 初始化
        call_foreign_long = call_foreign_short = call_foreign_net = 0
        put_foreign_long = put_foreign_short = put_foreign_net = 0
        call_dealer_long = call_dealer_short = call_dealer_net = 0
        put_dealer_long = put_dealer_short = put_dealer_net = 0

        current_type = ""  # CALL or PUT

        for line in lines:
            cols = line.split(',')
            if len(cols) < 7:
                continue

            # 判斷是 CALL 還是 PUT
            first_col = cols[0].strip().upper()
            if 'CALL' in first_col or '買權' in first_col:
                current_type = "CALL"
            elif 'PUT' in first_col or '賣權' in first_col:
                current_type = "PUT"

            identity = cols[1].strip() if len(cols) > 1 else ""

            if '外資' in identity or 'Foreign' in identity:
                if current_type == "CALL":
                    call_foreign_long = parse_number(cols[2]) if len(cols) > 2 else 0
                    call_foreign_short = parse_number(cols[4]) if len(cols) > 4 else 0
                    call_foreign_net = parse_number(cols[6]) if len(cols) > 6 else 0
                elif current_type == "PUT":
                    put_foreign_long = parse_number(cols[2]) if len(cols) > 2 else 0
                    put_foreign_short = parse_number(cols[4]) if len(cols) > 4 else 0
                    put_foreign_net = parse_number(cols[6]) if len(cols) > 6 else 0

            elif '自營商' in identity or 'Dealer' in identity:
                if current_type == "CALL":
                    call_dealer_long = parse_number(cols[2]) if len(cols) > 2 else 0
                    call_dealer_short = parse_number(cols[4]) if len(cols) > 4 else 0
                    call_dealer_net = parse_number(cols[6]) if len(cols) > 6 else 0
                elif current_type == "PUT":
                    put_dealer_long = parse_number(cols[2]) if len(cols) > 2 else 0
                    put_dealer_short = parse_number(cols[4]) if len(cols) > 4 else 0
                    put_dealer_net = parse_number(cols[6]) if len(cols) > 6 else 0

        # 計算 Put/Call Ratio
        total_call = abs(call_foreign_net) + abs(call_dealer_net)
        total_put = abs(put_foreign_net) + abs(put_dealer_net)
        pc_ratio = total_put / total_call if total_call > 0 else 1.0

        return OptionsPosition(
            call_foreign_long=call_foreign_long,
            call_foreign_short=call_foreign_short,
            call_foreign_net=call_foreign_net,
            put_foreign_long=put_foreign_long,
            put_foreign_short=put_foreign_short,
            put_foreign_net=put_foreign_net,
            call_dealer_long=call_dealer_long,
            call_dealer_short=call_dealer_short,
            call_dealer_net=call_dealer_net,
            put_dealer_long=put_dealer_long,
            put_dealer_short=put_dealer_short,
            put_dealer_net=put_dealer_net,
            pc_ratio=pc_ratio,
            date=date
        )

    except Exception as e:
        print(f"抓取選擇權資料失敗: {e}")
        return None


def get_latest_trading_date() -> str:
    """取得最近交易日 (排除週末)"""
    today = datetime.now()

    # 如果是週末，往前推到週五
    if today.weekday() == 5:  # 週六
        today = today - timedelta(days=1)
    elif today.weekday() == 6:  # 週日
        today = today - timedelta(days=2)

    # 如果現在是盤中（下午3點前），使用前一交易日
    if today.hour < 15:
        today = today - timedelta(days=1)
        if today.weekday() == 5:
            today = today - timedelta(days=1)
        elif today.weekday() == 6:
            today = today - timedelta(days=2)

    return today.strftime('%Y-%m-%d')


def analyze_institutional_signal(
    futures: Optional[FuturesPosition],
    options: Optional[OptionsPosition]
) -> InstitutionalSignal:
    """
    分析法人籌碼，產生綜合訊號

    判斷邏輯：
    1. 外資期貨淨多/淨空 (權重 40%)
    2. 自營商期貨淨部位 (權重 20%)
    3. 選擇權 Put/Call Ratio (權重 20%)
    4. 外資選擇權偏多偏空 (權重 20%)
    """
    date = futures.date if futures else (options.date if options else get_latest_trading_date())

    signals = []
    details = []
    score = 0  # -100 到 +100

    # 1. 分析期貨部位
    if futures:
        # 外資期貨
        if futures.foreign_net > 5000:
            score += 30
            signals.append("bullish")
            details.append(f"外資期貨淨多 {futures.foreign_net:,} 口 (強勢)")
        elif futures.foreign_net > 0:
            score += 15
            signals.append("bullish")
            details.append(f"外資期貨淨多 {futures.foreign_net:,} 口")
        elif futures.foreign_net < -5000:
            score -= 30
            signals.append("bearish")
            details.append(f"外資期貨淨空 {abs(futures.foreign_net):,} 口 (強勢)")
        elif futures.foreign_net < 0:
            score -= 15
            signals.append("bearish")
            details.append(f"外資期貨淨空 {abs(futures.foreign_net):,} 口")
        else:
            details.append("外資期貨持平")

        # 自營商期貨
        if futures.dealer_net > 3000:
            score += 15
            details.append(f"自營商期貨淨多 {futures.dealer_net:,} 口")
        elif futures.dealer_net < -3000:
            score -= 15
            details.append(f"自營商期貨淨空 {abs(futures.dealer_net):,} 口")
    else:
        details.append("期貨資料暫無法取得")

    # 2. 分析選擇權部位
    if options:
        # Put/Call Ratio
        if options.pc_ratio > 1.5:
            score -= 20
            signals.append("bearish")
            details.append(f"Put/Call Ratio {options.pc_ratio:.2f} (市場偏空)")
        elif options.pc_ratio > 1.2:
            score -= 10
            details.append(f"Put/Call Ratio {options.pc_ratio:.2f} (略偏空)")
        elif options.pc_ratio < 0.7:
            score += 20
            signals.append("bullish")
            details.append(f"Put/Call Ratio {options.pc_ratio:.2f} (市場偏多)")
        elif options.pc_ratio < 0.9:
            score += 10
            details.append(f"Put/Call Ratio {options.pc_ratio:.2f} (略偏多)")
        else:
            details.append(f"Put/Call Ratio {options.pc_ratio:.2f} (中性)")

        # 外資選擇權
        call_put_diff = options.call_foreign_net - options.put_foreign_net
        if call_put_diff > 10000:
            score += 15
            details.append(f"外資選擇權偏多 (CALL-PUT={call_put_diff:,})")
        elif call_put_diff < -10000:
            score -= 15
            details.append(f"外資選擇權偏空 (CALL-PUT={call_put_diff:,})")
    else:
        details.append("選擇權資料暫無法取得")

    # 3. 產生綜合訊號
    if score >= 30:
        signal = "bullish"
        color = "green"
        emoji = "🟢"
        strength = min(5, (score // 20) + 1)
        summary = "法人籌碼偏多，可積極操作"
    elif score <= -30:
        signal = "bearish"
        color = "red"
        emoji = "🔴"
        strength = min(5, (abs(score) // 20) + 1)
        summary = "法人籌碼偏空，宜謹慎防守"
    else:
        signal = "neutral"
        color = "yellow"
        emoji = "🟡"
        strength = 2
        summary = "法人籌碼中性，觀望為宜"

    return InstitutionalSignal(
        signal=signal,
        color=color,
        emoji=emoji,
        strength=strength,
        summary=summary,
        details=details,
        futures_position=futures,
        options_position=options,
        date=date
    )


def get_institutional_signal() -> InstitutionalSignal:
    """
    主要入口函數：取得最新法人籌碼訊號
    """
    futures = fetch_futures_positions()
    options = fetch_options_positions()
    return analyze_institutional_signal(futures, options)


# === 備用方案：從期交所網頁直接解析 ===

@inst_cache(ttl_seconds=600)
def fetch_futures_from_html() -> Optional[FuturesPosition]:
    """
    備用方案：從期交所網頁 HTML 抓取
    """
    url = "https://www.taifex.com.tw/cht/3/futContractsDate"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # 找到資料表格
        tables = soup.find_all('table', class_='table_f')

        if not tables:
            return None

        # 解析表格資料
        # 這裡需要根據實際網頁結構調整

        return None  # 如需要可進一步實作

    except Exception as e:
        print(f"HTML 抓取失敗: {e}")
        return None


# === 測試函數 ===

def test_fetch():
    """測試抓取功能"""
    print("=== 測試法人籌碼抓取 ===")

    signal = get_institutional_signal()

    print(f"\n日期: {signal.date}")
    print(f"訊號: {signal.emoji} {signal.signal.upper()}")
    print(f"強度: {'★' * signal.strength}{'☆' * (5 - signal.strength)}")
    print(f"摘要: {signal.summary}")
    print("\n詳細:")
    for detail in signal.details:
        print(f"  - {detail}")

    if signal.futures_position:
        f = signal.futures_position
        print(f"\n期貨部位:")
        print(f"  外資: 多{f.foreign_long:,} 空{f.foreign_short:,} 淨{f.foreign_net:,}")
        print(f"  自營: 多{f.dealer_long:,} 空{f.dealer_short:,} 淨{f.dealer_net:,}")

    if signal.options_position:
        o = signal.options_position
        print(f"\n選擇權部位:")
        print(f"  外資CALL淨: {o.call_foreign_net:,}")
        print(f"  外資PUT淨: {o.put_foreign_net:,}")
        print(f"  P/C Ratio: {o.pc_ratio:.2f}")


if __name__ == "__main__":
    test_fetch()
