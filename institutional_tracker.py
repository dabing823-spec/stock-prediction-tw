"""
法人籌碼追蹤器 - 自動從期交所 OpenAPI 抓取法人期貨/選擇權部位
Institutional Position Tracker - Auto-fetch from TAIFEX OpenAPI
"""

import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from functools import wraps
import hashlib
import time

# 簡易快取
_inst_cache: Dict[str, tuple] = {}

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
    foreign_net: int       # 外資淨部位 (未平倉)
    foreign_net_change: int  # 外資淨變化 (當日交易)
    dealer_long: int       # 自營商多單
    dealer_short: int      # 自營商空單
    dealer_net: int        # 自營商淨部位
    dealer_net_change: int # 自營商淨變化
    trust_long: int        # 投信多單
    trust_short: int       # 投信空單
    trust_net: int         # 投信淨部位
    trust_net_change: int  # 投信淨變化
    date: str              # 日期


@dataclass
class PutCallRatioData:
    """Put/Call Ratio 資料"""
    date: str
    put_volume: int
    call_volume: int
    pc_volume_ratio: float    # 成交量 P/C Ratio
    put_oi: int               # Put 未平倉
    call_oi: int              # Call 未平倉
    pc_oi_ratio: float        # 未平倉 P/C Ratio


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
    pc_ratio: Optional[PutCallRatioData]
    date: str


TAIFEX_API_BASE = "https://openapi.taifex.com.tw/v1"


def parse_int(s: Any) -> int:
    """安全解析整數"""
    if s is None or s == '':
        return 0
    try:
        return int(str(s).replace(',', ''))
    except:
        return 0


def parse_float(s: Any) -> float:
    """安全解析浮點數"""
    if s is None or s == '':
        return 0.0
    try:
        return float(str(s).replace(',', ''))
    except:
        return 0.0


@inst_cache(ttl_seconds=600)
def fetch_futures_positions() -> Optional[FuturesPosition]:
    """
    從期交所 OpenAPI 抓取三大法人台指期部位
    API: /MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate
    """
    url = f"{TAIFEX_API_BASE}/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"

    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"API 回應錯誤: {response.status_code}")
            return None

        data = response.json()

        if not data:
            return None

        # 找到台股期貨的資料
        foreign_data = None
        dealer_data = None
        trust_data = None
        date = None

        for item in data:
            contract = item.get('ContractCode', '')
            identity = item.get('Item', '')

            # 只看台股期貨 (大台)
            if '臺股期貨' not in contract:
                continue

            if date is None:
                date = item.get('Date', '')

            if '外資' in identity:
                foreign_data = item
            elif '自營商' in identity:
                dealer_data = item
            elif '投信' in identity:
                trust_data = item

        if not date:
            return None

        # 格式化日期
        if len(date) == 8:
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        return FuturesPosition(
            product="台指期",
            foreign_long=parse_int(foreign_data.get('OpenInterest(Long)', 0)) if foreign_data else 0,
            foreign_short=parse_int(foreign_data.get('OpenInterest(Short)', 0)) if foreign_data else 0,
            foreign_net=parse_int(foreign_data.get('OpenInterest(Net)', 0)) if foreign_data else 0,
            foreign_net_change=parse_int(foreign_data.get('TradingVolume(Net)', 0)) if foreign_data else 0,
            dealer_long=parse_int(dealer_data.get('OpenInterest(Long)', 0)) if dealer_data else 0,
            dealer_short=parse_int(dealer_data.get('OpenInterest(Short)', 0)) if dealer_data else 0,
            dealer_net=parse_int(dealer_data.get('OpenInterest(Net)', 0)) if dealer_data else 0,
            dealer_net_change=parse_int(dealer_data.get('TradingVolume(Net)', 0)) if dealer_data else 0,
            trust_long=parse_int(trust_data.get('OpenInterest(Long)', 0)) if trust_data else 0,
            trust_short=parse_int(trust_data.get('OpenInterest(Short)', 0)) if trust_data else 0,
            trust_net=parse_int(trust_data.get('OpenInterest(Net)', 0)) if trust_data else 0,
            trust_net_change=parse_int(trust_data.get('TradingVolume(Net)', 0)) if trust_data else 0,
            date=date
        )

    except Exception as e:
        print(f"抓取期貨資料失敗: {e}")
        return None


@inst_cache(ttl_seconds=600)
def fetch_put_call_ratio() -> Optional[PutCallRatioData]:
    """
    從期交所 OpenAPI 抓取 Put/Call Ratio
    API: /PutCallRatio
    """
    url = f"{TAIFEX_API_BASE}/PutCallRatio"

    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            return None

        # 取最新一筆資料
        latest = data[0]

        date = latest.get('Date', '')
        if len(date) == 8:
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        return PutCallRatioData(
            date=date,
            put_volume=parse_int(latest.get('PutVolume', 0)),
            call_volume=parse_int(latest.get('CallVolume', 0)),
            pc_volume_ratio=parse_float(latest.get('PutCallVolumeRatio%', 100)) / 100,
            put_oi=parse_int(latest.get('PutOI', 0)),
            call_oi=parse_int(latest.get('CallOI', 0)),
            pc_oi_ratio=parse_float(latest.get('PutCallOIRatio%', 100)) / 100,
        )

    except Exception as e:
        print(f"抓取 P/C Ratio 失敗: {e}")
        return None


def analyze_institutional_signal(
    futures: Optional[FuturesPosition],
    pc_ratio: Optional[PutCallRatioData]
) -> InstitutionalSignal:
    """
    分析法人籌碼，產生綜合訊號

    判斷邏輯：
    1. 外資期貨淨部位 (未平倉) - 權重 40%
    2. 外資期貨淨變化 (當日交易) - 權重 20%
    3. 自營商期貨淨部位 - 權重 15%
    4. 選擇權 Put/Call Ratio (未平倉) - 權重 25%
    """
    date = futures.date if futures else (pc_ratio.date if pc_ratio else datetime.now().strftime('%Y-%m-%d'))

    details = []
    score = 0  # -100 到 +100

    # 1. 分析期貨部位
    if futures:
        # 外資期貨未平倉淨部位
        if futures.foreign_net > 10000:
            score += 30
            details.append(f"🟢 外資期貨未平倉淨多 {futures.foreign_net:,} 口")
        elif futures.foreign_net > 0:
            score += 15
            details.append(f"🟢 外資期貨未平倉淨多 {futures.foreign_net:,} 口")
        elif futures.foreign_net < -10000:
            score -= 30
            details.append(f"🔴 外資期貨未平倉淨空 {abs(futures.foreign_net):,} 口")
        elif futures.foreign_net < 0:
            score -= 15
            details.append(f"🔴 外資期貨未平倉淨空 {abs(futures.foreign_net):,} 口")
        else:
            details.append("⚪ 外資期貨未平倉持平")

        # 外資當日交易淨變化
        if futures.foreign_net_change > 3000:
            score += 15
            details.append(f"🟢 外資今日加碼多單 {futures.foreign_net_change:,} 口")
        elif futures.foreign_net_change < -3000:
            score -= 15
            details.append(f"🔴 外資今日加碼空單 {abs(futures.foreign_net_change):,} 口")

        # 自營商期貨
        if futures.dealer_net > 5000:
            score += 10
            details.append(f"🟢 自營商期貨淨多 {futures.dealer_net:,} 口")
        elif futures.dealer_net < -5000:
            score -= 10
            details.append(f"🔴 自營商期貨淨空 {abs(futures.dealer_net):,} 口")

        # 投信期貨 (通常量較小，參考即可)
        if futures.trust_net > 10000:
            score += 5
            details.append(f"🟢 投信期貨淨多 {futures.trust_net:,} 口")
        elif futures.trust_net < -5000:
            score -= 5
            details.append(f"🔴 投信期貨淨空 {abs(futures.trust_net):,} 口")
    else:
        details.append("⚠️ 期貨資料暫無法取得")

    # 2. 分析選擇權 Put/Call Ratio
    if pc_ratio:
        # 使用未平倉 P/C Ratio (更能反映市場預期)
        oi_ratio = pc_ratio.pc_oi_ratio

        if oi_ratio > 1.5:
            # P/C Ratio 高 = 市場買很多 Put = 散戶偏空 = 反向指標可能偏多
            score += 15
            details.append(f"🟢 P/C Ratio {oi_ratio:.2f} (散戶偏空，逆向偏多)")
        elif oi_ratio > 1.2:
            score += 5
            details.append(f"🟡 P/C Ratio {oi_ratio:.2f} (略偏空)")
        elif oi_ratio < 0.8:
            # P/C Ratio 低 = 市場買很多 Call = 散戶偏多 = 反向指標可能偏空
            score -= 15
            details.append(f"🔴 P/C Ratio {oi_ratio:.2f} (散戶偏多，逆向偏空)")
        elif oi_ratio < 1.0:
            score -= 5
            details.append(f"🟡 P/C Ratio {oi_ratio:.2f} (略偏多)")
        else:
            details.append(f"⚪ P/C Ratio {oi_ratio:.2f} (中性)")
    else:
        details.append("⚠️ 選擇權資料暫無法取得")

    # 3. 產生綜合訊號
    if score >= 25:
        signal = "bullish"
        color = "green"
        emoji = "🟢"
        strength = min(5, (score // 15) + 1)
        summary = "法人籌碼偏多，可積極操作"
    elif score <= -25:
        signal = "bearish"
        color = "red"
        emoji = "🔴"
        strength = min(5, (abs(score) // 15) + 1)
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
        pc_ratio=pc_ratio,
        date=date
    )


def get_institutional_signal() -> InstitutionalSignal:
    """
    主要入口函數：取得最新法人籌碼訊號
    """
    futures = fetch_futures_positions()
    pc_ratio = fetch_put_call_ratio()
    return analyze_institutional_signal(futures, pc_ratio)


# === 測試函數 ===

def test_fetch():
    """測試抓取功能"""
    print("=== 測試法人籌碼抓取 (TAIFEX OpenAPI) ===\n")

    # 測試期貨資料
    print("1. 抓取台指期三大法人部位...")
    futures = fetch_futures_positions()
    if futures:
        print(f"   日期: {futures.date}")
        print(f"   外資: 多{futures.foreign_long:,} 空{futures.foreign_short:,} 淨{futures.foreign_net:,} (今日{futures.foreign_net_change:+,})")
        print(f"   自營: 多{futures.dealer_long:,} 空{futures.dealer_short:,} 淨{futures.dealer_net:,}")
        print(f"   投信: 多{futures.trust_long:,} 空{futures.trust_short:,} 淨{futures.trust_net:,}")
    else:
        print("   抓取失敗")

    # 測試 P/C Ratio
    print("\n2. 抓取 Put/Call Ratio...")
    pc = fetch_put_call_ratio()
    if pc:
        print(f"   日期: {pc.date}")
        print(f"   成交量 P/C: {pc.pc_volume_ratio:.2f}")
        print(f"   未平倉 P/C: {pc.pc_oi_ratio:.2f}")
        print(f"   Put OI: {pc.put_oi:,}, Call OI: {pc.call_oi:,}")
    else:
        print("   抓取失敗")

    # 測試綜合訊號
    print("\n3. 產生綜合訊號...")
    signal = get_institutional_signal()
    print(f"   {signal.emoji} {signal.signal.upper()}")
    print(f"   強度: {'★' * signal.strength}{'☆' * (5 - signal.strength)}")
    print(f"   摘要: {signal.summary}")
    print("\n   詳細:")
    for detail in signal.details:
        print(f"   {detail}")


if __name__ == "__main__":
    test_fetch()
