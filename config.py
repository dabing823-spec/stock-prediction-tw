"""
應用程式配置常數
"""
from dataclasses import dataclass
from typing import Dict, List

# HTTP 請求設定
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
REQUEST_TIMEOUT = 20

# 快取時間 (秒)
CACHE_TTL_SHORT = 300      # 5 分鐘 - 即時行情
CACHE_TTL_MEDIUM = 3600    # 1 小時 - ETF 持股
CACHE_TTL_LONG = 86400     # 24 小時 - 殖利率、產業分類

# 市值排名設定
DEFAULT_RANKING_LIMIT = 200
TOP_50_LIMIT = 50
TOP_150_LIMIT = 150

# 0050 納入/剔除門檻
THRESHOLD_0050_MUST_IN = 40
THRESHOLD_0050_MUST_OUT = 60

# MSCI 納入/剔除門檻
THRESHOLD_MSCI_PROB_IN = 85
THRESHOLD_MSCI_PROB_OUT = 100

# 0056 高股息門檻
THRESHOLD_0056_RANK_MIN = 50
THRESHOLD_0056_RANK_MAX = 150

# VIXTWN 閾值
VIXTWN_HIGH = 26  # 買 PUT 降部位
VIXTWN_LOW = 24   # 可上槓桿

# 支援的 ETF 列表
SUPPORTED_ETFS = ["0050", "0056", "00878", "00919"]

# 高股息 ETF 調整月份
@dataclass
class ETFSchedule:
    name: str
    adjustment_months: List[int]

HIGH_YIELD_SCHEDULES = [
    ETFSchedule("00878 (國泰)", [5, 11]),
    ETFSchedule("0056 (元大)", [6, 12]),
    ETFSchedule("00919 (群益)", [5, 12]),
]

# 電子產業分類
TECH_SECTORS = ["Technology", "Semiconductors", "Electronic Technology"]

# 資料來源 URL
URLS = {
    "taifex_ranking": "https://www.taifex.com.tw/cht/9/futuresQADetail",
    "msci_list": "https://stock.capital.com.tw/z/zm/zmd/zmdc.djhtm?MSCI=0",
    "etf_holdings": "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={etf_code}.TW",
    "stockq_vix": "http://www.stockq.org/index/VIXTWN.php",
}
