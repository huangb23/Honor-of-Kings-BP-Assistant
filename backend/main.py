# -*- coding: utf-8 -*-
"""
backend 主入口。

用法：
  python3 -u main.py \
      --my 百里守约 墨子 \
      --opp 少司缘 元歌 西施 \
      --ban 瑶

说明：
  - 自动确保数据就绪（胜率近5日、组合优势未过期则不重爬）。
  - 输出当前胜率、各分路单英雄 Top5、以及最优双选组合。
"""
import os
import json
import argparse
import datetime

from config import DATA_DIR, DEFAULT_WINRATE_MODE
from winrate_crawler import load as load_winrate, winrate_for_mode
from combo_crawler import load_combo
from model import WinRateModel
from engine import BPEngine


def load_roles():
    """从 combo_crawler 的最新英雄名册读取 {hero: [roles]}。"""
    from combo_crawler import load_hero_registry
    registry = load_hero_registry()
    return {name: info["roles"] for name, info in registry.items()}


def parse_hero_list(arg_str):
    return [x for x in (arg_str.split(",") if arg_str else []) if x.strip()]


def main():
    parser = argparse.ArgumentParser(description="BP 胜率预测与选人推荐")
    parser.add_argument("--my", default="", help="我方已选英雄，逗号分隔")
    parser.add_argument("--opp", default="", help="敌方已选英雄，逗号分隔")
    parser.add_argument("--ban", default="", help="已ban英雄，逗号分隔")
    parser.add_argument("--role", default=None, help="指定分路(对抗路/中路/发育路/打野/游走)，默认全部分路")
    parser.add_argument("--mode", default=DEFAULT_WINRATE_MODE,
                        choices=["dianfeng", "dazhong"],
                        help="胜率分段：dianfeng=巅峰千强，dazhong=大众分段(全分段/1350/顶端/巅峰千强加权)")
    parser.add_argument("--force", action="store_true", help="强制重新爬取组合优势")
    args = parser.parse_args()

    my_team = parse_hero_list(args.my)
    opp_team = parse_hero_list(args.opp)
    bans = parse_hero_list(args.ban)

    # 1. 数据就绪
    print("📦 加载/更新数据 ...")
    modes_map = load_winrate()                       # {hero: {m1,m3,m4,m6}}
    combo = load_combo()                # {hero: {synergy, counter}}

    # 2. 构建模型与引擎（按分段：巅峰直接用 m6；大众按克制数在 大众↔巅峰 间插值）
    df = winrate_for_mode(modes_map, "dianfeng")
    if args.mode == "dazhong":
        pk = winrate_for_mode(modes_map, "dazhong")
        model = WinRateModel(df, pk, combo, mode="dazhong")
    else:
        model = WinRateModel(df, {}, combo, mode="dianfeng")
    roles = load_roles()
    engine = BPEngine(model, roles)

    # 3. 基础胜率
    base = engine.base_win_rate(my_team, opp_team)
    mode_label = "巅峰千强" if args.mode == "dianfeng" else "大众分段"
    print(f"\n📊 胜率分段: {mode_label}（{args.mode}）")
    print(f"🎮 我方已选: {my_team or '(空)'}")
    print(f"🔴 敌方已选: {opp_team or '(空)'}")
    print(f"🚫 已ban   : {bans or '(无)'}")
    if len(my_team) < 5 or len(opp_team) < 5:
        print(f"\n⚠️ 阵容未满 5v5，已用中性补齐计算；满 5 人后为校准的绝对胜率。")
    print(f"\n当前阵容我方胜率: {base:.4f}")

    # 4. 单英雄推荐（按分路）
    print(f"\n=== 单英雄推荐（加入后胜率 Top5，按分路）===")
    picks = engine.single_pick_by_role(my_team, opp_team, bans, role=args.role, top_k=5)
    for role, items in picks.items():
        print(f"  【{role}】")
        for i, (h, wr) in enumerate(items, 1):
            print(f"    Top{i} | {h:<8} 胜率={wr:.4f}")

    # 5. 双英雄推荐
    print(f"\n=== 双英雄组合推荐 ===")
    doubles = engine.suggest_double_pick(my_team, opp_team, bans, top_k=3)
    for i, ((a, b), wr) in enumerate(doubles, 1):
        print(f"  组合{i}: {a} + {b}  胜率={wr:.4f}")


if __name__ == "__main__":
    main()