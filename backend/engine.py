# -*- coding: utf-8 -*-
"""
BP 推荐引擎。

输入：
  my_team   我方已选英雄（可为空/部分，≤5）
  opp_team  敌方已选英雄（可为空/部分，≤5）
  bans      已 ban 英雄（可选）
  role      可选，只推荐某分路；None 则按所有分路分组

输出：
  single_pick: { role: [ (hero, win_rate), ... top5 ] }
  double_pick: { "heroes": (a, b), "win_rate": x }  （最优双选组合）
  base_win_rate: 当前阵容胜率
"""
from itertools import combinations

ALL_ROLES = ["对抗路", "中路", "发育路", "打野", "游走"]


class BPEngine:
    def __init__(self, model, hero_roles):
        """
        :param model: WinRateModel
        :param hero_roles: {heroName: [role, ...]}  角色映射
        """
        self.model = model
        self.hero_roles = hero_roles
        self.heroes = set(hero_roles.keys())

    def candidates(self, my_team, opp_team, ban):
        """可选的英雄 = 全英雄池 − 已选(双方) − 已ban。"""
        used = set(my_team) | set(opp_team) | set(ban or [])
        return sorted(self.heroes - used)

    def base_win_rate(self, my_team, opp_team):
        return self.model.win_rate(my_team, opp_team)

    def single_pick_by_role(self, my_team, opp_team, ban=None, role=None, top_k=8):
        """每个分路推荐 top_k 个单英雄（加入后胜率最高）。"""
        cands = self.candidates(my_team, opp_team, ban)
        # 逐英雄计算加入后胜率
        results = []
        for h in cands:
            new_team = list(my_team) + [h]
            wr = self.model.win_rate(new_team, opp_team)
            results.append((h, wr))

        # 按分路分组
        if role is not None:
            roles = [role]
        else:
            roles = ALL_ROLES

        out = {}
        for r in roles:
            in_role = [x for x in results if r in self.hero_roles.get(x[0], [])]
            in_role.sort(key=lambda x: -x[1])
            out[r] = [(h, round(float(w), 4)) for h, w in in_role[:top_k]]
        return out

    def _pair_covers_empty(self, roles_a, roles_b, empty):
        """两人是否可分别放进两个不同的空分路。"""
        a = set(roles_a) & empty
        b = set(roles_b) & empty
        if not a or not b:
            return False
        return len(a | b) >= 2

    def suggest_double_pick(self, my_team, opp_team, ban=None, top_k=20, used_roles=None):
        """
        选 2 个英雄的最优组合（补齐两个不同的空分路）。
        :param used_roles: 我方已锁定位置（分路）集合（hero 与 role 都非空的槽）。
            双人组合的两人必须能分别补到两个不同的空位，避免推荐两个同分路/无效位置的英雄。
        """
        cands = self.candidates(my_team, opp_team, ban)
        used = set(used_roles or [])
        empty = set(ALL_ROLES) - used
        # 若空位不足 2 个，无法形成有效的双人补位
        if len(empty) < 2:
            return []
        best = []
        for a, b in combinations(cands, 2):
            if not self._pair_covers_empty(self.hero_roles.get(a, []),
                                           self.hero_roles.get(b, []), empty):
                continue
            new_team = list(my_team) + [a, b]
            wr = self.model.win_rate(new_team, opp_team)
            best.append(((a, b), wr))
        best.sort(key=lambda x: -x[1])
        return [(tuple(pair), round(float(wr), 4)) for pair, wr in best[:top_k]]