# -*- coding: utf-8 -*-
"""
英雄视角交互模型（I5：z=3.0 置信截断 + 5 个全局系数，无分组）。

每个英雄的三项评分（csv/syn/cnt）与「有效克制关系数 k」以交互项形式进入打分，
替代旧版的「按 k 分组换权重」——权重曲线连续、无组间跳变：

  s_i = α·csv_i + β·(k_i·csv_i) + w_syn·syn_i + γ0·cnt_i + γ1·(k_i·cnt_i)

  csv_i = 该英雄站点 csv 胜率（百分数；大众分段按 k 在 大众↔巅峰 间插值）
  syn_i = 对队友有效协同截断值之和 / 有效协同条数
  cnt_i = 对对手有效克制截断值之和 / 有效克制条数
  k_i   = 对 5 个对手的有效克制关系数（totalMatches ≥ MIN_M，0..5）

阵营得分 = Σ s_i / 5；logit = 我方 − 敌方；win_rate = sigmoid(logit)。

关系值预处理（z=3.0 置信截断，抑制低场次大指数的噪声夸大）：
  idx_eff = sign(idx)·min(|idx|, μ_post + 3σ_post)
  μ_post = |idx|·τ²/(τ²+s²)，σ_post = sqrt(1/(1/τ²+1/s²))，s = 50/√m，τ = 1.83pp

隐含权重曲线（连续、可解释）：
  w_csv(k) = α + β·k：+0.062 → −0.145（被克制越多，自身胜率参考价值越低）
  w_cnt(k) = γ0 + γ1·k：0.040 → 0.277（克制信号随环境放大）

系数来源：training/exp_interaction.py（时间切分 80/20 训练集拟合，LR 无截距 C=1.0；
CV acc 0.5731 / 时间切分 0.5710，logloss 0.6770 为全部配置最低）。
实验推导与结论详见 training/SUMMARY.md 附录。
"""
import math

import numpy as np

# 关系频次阈值：totalMatches < MIN_M 的关系视为不存在
MIN_M = 50

# 置信截断参数
CAP_Z = 3.0     # 99.9% 置信上界
TAU = 1.83      # 真实效应先验标准差（百分点）
C_NOISE = 50.0  # 噪声尺度：s = C_NOISE / √m

# I5 交互模型系数（training/exp_interaction.py 时间切分拟合）
ALPHA_CSV = 0.061797   # csv 基础价值
BETA_KCSV = -0.041350  # 被针对时自身胜率价值的衰减（每条克制关系）
W_SYN = 0.079392       # 协同价值（全局）
GAMMA0 = -0.019284     # 克制价值基线
GAMMA1 = 0.059312      # 克制价值的环境放大（每条克制关系）

# 中性占位符：用于将部分阵容补满到 5 人，贡献恒为 0
NEUTRAL = "__NEUTRAL__"


def _cap(m, idx):
    """z=3.0 置信截断；idx=0（含缺失关系）原样返回。"""
    if idx == 0:
        return 0.0
    s2 = C_NOISE * C_NOISE / m
    f = TAU * TAU / (TAU * TAU + s2)
    a = abs(idx)
    mu = a * f
    sd = math.sqrt(1.0 / (1.0 / (TAU * TAU) + 1.0 / s2))
    return math.copysign(min(a, mu + CAP_Z * sd), idx)


def _idx_m(rel, hero_b):
    """从关系 dict 取 (指数, totalMatches)；无数据返回 (0.0, 0)。"""
    v = rel.get(hero_b)
    if v is None:
        return 0.0, 0
    if isinstance(v, dict):
        return float(v.get("idx", 0.0)), int(v.get("m", 0))
    # 兼容旧格式：直接存指数
    return float(v), 0


class WinRateModel:
    def __init__(self, dianfeng_map, popular_map, combo_map, mode="dianfeng"):
        """
        :param dianfeng_map: {heroName: winRate}  巅峰千强胜率（百分数）
        :param popular_map:  {heroName: winRate}  大众分段聚合胜率（百分数）
        :param combo_map:    {heroName: {"synergy": {A: {"idx":..,"m":..}}, "counter": {B: {...}}}}
        :param mode: 胜率分段：'dianfeng' 直接用巅峰千强；'dazhong' 按 k 在 大众↔巅峰 间插值
        """
        self.dianfeng = dianfeng_map
        self.popular = popular_map
        self.combo = combo_map
        self.mode = mode

    def _hero_winrate(self, hero, k=0.0):
        # 未选槽位：中性 50；查不到胜率的真实英雄：45（较弱兜底）
        if hero == NEUTRAL:
            return 50.0
        base_df = self.dianfeng.get(hero, 45.0)
        if self.mode != "dazhong":
            return base_df
        # 大众分段：被克制越多，越按巅峰千强口径评估（k=0..5 线性插值）
        base_pop = self.popular.get(hero, 45.0)
        return base_pop + (base_df - base_pop) * (min(k, 5.0) / 5.0)

    def _relation(self, hero, rel_type):
        return self.combo.get(hero, {}).get(rel_type, {})

    def _hero_triple(self, hero, team, opp):
        """返回英雄的三项评分 (csv_i, syn_i, cnt_i) 与有效克制数 k。"""
        mates = [x for x in team if x != hero and x != NEUTRAL]
        opps = [x for x in opp if x != NEUTRAL]

        syn_cnt = 0
        syn_sum = 0.0
        for m_ in mates:
            idx, m = _idx_m(self._relation(hero, "synergy"), m_)
            if m >= MIN_M:
                syn_sum += _cap(m, idx)
                syn_cnt += 1

        k = 0
        cnt_sum = 0.0
        for o in opps:
            idx, m = _idx_m(self._relation(hero, "counter"), o)
            if m >= MIN_M:
                cnt_sum += _cap(m, idx)
                k += 1

        syn_i = syn_sum / syn_cnt if syn_cnt > 0 else 0.0
        cnt_i = cnt_sum / k if k > 0 else 0.0
        csv_i = self._hero_winrate(hero, k)
        return csv_i, syn_i, cnt_i, k

    def _team_score(self, team, opp):
        """阵营得分 = 5 英雄贡献之和 / 5（英雄视角求和）。

        未选槽位（NEUTRAL）按中性 50 胜率、无协同/克制计分（csv=50, k=0, syn=cnt=0），
        使部分阵容与满阵容可比；空阵容对空阵容恰为 0.5。
        """
        team = list(team)
        while len(team) < 5:
            team.append(NEUTRAL)
        total = 0.0
        for h in team:
            if h == NEUTRAL:
                total += ALPHA_CSV * 50.0
                continue
            csv_i, syn_i, cnt_i, k = self._hero_triple(h, team, opp)
            total += (ALPHA_CSV * csv_i
                      + BETA_KCSV * k * csv_i
                      + W_SYN * syn_i
                      + GAMMA0 * cnt_i
                      + GAMMA1 * k * cnt_i)
        return total / 5.0

    def score(self, team1, team2):
        """logit = 我方阵营得分 - 敌方阵营得分。"""
        return self._team_score(team1, team2) - self._team_score(team2, team1)

    def win_rate(self, team1, team2):
        s = self.score(team1, team2)
        return 1.0 / (1.0 + np.exp(-s))
