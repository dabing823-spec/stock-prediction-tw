"""
排名躍進追蹤器 - 追蹤市值排名變化，找出潛在 0050 納入標的
Ranking Momentum Tracker - Track market cap ranking changes
"""

import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import pandas as pd


# 排名快照儲存路徑
RANKING_HISTORY_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "ranking_history.json"
)


@dataclass
class RankingChange:
    """排名變化資料"""
    code: str
    name: str
    current_rank: int
    previous_rank: int
    rank_change: int          # 正數表示排名上升 (數字變小)
    days_tracked: int         # 追蹤天數
    trend: str                # "rising", "falling", "stable"
    is_near_threshold: bool   # 是否接近 40 名門檻
    alert_level: str          # "high", "medium", "low"


@dataclass
class RankingSnapshot:
    """排名快照"""
    date: str
    rankings: Dict[str, int]  # {code: rank}
    names: Dict[str, str]     # {code: name}


def ensure_data_dir():
    """確保資料目錄存在"""
    data_dir = os.path.dirname(RANKING_HISTORY_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)


def load_ranking_history() -> List[RankingSnapshot]:
    """載入歷史排名資料"""
    ensure_data_dir()

    if not os.path.exists(RANKING_HISTORY_FILE):
        return []

    try:
        with open(RANKING_HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [
                RankingSnapshot(
                    date=item['date'],
                    rankings=item['rankings'],
                    names=item.get('names', {})
                )
                for item in data
            ]
    except Exception as e:
        print(f"載入排名歷史失敗: {e}")
        return []


def save_ranking_history(history: List[RankingSnapshot]):
    """儲存歷史排名資料"""
    ensure_data_dir()

    try:
        data = [
            {
                'date': s.date,
                'rankings': s.rankings,
                'names': s.names
            }
            for s in history
        ]
        with open(RANKING_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"儲存排名歷史失敗: {e}")


def update_ranking_snapshot(df_ranking: pd.DataFrame) -> RankingSnapshot:
    """
    更新今日排名快照
    df_ranking: 包含 ['排名', '股票代碼', '股票名稱'] 的 DataFrame
    """
    today = datetime.now().strftime('%Y-%m-%d')

    # 建立當前快照
    rankings = {}
    names = {}

    for _, row in df_ranking.iterrows():
        code = str(row.get('股票代碼', ''))
        rank = int(row.get('排名', 0))
        name = str(row.get('股票名稱', ''))

        if code and rank:
            rankings[code] = rank
            names[code] = name

    current_snapshot = RankingSnapshot(
        date=today,
        rankings=rankings,
        names=names
    )

    # 載入歷史並更新
    history = load_ranking_history()

    # 檢查今天是否已有快照
    existing_today = [s for s in history if s.date == today]
    if existing_today:
        # 更新今天的快照
        history = [s for s in history if s.date != today]

    history.insert(0, current_snapshot)

    # 只保留最近 90 天的資料
    cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    history = [s for s in history if s.date >= cutoff_date]

    save_ranking_history(history)

    return current_snapshot


def analyze_ranking_momentum(
    df_ranking: pd.DataFrame,
    lookback_days: int = 30,
    min_rank_change: int = 5
) -> List[RankingChange]:
    """
    分析排名躍進情況

    Args:
        df_ranking: 當前排名 DataFrame
        lookback_days: 回溯天數 (預設 30 天)
        min_rank_change: 最小排名變化 (預設 5 名)

    Returns:
        排名變化清單，按躍進幅度排序
    """
    # 更新今日快照
    current_snapshot = update_ranking_snapshot(df_ranking)

    # 載入歷史
    history = load_ranking_history()

    if len(history) < 2:
        # 資料不足，返回空列表
        return []

    # 找到 lookback_days 前的快照
    target_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    past_snapshot = None

    for snapshot in history:
        if snapshot.date <= target_date:
            past_snapshot = snapshot
            break

    # 如果沒有足夠久的歷史，使用最早的快照
    if past_snapshot is None and len(history) > 1:
        past_snapshot = history[-1]

    if past_snapshot is None:
        return []

    # 計算排名變化
    changes = []
    current_rankings = current_snapshot.rankings
    past_rankings = past_snapshot.rankings

    for code, current_rank in current_rankings.items():
        if code in past_rankings:
            past_rank = past_rankings[code]
            rank_change = past_rank - current_rank  # 正數表示排名上升

            # 判斷趨勢 (需要更多歷史資料才能準確判斷)
            if rank_change > 3:
                trend = "rising"
            elif rank_change < -3:
                trend = "falling"
            else:
                trend = "stable"

            # 判斷是否接近門檻
            is_near_threshold = 41 <= current_rank <= 55

            # 判斷警示等級
            if current_rank <= 45 and rank_change >= 10:
                alert_level = "high"
            elif current_rank <= 50 and rank_change >= 5:
                alert_level = "medium"
            else:
                alert_level = "low"

            # 計算追蹤天數
            days_tracked = (
                datetime.strptime(current_snapshot.date, '%Y-%m-%d') -
                datetime.strptime(past_snapshot.date, '%Y-%m-%d')
            ).days

            name = current_snapshot.names.get(code, past_snapshot.names.get(code, ''))

            changes.append(RankingChange(
                code=code,
                name=name,
                current_rank=current_rank,
                previous_rank=past_rank,
                rank_change=rank_change,
                days_tracked=days_tracked,
                trend=trend,
                is_near_threshold=is_near_threshold,
                alert_level=alert_level
            ))

    # 篩選並排序
    # 1. 篩選有顯著變化的
    significant_changes = [c for c in changes if abs(c.rank_change) >= min_rank_change]

    # 2. 按排名躍進幅度排序 (躍進最多的在前)
    significant_changes.sort(key=lambda x: x.rank_change, reverse=True)

    return significant_changes


def get_potential_inclusions(
    df_ranking: pd.DataFrame,
    current_holdings: List[str]
) -> Tuple[List[RankingChange], List[RankingChange]]:
    """
    取得潛在納入/剔除標的

    Returns:
        (potential_in, potential_out)
        - potential_in: 排名快速上升且接近門檻的非成分股
        - potential_out: 排名快速下降的現有成分股
    """
    all_changes = analyze_ranking_momentum(df_ranking, lookback_days=30, min_rank_change=3)

    # 潛在納入：排名上升 + 目前不在成分股 + 排名接近 40
    potential_in = [
        c for c in all_changes
        if c.rank_change > 0
        and c.code not in current_holdings
        and c.current_rank <= 60
    ]

    # 潛在剔除：排名下降 + 目前在成分股 + 排名接近 60
    potential_out = [
        c for c in all_changes
        if c.rank_change < 0
        and c.code in current_holdings
        and c.current_rank >= 50
    ]

    return potential_in, potential_out


def get_ranking_momentum_summary(df_ranking: pd.DataFrame) -> Dict:
    """
    取得排名動能摘要

    Returns:
        {
            'top_risers': List[RankingChange],  # 排名上升最多的
            'top_fallers': List[RankingChange], # 排名下降最多的
            'near_threshold': List[RankingChange],  # 接近門檻的
            'history_days': int,  # 歷史資料天數
        }
    """
    all_changes = analyze_ranking_momentum(df_ranking, lookback_days=30, min_rank_change=3)

    history = load_ranking_history()
    history_days = len(history)

    # 排名上升最多的 (前 10 名)
    top_risers = [c for c in all_changes if c.rank_change > 0][:10]

    # 排名下降最多的 (前 10 名)
    top_fallers = sorted(
        [c for c in all_changes if c.rank_change < 0],
        key=lambda x: x.rank_change
    )[:10]

    # 接近門檻且上升中的
    near_threshold = [
        c for c in all_changes
        if c.is_near_threshold and c.rank_change > 0
    ]

    return {
        'top_risers': top_risers,
        'top_fallers': top_fallers,
        'near_threshold': near_threshold,
        'history_days': history_days,
    }


# === 測試函數 ===

def test_ranking_tracker():
    """測試排名追蹤器"""
    import pandas as pd

    # 模擬排名資料
    test_data = {
        '排名': [1, 2, 3, 41, 42, 43, 50, 51],
        '股票代碼': ['2330', '2454', '2317', '3008', '2382', '6669', '3034', '2327'],
        '股票名稱': ['台積電', '聯發科', '鴻海', '大立光', '廣達', '緯穎', '聯詠', '國巨']
    }
    df = pd.DataFrame(test_data)

    print("=== 測試排名追蹤器 ===\n")

    # 更新快照
    snapshot = update_ranking_snapshot(df)
    print(f"已更新快照: {snapshot.date}")
    print(f"追蹤股票數: {len(snapshot.rankings)}")

    # 取得摘要
    summary = get_ranking_momentum_summary(df)
    print(f"\n歷史資料天數: {summary['history_days']}")
    print(f"排名上升股票數: {len(summary['top_risers'])}")
    print(f"接近門檻股票數: {len(summary['near_threshold'])}")


if __name__ == "__main__":
    test_ranking_tracker()
