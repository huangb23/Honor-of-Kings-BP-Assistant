# -*- coding: utf-8 -*-
"""
英雄胜率爬虫：直接使用站点"巅峰千强 近5日"聚合接口的 winRate。

来源：https://tianyuanzhiyi.com/api/herostats?date=YYYY-MM-DD&gameMode=6
  - gameMode=6 即"近 5 日聚合"，返回每个英雄的 winRate，无需再对多日取平均。
  - 每天只更新前一天数据，因此优先用"昨天"，若当天接口已就绪则用当天。

输出：backend/data/hero_winrate.json
    {
      "fetched_at": "2026-08-16",
      "game_mode": 6,
      "dates": ["2026-08-15"],
      "heroes": { "廉颇": {"winRate": 44.95, "days": 5}, ... }
    }

用法：.venv/bin/python -u winrate_crawler.py
"""
import os
import json
import datetime
import requests

from config import BASE_URL, HEADERS, WINRATE_GAME_MODE, DATA_DIR, WINRATE_FILE


def fetch_game_mode(session, date_str):
    """抓取某天 gameMode 的每英雄胜率，返回 {heroName: winRate}。"""
    url = f"{BASE_URL}/api/herostats?date={date_str}&gameMode={WINRATE_GAME_MODE}"
    r = session.get(url, timeout=25)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return {}
    return {item["heroName"]: item.get("winRate") for item in data}


def collect():
    session = requests.Session()
    session.headers.update(HEADERS)

    today = datetime.date.today()
    # 每天只更新前一天数据，优先从昨天开始；若昨天尚未出数据则继续回退更早
    for back in range(1, 8):
        d = today - datetime.timedelta(days=back)
        ds = d.isoformat()
        try:
            day_map = fetch_game_mode(session, ds)
        except Exception as e:
            print(f"⚠️ {ds} 抓取失败: {e}")
            continue
        if day_map:
            # 接口返回但胜率为 None 的英雄，用 45 兜底，保证与名册/组合英雄数一致
            out = {hero: {"winRate": round(wr if wr is not None else 45.0, 4), "days": 5}
                   for hero, wr in day_map.items()}
            os.makedirs(DATA_DIR, exist_ok=True)
            path = os.path.join(DATA_DIR, WINRATE_FILE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "fetched_at": today.isoformat(),
                    "game_mode": WINRATE_GAME_MODE,
                    "dates": [ds],
                    "heroes": out,
                }, f, ensure_ascii=False, indent=2)
            print(f"✅ 胜率已保存: {path}，共 {len(out)} 个英雄，来源日期 {ds}")
            return path

    raise RuntimeError("近几日均未抓到英雄胜率数据。")


def load():
    """读取已保存的胜率，返回 {hero: winRate}。
    每天新增前一天数据 → 若文件不存在或 fetched_at 不是今天，则重新拉取。"""
    path = os.path.join(DATA_DIR, WINRATE_FILE)
    if not os.path.exists(path):
        collect()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("fetched_at") != datetime.date.today().isoformat():
        print("⚠️ 胜率数据非今日，重新拉取近 5 日胜率...")
        collect()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return {h: v["winRate"] for h, v in data.get("heroes", {}).items()}


if __name__ == "__main__":
    collect()