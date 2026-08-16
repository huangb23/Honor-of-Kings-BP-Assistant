# 王者荣耀 BP 选人助手

基于英雄胜率 + 协同/克制指数，做 BP（Ban/Pick）阶段的胜率预测与选人推荐。

主分支 `main` 只保留**前后端**（`backend/` + `frontend/`）。训练与数据相关代码放在 `develop` 分支（`training/`、`win_rate/`），不污染主分支。

---

## 目录结构（main 分支）

```
wzry/
├── backend/            # Python 后端：数据爬取 + 胜率模型 + 预测 API
│   ├── main.py         # 命令行入口
│   ├── server.py       # BP 预测 HTTP 服务（零依赖，标准库 http.server）
│   ├── winrate_crawler.py   # 英雄胜率爬虫（巅峰千强近 5 日）
│   ├── combo_crawler.py     # 组合优势爬虫（协同/克制指数，≥5 天过期重爬）
│   ├── gen_pinyin.py        # 生成英雄拼音映射（前端拼音检索用）
│   ├── model.py        # 三特征胜率模型
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

### requirements.txt

后端运行只需 3 个第三方依赖（其余用 Python 标准库）：

```python
requests>=2.28   # 爬取英雄胜率与组合优势
numpy>=1.24      # 胜率模型数值计算
pypinyin>=0.50   # 生成英雄拼音映射（前端拼音检索）
```

---

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
- 点击"预测"展示：当前阵容胜率、各分路单英雄 Top5、双人组合 Top20

---

## 胜率模型（详见 backend/README.md 与 develop 分支的 training/SUMMARY.md）

```
csv_diff = mean(我方英雄csv胜率) − mean(敌方英雄csv胜率)      # 胜率不 ÷100
syn_diff = mean(我方队内协同)   − mean(敌方队内协同)
cnt_diff = mean(我方克制敌方)   − mean(敌方克制我方)

score = −0.2410·csv_diff + 0.2229·syn_diff + 0.3324·cnt_diff
win_rate = 1 / (1 + e^{−score})
```

- 无独热、无截距、无需归一化
- 特征来自站点 `tianyuanzhiyi.com`：巅峰千强近 5 日胜率、英雄协同 / 克制指数

---

## 数据更新

| 数据 | 来源 | 更新策略 |
|------|------|---------|
| 英雄胜率 | `herostats?date=昨日&gameMode=6`（巅峰千强近 5 日）| 每天自动刷新（非今日则重拉）|
| 组合优势 | `hero/analysis?heroId=`（协同 / 克制）| 距上次 ≥ 5 天则重爬 |
| 英雄名册 | 站点 herostats 全量 | 组合过期重爬时自动更新，含新英雄 |
| 英雄拼音 | 本地 pypinyin 生成 | 手动执行 `gen_pinyin.py` 重新生成 |

爬取产物（`backend/data/`）已在 `.gitignore` 中忽略，不入库。

---

## 分支约定

- **`main`**：前后端（`backend/`、`frontend/`、启动脚本、文档）
- **`develop`**：训练与数据采集（`training/`、`win_rate/`）

`.gitignore` 已忽略 `training/`、`win_rate/`、`backend/data/`，确保主分支干净。