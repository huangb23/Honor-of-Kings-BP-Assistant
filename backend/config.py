# -*- coding: utf-8 -*-
"""backend 全局配置。"""
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, 'data')

# 数据站点
BASE_URL = "https://tianyuanzhiyi.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://tianyuanzhiyi.com/",
}

# 胜率：巅峰千强(gameMode=6=近5日聚合)，直接取该接口的 winRate，无需多日平均
WINRATE_GAME_MODE = 6          # 1=全分段, 3=1350+, 4=顶端排位, 5=巅峰千强(单日), 6=巅峰千强(近5日)
WINRATE_FILE = "hero_winrate.json"

# 组合优势（协同/克制指数）来源
HERO_ANALYSIS_API = "/api/hero/analysis"   # ?heroId={id}
HERO_REGISTRY_API = "/api/hero/list"       # 若无英雄名册本地文件则用
HEROES_DIR = "heroes"                      # 存 {id}.json
COMBO_FILE = "combo_advantage.json"        # 汇总一份组合优势
COMBO_MAX_AGE_DAYS = 5                     # 超过 5 天则重新爬取

# 模型权重（来自 SUMMARY.md，无截距、无归一化）
MODEL_W = {
    "csv": -0.2410,
    "synergy": 0.2229,
    "counter": 0.3324,
}

# 英雄名册文件（id/name/roles 映射）
REGISTRY_FILE = "hero_registry.json"