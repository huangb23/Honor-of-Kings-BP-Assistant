# -*- coding: utf-8 -*-
"""
英雄视角 18 权重胜率模型（最终方案）。

将阵营得分拆到英雄视角：每个英雄按「对手克制数」落在 6 个克制组之一，
用该组的三项权重(csv/syn/cnt)乘以它的三项评分，阵营得分 = 5 英雄之和 / 5，
双方相减得 logit。win_rate = sigmoid(logit)。

三项评分（按有效条数归一化）：
  csv_i = 该英雄站点 csv 胜率（百分数）
  syn_i = (对队友有效 synergy 指数之和) / 有效 synergy 条数（0 条则 0）
  cnt_i = (对对手有效 counter 指数之和) / 有效 counter 条数（0 条则 0）

有效关系 = combo 中 totalMatches >= MIN_M（低频关系视为不存在）。

权重来自 training/train_18w.py（min=50, shrink=0，站点 csv 胜率口径），
18 个权重按「对手克制数 0..5」分组。
"""
import numpy as np

# 关系频次阈值：totalMatches < MIN_M 的关系视为不存在
MIN_M = 50

# 18 权重：W_CNT[k] = [csv, syn, cnt]，k = 对手克制数 (0..5)
W_CNT = [
    [ 0.0700,  0.0912,  0.0000],  # 0克制
    [ 0.0308,  0.0527,  0.0350],  # 1克制
    [-0.0106,  0.0631,  0.1059],  # 2克制
    [-0.0504,  0.1034,  0.1537],  # 3克制
    [-0.0915,  0.0592,  0.2217],  # 4克制
    [-0.1326,  0.0841,  0.2373],  # 5克制
]


# 中性占位符：用于将部分阵容补满到 5 人，贡献恒为 0
NEUTRAL = "__NEUTRAL__"


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
        :param combo_map:   {heroName: {"synergy": {A: {"idx":..,"m":..}}, "counter": {B: {...}}}}
        :param mode: 胜率分段：'dianfeng' 直接用巅峰千强；'dazhong' 按克制数插值
        """
        self.dianfeng = dianfeng_map
        self.popular = popular_map
        self.combo = combo_map
        self.mode = mode

    def _hero_winrate(self, hero, k=0):
        # 未选槽位：中性 50；查不到胜率的真实英雄：45（较弱兜底）
        if hero == NEUTRAL:
            return 50.0
        base_df = self.dianfeng.get(hero, 45.0)
        if self.mode != "dazhong":
            return base_df
        # 大众分段：按克制数 k 在「大众胜率」与「巅峰千强胜率」间线性插值
        base_pop = self.popular.get(hero, 45.0)
        return base_pop + (base_df - base_pop) * (k / 5.0)

    def _relation(self, hero, rel_type):
        return self.combo.get(hero, {}).get(rel_type, {})

    def _valid(self, hero, other, rel_type):
        _, m = _idx_m(self._relation(hero, rel_type), other)  # 第2个是 totalMatches
        return m >= MIN_M

    def _val(self, hero, other, rel_type):
        idx, m = _idx_m(self._relation(hero, rel_type), other)
        return idx if m >= MIN_M else 0.0

    def _hero_triple(self, hero, team, opp):
        """返回英雄 H 的三项评分 (csv, syn, cnt) 与其克制数 k。"""
        mates = [x for x in team if x != hero and x != NEUTRAL]
        opps = [x for x in opp if x != NEUTRAL]

        syn_cnt = sum(1 for m in mates if self._valid(hero, m, "synergy"))
        cnt_cnt = sum(1 for o in opps if self._valid(hero, o, "counter"))

        # 防御：对手数理论上 ≤5，异常输入时钳位避免越界
        k = min(cnt_cnt, 5)

        # csv 胜率按模式取值；大众分段时按克制数 k 在 大众↔巅峰 间插值
        csv_i = self._hero_winrate(hero, k)
        syn_i = sum(self._val(hero, m, "synergy") for m in mates)
        syn_i = syn_i / syn_cnt if syn_cnt > 0 else 0.0
        cnt_i = sum(self._val(hero, o, "counter") for o in opps)
        cnt_i = cnt_i / cnt_cnt if cnt_cnt > 0 else 0.0

        return k, (csv_i, syn_i, cnt_i)

    def _team_score(self, team, opp):
        """阵营得分 = 5 英雄评分之和 / 5（英雄视角求和）。

        未选槽位（NEUTRAL）按中性 50 胜率、无协同/克制计分（csv=50, syn=cnt=0, k=0），
        使部分阵容与满阵容可比。
        """
        team = list(team)
        # 补齐到 5 个槽位：未选槽位用 NEUTRAL 表示（csv=50、无协同/克制），
        # 保证部分阵容与满阵容在同一 5 槽尺度上可比。
        while len(team) < 5:
            team.append(NEUTRAL)
        total = 0.0
        for h in team:
            if h == NEUTRAL:
                wcsv, _, _ = W_CNT[0]
                total += wcsv * 50.0
                continue
            k, (csv_i, syn_i, cnt_i) = self._hero_triple(h, team, opp)
            wcsv, wsyn, wcnt = W_CNT[k]
            total += wcsv * csv_i + wsyn * syn_i + wcnt * cnt_i
        return total / 5.0

    def score(self, team1, team2):
        """logit = 我方阵营得分 - 敌方阵营得分。"""
        return self._team_score(team1, team2) - self._team_score(team2, team1)

    def win_rate(self, team1, team2):
        s = self.score(team1, team2)
        return 1.0 / (1.0 + np.exp(-s))