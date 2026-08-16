# -*- coding: utf-8 -*-
"""
三特征胜率模型（公式见 training/SUMMARY.md）。

score = −0.2410·csv_diff + 0.2229·syn_diff + 0.3324·cnt_diff
win_rate = 1 / (1 + e^{−score})

特征（全部尺寸归一化，支持部分阵容）：
  csv_diff   我方英雄csv胜率均值 − 敌方英雄csv胜率均值   （胜率不 ÷100）
  syn_diff   我方队内协同指数均值 − 敌方队内协同指数均值
  cnt_diff   我方克敌方平均 − 敌方克我方平均
"""
import numpy as np

# 与 config 保持一致（权重固定，无截距）
W = {
    "csv": -0.2410,
    "synergy": 0.2229,
    "counter": 0.3324,
}


# 中性占位符：胜率=50、协同/克制=0，用于将部分阵容补满到 5 人
NEUTRAL = "__NEUTRAL__"


class WinRateModel:
    def __init__(self, winrate_map, combo_map):
        """
        :param winrate_map: {heroName: winRate}  巅峰千强近7天平均胜率（百分数）
        :param combo_map:   {heroName: {"synergy": {A: idx}, "counter": {B: idx}}}
        """
        self.winrate = winrate_map
        self.combo = combo_map

    def _hero_winrate(self, hero):
        # 查不到胜率的英雄，按较弱处理（45），避免误判为中性
        return self.winrate.get(hero, 45.0)

    def _synergy(self, a, b):
        return self.combo.get(a, {}).get("synergy", {}).get(b, 0.0)

    def _counter(self, a, b):
        return self.combo.get(a, {}).get("counter", {}).get(b, 0.0)

    def _pad(self, team):
        """把阵容补满到 5 人，缺位用中性占位符。"""
        team = list(team)
        while len(team) < 5:
            team.append(NEUTRAL)
        return team

    def csv_diff(self, team1, team2):
        t1 = self._pad(team1)
        t2 = self._pad(team2)
        m1 = sum(self._hero_winrate(h) for h in t1) / 5
        m2 = sum(self._hero_winrate(h) for h in t2) / 5
        return m1 - m2

    def synergy_diff(self, team1, team2):
        s1 = self._synergy_avg(self._pad(team1))
        s2 = self._synergy_avg(self._pad(team2))
        return s1 - s2

    def counter_diff(self, team1, team2):
        t1 = self._pad(team1)
        t2 = self._pad(team2)
        c12 = sum(self._counter(a, b) for a in t1 for b in t2)
        c21 = sum(self._counter(b, a) for a in t1 for b in t2)
        return (c12 - c21) / 25

    def _synergy_avg(self, team):
        # team 已补满 5 人；中性英雄贡献 0
        n = len(team)
        s = 0.0
        for i in range(n):
            for j in range(n):
                if i != j and team[i] != NEUTRAL and team[j] != NEUTRAL:
                    s += self._synergy(team[i], team[j])
        return s / (n * (n - 1)) if n >= 2 else 0.0

    def features(self, team1, team2):
        return {
            "csv_diff": self.csv_diff(team1, team2),
            "synergy_diff": self.synergy_diff(team1, team2),
            "counter_diff": self.counter_diff(team1, team2),
        }

    def score(self, team1, team2):
        f = self.features(team1, team2)
        return (W["csv"] * f["csv_diff"]
                + W["synergy"] * f["synergy_diff"]
                + W["counter"] * f["counter_diff"])

    def win_rate(self, team1, team2):
        s = self.score(team1, team2)
        return 1.0 / (1.0 + np.exp(-s))