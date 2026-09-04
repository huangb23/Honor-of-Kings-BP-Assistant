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

# 胜率分段（gameMode）：1=全分段, 3=1350+, 4=顶端排位, 6=巅峰千强(近5日聚合)
# 需抓取的分段集合（大众分段聚合需要 1/3/4/6）
WINRATE_GAME_MODES = [1, 3, 4, 6]
# 默认展示分段（后端加载胜率时使用）：'dianfeng'=巅峰千强(mode6), 'dazhong'=大众分段(聚合)
DEFAULT_WINRATE_MODE = 'dazhong'
WINRATE_FILE = "hero_winrate.json"

# 大众分段聚合权重：popular = (mode1*0.5 + mode3*1 + mode4*1 + mode6*0.5) / 3
POPULAR_WEIGHTS = {1: 0.5, 3: 1.0, 4: 1.0, 6: 0.5}
POPULAR_DIVISOR = 3.0

# 组合优势（协同/克制指数）来源
HERO_ANALYSIS_API = "/api/hero/analysis"   # ?heroId={id}
HERO_REGISTRY_API = "/api/hero/list"       # 若无英雄名册本地文件则用
HEROES_DIR = "heroes"                      # 存 {id}.json
COMBO_FILE = "combo_advantage.json"        # 汇总一份组合优势
COMBO_MAX_AGE_DAYS = 1                     # 每日更新：数据非今日则重新爬取

# 模型：英雄视角 18 权重（6 克制组 × csv/syn/cnt）。
# 权重实际定义在 model.W_CNT（按「对手克制数 0..5」分组），此处仅作说明保留。
MODEL_W = "见 model.W_CNT"

# 英雄名册文件（id/name/roles 映射）
REGISTRY_FILE = "hero_registry.json"