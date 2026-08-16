# backend — BP 胜率预测与选人推荐器

给定"我方部分/满阵容 vs 敌方部分/满阵容 + 已 ban 英雄"，预测胜率，并推荐：
1. **单英雄选人**：按分路给出各位置的 Top5 推荐英雄及对应胜率
2. **双英雄选人**：给出最优的 2 英雄组合及对应胜率

## 快速使用

```bash
cd backend
python3 -u main.py \
    --my 百里守约,墨子,元流之子(坦克) \
    --opp 少司缘,元歌,西施,孙尚香,云缨 \
    --ban 瑶
```

参数：
| 参数 | 说明 |
|------|------|
| `--my` | 我方已选英雄，逗号分隔（可空/部分）|
| `--opp` | 敌方已选英雄，逗号分隔（可空/部分）|
| `--ban` | 已 ban 英雄，逗号分隔（可选）|
| `--role` | 只推荐某分路（对抗路/中路/发育路/打野/游走），默认全部分路 |
| `--force` | 强制重新爬取组合优势（默认按过期自动判断）|

**规则**：已选（无论我方还是敌方）与已 ban 的英雄不会再出现在推荐里。

**未满 5v5 处理**：未满的阵容用"中性"补齐（缺位英雄胜率按 45、协同/克制按 0），这样部分阵容也能算出可比、不虚高的胜率。满 5 人后即为校准的绝对胜率。

---

## 数据更新

### 英雄胜率（巅峰千强 近5日胜率）
来源：`https://tianyuanzhiyi.com/api/herostats?date=YYYY-MM-DD&gameMode=6`
- `gameMode=6` 直接返回"巅峰千强 **近5日聚合**胜率"，每个英雄一个 `winRate`，**无需再对多日取平均**。
- 每天只更新前一天数据，优先用昨天；当天接口若已就绪则用当天。
- **每天自动刷新**：若 `hero_winrate.json` 的 `fetched_at` 不是今天，则重新拉取；当天已爬过则复用。
- 保存到 `data/hero_winrate.json`（含全量英雄，胜率缺失的英雄用 45 兜底）。

### 组合优势（协同/克制指数）
来源：`https://tianyuanzhiyi.com/api/hero/analysis?heroId={id}`
- **英雄名册**直接从站点 `herostats` 接口拉取全量（含新英雄），保存为 `data/hero_registry.json`；站点失败才回退本地缓存 / 旧 1.json。
- 抓取每个英雄的 `goodSynergies`/`badSynergies`（协同）和 `counters`/`counteredBy`（克制）。
- 汇总为一份 `data/combo_advantage.json`（与胜率英雄数一致，当前 132）。
- **过期规则**：该文件距今 >= 5 天则重新爬取；否则直接复用。

---

## 数据文件（data/）

| 文件 | 内容 |
|------|------|
| `hero_winrate.json` | 每英雄近 7 天巅峰千强平均胜率 |
| `combo_advantage.json` | 每英雄的协同/克制指数（组合优势）|
| `hero_registry.json` | 英雄名 → id 映射（缓存）|

---

## 模型（training/SUMMARY.md）

```
csv_diff = mean(我方csv胜率) − mean(敌方csv胜率)      # 胜率不 ÷100
syn_diff = mean(我方队内协同) − mean(敌方队内协同)
cnt_diff = mean(我方克制敌方) − mean(敌方克制我方)

score = −0.2410·csv_diff + 0.2229·syn_diff + 0.3324·cnt_diff
win_rate = 1 / (1 + e^{−score})
```

- 无独热、无截距、无需归一化
- 权重固定（来自无截距逻辑回归 + 内化标准化）

---

## 模块

| 文件 | 作用 |
|------|------|
| `main.py` | 命令行入口 |
| `winrate_crawler.py` | 胜率爬虫 |
| `combo_crawler.py` | 组合优势爬虫（含过期检查）|
| `model.py` | 三特征模型（score / win_rate）|
| `engine.py` | BP 推荐引擎（单英雄 Top5 / 双英雄组合）|
| `config.py` | 全局配置（站点、天数、权重等）|