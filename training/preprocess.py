"""
我现在有数据：data/hero_battle_lineups.csv，形如

廉颇,墨子,1,阵营2 胜利,"元歌,诸葛亮,公孙离,镜,墨子","曹操,海月,蚩奼,裴擒虎,廉颇"
廉颇,墨子,2,阵营1 胜利,"影,甄姬,孙尚香,橘右京,墨子","元歌,嫦娥,百里守约,哪吒,廉颇"
廉颇,墨子,3,阵营1 胜利,"元歌,小乔,敖隐,阿古朵,廉颇","曹操,沈梦溪,孙权,澜,墨子"
廉颇,庄周,1,阵营1 胜利,"夏洛特,干将莫邪,敖隐,司马懿,庄周","狂铁,诸葛亮,元流之子(射手),韩信,廉颇"
廉颇,庄周,2,阵营1 胜利,"关羽,诸葛亮,敖隐,马超,廉颇","姬小满,元流之子(法师),戈娅,云缨,庄周"
廉颇,庄周,3,阵营2 胜利,"元歌,海月,元流之子(射手),阿轲,庄周","关羽,甄姬,敖隐,露娜,廉颇"
廉颇,鲁班大师,6,阵营2 胜利,"夏侯惇,嫦娥,艾琳,马超,鲁班大师,蒙恬,蚩奼,孙悟空,廉颇",未集齐10人
庄周,瑶,14,阵营2 胜利,,未集齐10人

其中，前两个字段表示阵营，有第一个英雄（如廉颇）的为阵营1，有第二个英雄（如墨子/庄周）的为阵营2，处理后可以把胜利的阵营放在前面。若出现“未集齐10人”，则删除这条数据。

然后是数据 data/1.json. 形如：
[{
	"id": 105,
	"name": "廉颇",
	"avatarUrl": "https://img.pvp.mcxssg.net/manage/custom_wzry_skin_128x128/d9ce3579a525ab564afa50ba82d2fbe0.png",
	"roles": "游走/对抗路",
	"profession": "开团辅"
}, {
	"id": 106,
	"name": "小乔",
	"avatarUrl": "https://img.pvp.mcxssg.net/manage/custom_wzry_skin_128x128/34ca070ab867be1157b81b688be18cbb.png",
	"roles": "中路",
	"profession": "法核" ....
它提供了name和id之间的映射。

然后是data/20260529_top.csv ，形如
英雄,胜率,出场率,输出占比,承伤占比,分均经济,拿牌率,前期胜率,中期胜率,后期胜率
敖隐,50.5%,11.3%,23.9%,17.0%,698,25.5%,54.0%,50.0%,48.9%
马超,51.0%,16.6%,21.4%,20.2%,790,27.3%,50.9%,50.7%,47.6%
少司缘,53.5%,29.1%,12.7%,23.0%,584,38.7%,52.7%,51.7%,49.6%
我只需要每个英雄的胜率。

然后是data/heroes/{id}.json，它包括counters，counteredBy字段，例如：  

"counters": [
    {
      "heroName": "米莱狄",
      "totalMatches": 124,
      "advantageIndex": 9.67,
      "thresholdSource": "counterThreshold"
    },
    {
      "heroName": "扁鹊",
      "totalMatches": 97,
      "advantageIndex": 9.37,
      "thresholdSource": "counterThreshold"
    }
],
"counteredBy": [
    {
      "heroName": "大司命",
      "totalMatches": 774,
      "advantageIndex": -6.43,
      "thresholdSource": "counterThreshold"
    },
    {
      "heroName": "蒙犽",
      "totalMatches": 177,
      "advantageIndex": -6.35,
      "thresholdSource": "counterThreshold"
    }
]

表示 英雄（由文件id决定）和特定其它英雄作为对手时的胜率变化。

还包括"goodSynergies"和"badSynergies"字段，例如： 

"goodSynergies": [
    {
      "heroName": "扁鹊",
      "totalMatches": 137,
      "synergyIndex": 7.46
    },
表示 英雄（由文件id决定）和特定其它英雄作为队友时的胜率变化。


现在，我想要处理一开始的data/hero_battle_lineups.csv数据，去除无效数据后，按1：1划分训练集和测试集（固定seed）。并且对于每一条数据（假设已经都交换为第一个阵营获胜），处理成以下字段：
1. 第一个阵营各个英雄胜率。（5维）
2. 第二个阵营各个英雄胜率。（5维）
3. 第一个阵营英雄两两组合场次和胜率变化。（5*5）
4. 第二个阵营英雄两两组合场次和胜率变化。（5*5）
5. 第一个阵营英雄和第二个阵营英雄两两组合作为对手时的场次和胜率变化。（5*5）

然后，设计一个简单策略来进行训练和测试，预测哪一边获胜，给出准确率。要留出接口方便我写其它策略。

"""



import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from abc import ABC, abstractmethod

# ==========================================
# 1. 数据加载与预处理类
# ==========================================
class HonorOfKingsDataLoader:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.name_to_id = {}
        self.id_to_name = {}
        self.base_win_rates = {}
        self.hero_relations = {} # 存储每个英雄的 synergy 和 counter 数据
        
    def load_base_mappings(self):
        # 加载 1.json (Name -> ID)
        with open(os.path.join(self.base_dir, "1.json"), "r", encoding="utf-8") as f:
            data_1 = json.load(f)
            for item in data_1:
                self.name_to_id[item["name"]] = str(item["id"])
                self.id_to_name[str(item["id"])] = item["name"]
                
        # 加载 20260529_top.csv (基础胜率)
        top_df = pd.read_csv(os.path.join(self.base_dir, "20260529_top.csv"))
        for _, row in top_df.iterrows():
            hero_name = row["英雄"].strip()
            # 转换为浮点数格式 (如 50.5% -> 0.505)
            wr_str = str(row["胜率"]).replace("%", "")
            self.base_win_rates[hero_name] = float(wr_str) / 100.0

    def load_hero_relations(self):
        # 遍历 data/heroes/{id}.json
        heroes_dir = os.path.join(self.base_dir, "heroes")
        if not os.path.exists(heroes_dir):
            print(f"Warning: {heroes_dir} 不存在，关系指数将默认为 0")
            return
            
        for file_name in os.listdir(heroes_dir):
            if file_name.endswith(".json"):
                hero_id = file_name.split(".")[0]
                hero_name = self.id_to_name.get(hero_id)
                if not hero_name:
                    continue
                
                with open(os.path.join(heroes_dir, file_name), "r", encoding="utf-8") as f:
                    detail = json.load(f)
                
                # 初始化该英雄的映射关系
                self.hero_relations[hero_name] = {
                    "synergy": {}, # 队友 -> (matches, index)
                    "counter": {}  # 对手 -> (matches, index)
                }
                
                # 队友正/负协同
                for item in detail.get("goodSynergies", []) + detail.get("badSynergies", []):
                    self.hero_relations[hero_name]["synergy"][item["heroName"]] = (
                        item.get("totalMatches", 0), item.get("synergyIndex", 0.0)
                    )
                # 对手克制/被克制
                for item in detail.get("counters", []) + detail.get("counteredBy", []):
                    self.hero_relations[hero_name]["counter"][item["heroName"]] = (
                        item.get("totalMatches", 0), item.get("advantageIndex", 0.0)
                    )

    def get_relation_features(self, hero_a, hero_b, relation_type="synergy"):
        """获取 hero_a 与 hero_b 组合的 (场次, 胜率变化)"""
        if hero_a in self.hero_relations and hero_b in self.hero_relations[hero_a][relation_type]:
            return self.hero_relations[hero_a][relation_type][hero_b]
        return (0, 0.0)

    def process_lineups(self):
        csv_path = os.path.join(self.base_dir, "hero_battle_lineups.csv")
        # 由于CSV部分行未集齐10人列数可能有变，采用通用读取
        raw_data = []
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                if "未集齐10人" in line:
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                raw_data.append(parts)
                
        processed_features = []
        
        for row in raw_data:
            # 解析原始字段
            hero1, hero2, _, winner_tag = row[0], row[1], row[2], row[3]
            # 解析两个阵营的英雄列表（去除双引号）
            team_a_str = ",".join(row[4:9]).replace('"', '')
            team_b_str = ",".join(row[9:14]).replace('"', '')
            
            team_a = [h.strip() for h in team_a_str.split(",") if h.strip()]
            team_b = [h.strip() for h in team_b_str.split(",") if h.strip()]
            
            if len(team_a) != 5 or len(team_b) != 5:
                continue # 双重保险，确保满10人
                
            # 判断原本是谁包含了 阵营1/2 的特征英雄
            real_team1 = team_a if hero1 in team_a else team_b
            real_team2 = team_b if hero1 in team_a else team_a
            
            # 根据胜负关系进行调整，使第一个阵营永远是获胜方
            if "阵营1 胜利" in winner_tag:
                win_team, lose_team = real_team1, real_team2
            else:
                win_team, lose_team = real_team2, real_team1
                
            # --- 构建 5 组核心特征 ---
            # 1 & 2. 双方各自英雄的固有胜率 (默认0.5)
            win_base_wr = [self.base_win_rates.get(h, 0.5) for h in win_team]
            lose_base_wr = [self.base_win_rates.get(h, 0.5) for h in lose_team]
            
            # 3. 获胜方英雄两两组合(Synergy) -> 5x5
            win_synergy = []
            for h1 in win_team:
                row_feat = []
                for h2 in win_team:
                    row_feat.append(self.get_relation_features(h1, h2, "synergy"))
                win_synergy.append(row_feat)
                
            # 4. 失败方英雄两两组合(Synergy) -> 5x5
            lose_synergy = []
            for h1 in lose_team:
                row_feat = []
                for h2 in lose_team:
                    row_feat.append(self.get_relation_features(h1, h2, "synergy"))
                lose_synergy.append(row_feat)
                
            # 5. 获胜方 vs 失败方英雄组合(Counter) -> 5x5
            win_vs_lose_counter = []
            for h1 in win_team:
                row_feat = []
                for h2 in lose_team:
                    row_feat.append(self.get_relation_features(h1, h2, "counter"))
                win_vs_lose_counter.append(row_feat)
                
            processed_features.append({
                "win_team": win_team,
                "lose_team": lose_team,
                "win_base_wr": win_base_wr,
                "lose_base_wr": lose_base_wr,
                "win_synergy": win_synergy,
                "lose_synergy": lose_synergy,
                "win_vs_lose_counter": win_vs_lose_counter
            })
            
        return processed_features

# ==========================================
# 2. 预测策略抽象基类与基础实现
# ==========================================
class BasePredictionStrategy(ABC):
    @abstractmethod
    def train(self, train_data):
        """留给复杂机器学习模型的训练接口"""
        pass
        
    @abstractmethod
    def predict(self, sample):
        """
        输入单条样本特征，预测哪一边获胜。
        由于输入时已经将实际获胜方全部调整为前队，
        所以如果策略认为前队胜，返回 1 (预测正确)；认为后队胜，返回 0 (预测错误)。
        """
        pass

class SimpleWinRateStrategy(BasePredictionStrategy):
    """
    简单策略：基于双方英雄基础胜率之和 + 组合增益指数
    来综合评估两边胜率。
    """
    def __init__(self, alpha=1.0, beta=1.0):
        self.alpha = alpha  # 协同指数权重
        self.beta = beta    # 克制指数权重

    def train(self, train_data):
        # 简单规则无需显式训练，可在子类中用标准 ML 模型拟合权重
        pass
        
    def predict(self, sample):
        # 1. 基础胜率分
        score_team1 = sum(sample["win_base_wr"])
        score_team2 = sum(sample["lose_base_wr"])
        
        # 2. 队友协同分 (提取 5x5 矩阵中的 synergyIndex)
        for i in range(5):
            for j in range(5):
                if i != j:
                    score_team1 += self.alpha * sample["win_synergy"][i][j][1]
                    score_team2 += self.alpha * sample["lose_synergy"][i][j][1]
                    
        # 3. 对手克制分 (提取 5x5 矩阵中的 advantageIndex)
        for i in range(5):
            for j in range(5):
                # 队1对队2的克制加分
                score_team1 += self.beta * sample["win_vs_lose_counter"][i][j][1]
                # 队2对队1的克制分（通常由对战反向推导，这里视作样本中的相对克制）
                
        # 哪边分数高，就预测哪边获胜
        return 1 if score_team1 >= score_team2 else 0


# ==========================================
# 3. 评估与主流程
# ==========================================
def evaluate_strategy(strategy, train_data, test_data):
    # 训练模型
    strategy.train(train_data)
    
    # 测试模型
    correct_predictions = 0
    for sample in test_data:
        pred = strategy.predict(sample)
        if pred == 1: # 因为测试集里全被我们调成了前队赢，所以 pred==1 代表预测正确
            correct_predictions += 1
            
    accuracy = correct_predictions / len(test_data) if test_data else 0
    return accuracy

if __name__ == "__main__":
    # 初始化数据加载器
    # 确保当前路径有 data 文件夹且放入了你的文件
    loader = HonorOfKingsDataLoader(base_dir="data")
    
    print("正在加载基础映射与胜率数据...")
    loader.load_base_mappings()
    print("正在加载英雄对抗克制关系...")
    loader.load_hero_relations()
    
    print("正在处理原始对局阵容...")
    all_samples = loader.process_lineups()
    print(f"有效对局总数: {len(all_samples)}")
    
    if len(all_samples) == 0:
        print("未找到有效对局数据，请检查数据路径与格式。")
    else:
        # 1:1 固定种子切分训练集与测试集
        train_data, test_data = train_test_split(all_samples, test_size=0.5, random_state=42)
        print(f"训练集大小: {len(train_data)}, 测试集大小: {len(test_data)}")
        
        # 实例化并评估简单策略
        baseline_strategy = SimpleWinRateStrategy(alpha=0.01, beta=0.01) # 微调指数权重
        accuracy = evaluate_strategy(baseline_strategy, train_data, test_data)
        
        print("-" * 30)
        print(f"简单融合策略在测试集上的准确率 (Accuracy): {accuracy:.2%}")
        print("-" * 30)