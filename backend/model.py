# -*- coding: utf-8 -*-
"""
英雄视角分组权重胜率模型（v2：z=3.0 置信截断 + 强/弱克制数分组）。

将阵营得分拆到英雄视角：每个英雄按「对手中强/弱克制关系」落在 8 组之一，
用该组的权重 (csv/syn/cnt) 乘以它的三项评分，阵营得分 = 5 英雄之和 / 5，
双方相减得 logit。win_rate = sigmoid(logit)。

关系值预处理（置信截断，z=3.0）：
  观测 idx = 真实效应 θ + 抽样噪声，s = 50/√m（百分点口径），先验 θ ~ N(0, τ²)，τ=1.83pp
  idx_eff = sign(idx)·min(|idx|, μ_post + 3·σ_post)
  μ_post = |idx|·τ²/(τ²+s²)，σ_post = sqrt(1/(1/τ² + 1/s²))
  动机：低场次关系的观测幅度被抽样噪声夸大，超过 99.9% 置信上界的部分不采信。

分组（代替旧版「有效克制数 0..5」分组，消除微弱克制导致的组间跳变）：
  对 5 个对手中每条有效关系（totalMatches ≥ MIN_M）的截断值 c：
    强克制：|c| ≥ STRONG_T (4.0)
    弱克制：有效且 |c| < 4.0
  组索引 k = min(强克制数, 3) × 2 + (1 if 有弱克制 else 0)   → 8 组

三项评分（按有效条数归一化，均使用截断后的值）：
  csv_i = 该英雄站点 csv 胜率（百分数；大众分段按克制强度 kf 在 大众↔巅峰 间插值）
  syn_i = 对队友有效协同截断值之和 / 有效协同条数
  cnt_i = 对对手有效克制截断值之和 / 有效克制条数

权重来自 training/exp_grouping.py（z=3.0 截断 + 强3档×弱有无分组，
时间切分 80/20 训练集拟合；CV acc 0.5737 vs 旧 18 权重 0.5728）。
实验结论详见 training/SUMMARY.md 附录。
"""
import math

import numpy as np

# 关系频次阈值：totalMatches < MIN_M 的关系视为不存在
MIN_M = 50

# 置信截断参数
CAP_Z = 3.0     # 99.9% 置信上界
TAU = 1.83      # 真实效应先验标准差（百分点）
C_NOISE = 50.0  # 噪声尺度：s = C_NOISE / √m

# 强/弱克制分界（截断后 |idx| ≥ STRONG_T 记为强克制）
STRONG_T = 4.0

# 24 权重：8 组 × [csv, syn, cnt]
# 组索引 k = min(强克制数, 3) * 2 + (有弱克制 ? 1 : 0)
W_CNT = [
    [-0.0413, 0.1150, 0.0000],   # 强0, 无弱
    [-0.0396, 0.0782, 0.1154],   # 强0, 有弱
    [-0.0330, 0.0976, 0.0513],   # 强1, 无弱
    [-0.0374, 0.0917, 0.1498],   # 强1, 有弱
    [-0.0289, 0.2540, 0.1819],   # 强2, 无弱
    [-0.0363, 0.0518, 0.2296],   # 强2, 有弱
    [-0.0188, 0.1544, 0.4469],   # 强3+, 无弱
    [-0.0150, 0.1954, 0.2544],   # 强3+, 有弱
]

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
        :param mode: 胜率分段：'dianfeng' 直接用巅峰千强；'dazhong' 按克制强度插值
        """
        self.dianfeng = dianfeng_map
        self.popular = popular_map
        self.combo = combo_map
        self.mode = mode

    def _hero_winrate(self, hero, kf=0.0):
        # 未选槽位：中性 50；查不到胜率的真实英雄：45（较弱兜底）
        if hero == NEUTRAL:
            return 50.0
        base_df = self.dianfeng.get(hero, 45.0)
        if self.mode != "dazhong":
            return base_df
        # 大众分段：按克制强度 kf（强数 + 0.5×弱数，0..5）在「大众」与「巅峰千强」间线性插值
        base_pop = self.popular.get(hero, 45.0)
        return base_pop + (base_df - base_pop) * (min(kf, 5.0) / 5.0)

    def _relation(self, hero, rel_type):
        return self.combo.get(hero, {}).get(rel_type, {})

    def _hero_triple(self, hero, team, opp):
        """返回英雄的 (组索引 k, 插值强度 kf, 三项评分 (csv, syn, cnt))。"""
        mates = [x for x in team if x != hero and x != NEUTRAL]
        opps = [x for x in opp if x != NEUTRAL]

        syn_cnt = 0
        syn_sum = 0.0
        for m_ in mates:
            idx, m = _idx_m(self._relation(hero, "synergy"), m_)
            if m >= MIN_M:
                syn_sum += _cap(m, idx)
                syn_cnt += 1

        n_strong = 0
        n_weak = 0
        cnt_cnt = 0
        cnt_sum = 0.0
        for o in opps:
            idx, m = _idx_m(self._relation(hero, "counter"), o)
            if m >= MIN_M:
                c = _cap(m, idx)
                cnt_sum += c
                cnt_cnt += 1
                if abs(c) >= STRONG_T:
                    n_strong += 1
                else:
                    n_weak += 1

        syn_i = syn_sum / syn_cnt if syn_cnt > 0 else 0.0
        cnt_i = cnt_sum / cnt_cnt if cnt_cnt > 0 else 0.0

        # 克制强度 kf：强克制 + 0.5×弱克制（0..5），用于大众分段插值
        kf = min(n_strong + 0.5 * n_weak, 5.0)
        csv_i = self._hero_winrate(hero, kf)

        group = min(n_strong, 3) * 2 + (1 if n_weak > 0 else 0)
        return group, kf, (csv_i, syn_i, cnt_i)

    def _team_score(self, team, opp):
        """阵营得分 = 5 英雄评分之和 / 5（英雄视角求和）。

        未选槽位（NEUTRAL）按中性 50 胜率、无协同/克制计分（csv=50, syn=cnt=0，
        落入「强0, 无弱」组），使部分阵容与满阵容可比。
        """
        team = list(team)
        while len(team) < 5:
            team.append(NEUTRAL)
        total = 0.0
        for h in team:
            if h == NEUTRAL:
                wcsv, _, _ = W_CNT[0]
                total += wcsv * 50.0
                continue
            group, _, (csv_i, syn_i, cnt_i) = self._hero_triple(h, team, opp)
            wcsv, wsyn, wcnt = W_CNT[group]
            total += wcsv * csv_i + wsyn * syn_i + wcnt * cnt_i
        return total / 5.0

    def score(self, team1, team2):
        """logit = 我方阵营得分 - 敌方阵营得分。"""
        return self._team_score(team1, team2) - self._team_score(team2, team1)

    def win_rate(self, team1, team2):
        s = self.score(team1, team2)
        return 1.0 / (1.0 + np.exp(-s))
