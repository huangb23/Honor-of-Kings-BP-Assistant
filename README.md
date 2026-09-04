# 王者荣耀 BP 选人助手

基于英雄胜率 + 协同/克制指数，做 BP（Ban/Pick）阶段的胜率预测与选人推荐。


---

## 目录结构（main 分支）

```
wzry/
├── backend/            # Python 后端：数据爬取 + 胜率模型 + 预测 API
│   ├── main.py         # 命令行入口
│   ├── server.py       # BP 预测 HTTP 服务（零依赖，标准库 http.server）
│   ├── winrate_crawler.py   # 英雄胜率爬虫（巅峰千强近 5 日）
│   ├── combo_crawler.py     # 组合优势爬虫（协同/克制指数+totalMatches，每日更新）
│   ├── gen_pinyin.py        # 生成英雄拼音映射（前端拼音检索用）
│   ├── model.py        # 英雄视角 I5 交互模型（z=3.0 截断 + 5 全局系数）
│   ├── engine.py       # BP 推荐引擎
│   ├── config.py       # 全局配置
│   └── README.md       # 后端详细说明
├── frontend/           # 前端页面（纯 HTML+JS 单文件，由后端托管）
│   └── index.html
├── start.sh            # Mac / Linux 启动脚本
├── start.bat           # Windows 启动脚本
├── requirements.txt    # Python 依赖
├── README.md
└── .gitignore
```


## 快速启动

### 首次准备：安装依赖（系统 Python）

```bash
pip install -r requirements.txt
```

### Mac / Linux

```bash
./start.sh            # 默认端口 8000
./start.sh 9000       # 指定端口
```

### Windows

```
双击 start.bat
（或命令行：start.bat 9000）
```

启动后浏览器打开：**http://localhost:8000/index.html**

> 启动脚本默认使用**系统 `python3`/`python`**，不依赖任何 venv。

---

## 前端功能

- 我方 / 敌方各 5 个位置，默认分路为 对抗路 / 中路 / 发育路 / 打野 / 游走
- 每个位置支持**拼音检索**（全拼 / 首字母 / 拼音子串）+ 回车确认 + 退格清除
- 禁用（Ban）区支持**下拉多选**，回车后焦点停留可连续输入多个 ban
- 已选 / 已 ban 的英雄自动从下拉候选排除
- **清除按钮**：一键清空 11 个输入框（我方 5 + 敌方 5 + ban）
- **分段选择**：巅峰千强 / 大众分段（大众 = 按克制数在 大众聚合胜率 与 巅峰千强 之间插值）
- 点击"预测"展示：当前阵容胜率、各分路单英雄 Top8、双人组合 Top20
- 推荐英雄的**名字**按其自身胜率着色（47%~53% 区间：灰 → 蓝 → 绿 → 黄 → 红，越高越鲜艳），推荐旁附胜率-颜色图例条
- **排行榜区块**：胜率榜 Top10 + 相比前一天变动榜（上涨/下跌 Top10），随分段选择自动切换

---

## 胜率模型（详见 backend/README.md 与 develop 分支的 training/SUMMARY.md）

英雄视角 I5 交互模型：每个英雄的三项评分与「有效克制关系数 k」以交互项进入打分，
替代旧版「按 k 分组换权重」——权重曲线连续、无组间跳变。

```
每个英雄（k = 对 5 个对手的有效克制关系数，0..5）：
  hero_score = α·csv_i + β·(k·csv_i) + w_syn·syn_i + γ0·cnt_i + γ1·(k·cnt_i)
    csv_i = 该英雄站点 csv 胜率（百分数）
    syn_i = (对队友有效协同截断值之和) / 有效协同条数   # 低频关系(totalMatches<50)视为不存在
    cnt_i = (对对手有效克制截断值之和) / 有效克制条数

score = (Σ 我方 hero_score)/5 − (Σ 敌方 hero_score)/5
win_rate = 1 / (1 + e^{−score})
```

- 无独热、无截距、无需归一化
- 关系值先经 z=3.0 置信截断（抑制低场次大指数噪声）；系数与推导见 backend/README.md 与 develop 的 training/SUMMARY.md 附录
- 特征来自站点 `tianyuanzhiyi.com`：巅峰千强近 5 日胜率、英雄协同 / 克制指数（含 totalMatches）

---

## 数据更新

| 数据 | 来源 | 更新策略 |
|------|------|---------|
| 英雄胜率 | `herostats?date=昨日&gameMode={1,3,4,6}`（全分段/1350/顶端/巅峰千强）| 每天自动刷新（非今日则重拉）|
| 组合优势 | `hero/analysis?heroId=`（协同 / 克制）| 每天自动刷新（失败回填旧数据并重试）|
| 英雄名册 | 站点 herostats 全量 | 组合过期重爬时自动更新，含新英雄 |
| 英雄拼音 | 本地 pypinyin 生成 | 手动执行 `gen_pinyin.py` 重新生成 |

爬取产物（`backend/data/`）已在 `.gitignore` 中忽略，不入库。

---