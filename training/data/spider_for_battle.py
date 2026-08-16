import json
import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from tqdm import tqdm  # 引入进度条库

POS = '打野'
csv_file = f"hero_battle_lineups_20260602_{POS}.csv"

def load_hero_whitelist_from_json(json_path="1.json"):
    """从本地的 1.json 中动态加载所有英雄名字，生成白名单集合"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            hero_data = json.load(f)
        hero_set = {item['name'] for item in hero_data if 'name' in item}
        print(f"📂 成功读取 {json_path}！已动态加载 {len(hero_set)} 个英雄作为过滤白名单。")
        return hero_set
    except Exception as e:
        print(f"🚨 读取 {json_path} 失败，请检查文件路径或格式！错误原因: {e}")
        return set()

def get_all_hero_names(driver, wait):
    """获取 31 个全量{POS}英雄清单"""
    first_roaming_xpath = f"(//p[text()='{POS}'])[1]/following-sibling::div"
    wait.until(EC.element_to_be_clickable((By.XPATH, first_roaming_xpath))).click()
    
    hero_box_xpath = f"//*[contains(@id, '-content-{POS}')]"
    wait.until(EC.presence_of_element_located((By.XPATH, f"{hero_box_xpath}//button")))
    
    scroll_container = driver.find_element(By.XPATH, hero_box_xpath)
    for _ in range(3):
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scroll_container)
        time.sleep(0.5)
    
    hero_elements = driver.find_elements(By.XPATH, f"{hero_box_xpath}//button//p")
    hero_names = [hero.text for hero in hero_elements if hero.text.strip()]
    
    print(f"🌲 成功初始化{POS}英雄库！共检测到 {len(hero_names)} 个英雄。\n")
    driver.refresh()
    return hero_names

def select_hero_by_name(driver, wait, area_index, hero_name):
    """选择指定阵营的英雄"""
    roaming_xpath = f"(//p[text()='{POS}'])[{area_index}]/following-sibling::div"
    wait.until(EC.element_to_be_clickable((By.XPATH, roaming_xpath))).click()
    
    target_hero_xpath = f"//*[contains(@id, '-content-{POS}')]//button[.//p[text()='{hero_name}']]"
    hero_btn = wait.until(EC.presence_of_element_located((By.XPATH, target_hero_xpath)))
    
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", hero_btn)
    time.sleep(0.2)
    driver.execute_script("arguments[0].click();", hero_btn)
    time.sleep(0.5)

def main_spider():
    file_exists = os.path.isfile(csv_file)
    
    WZRY_HEROES = load_hero_whitelist_from_json("1.json")
    if not WZRY_HEROES:
        print("❌ 英雄白名单为空，脚本退出。")
        return

    # 💡 【后台运行配置】：开启 Headless 模式
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # 新版无头模式，稳定且不易被网站检测
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080') # 虽是后台运行，但建议指定分辨率防止页面元素堆叠
    options.add_argument('--log-level=3')           # 屏蔽浏览器原生的一些不重要警告日志
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        url = "https://tianyuanzhiyi.com/battle"
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        
        hero_list = get_all_hero_names(driver, wait)
        total_heroes = len(hero_list)
        
        # 💡 计算总组合数：组合数公式 N * (N - 1) / 2
        total_combinations = int(total_heroes * (total_heroes - 1) / 2)
        print(f"📊 已启用优化算法，总对局组合已从 {total_heroes * total_heroes} 优化至 {total_combinations} 组！")
        print("🚀 正在启动后台无头浏览器，请静候进度条启动...\n")

        with open(csv_file, mode="a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["英雄A(阵营1)", "英雄B(阵营2)", "对局序号", "单局胜负摘要", "蓝方阵容(5人)", "红方阵容(5人)"])

            # 💡 【核心升级】：用 tqdm 托管你的双层循环进度
            with tqdm(total=total_combinations, desc="爬取总进度", unit="组") as pbar:
                for i in range(total_heroes):
                    # 采用你优化后的无重复组合循环
                    for j in range(i + 1, total_heroes):
                        hero_A = hero_list[i]
                        hero_B = hero_list[j]
                        
                        # 动态更新进度条左侧的描述文字，让你不看日志也知道后台在忙活啥
                        pbar.set_description(f"正在处理: 【{hero_A}】VS【{hero_B}】")
                        
                        try:
                            select_hero_by_name(driver, wait, 1, hero_A)
                            select_hero_by_name(driver, wait, 2, hero_B)
                            
                            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '查询对局记录')]")))
                            driver.execute_script("arguments[0].click();", submit_btn)
                            
                            # 智能轮询等待
                            has_data = False
                            for check_round in range(20): 
                                time.sleep(0.5)
                                cards_check = driver.find_elements(By.XPATH, "//div[@data-slot='card' and .//button[contains(., '详情')]]")
                                if len(cards_check) > 0:
                                    has_data = True
                                    break
                            
                            if not has_data:
                                pbar.update(1) # 没有数据也要推进1个进度
                                continue

                            match_cards = driver.find_elements(By.XPATH, "//div[@data-slot='card' and .//button[contains(., '详情')]]")
                            total_cards = len(match_cards) - 1
                            
                            for idx in range(total_cards):
                                current_match_cards = driver.find_elements(By.XPATH, "//div[@data-slot='card' and .//button[contains(., '详情')]]")
                                card = current_match_cards[idx]
                                
                                summary_text = card.find_element(By.CSS_SELECTOR, "p").text.strip().replace("\n", " ")
                                
                                detail_btn = card.find_element(By.XPATH, ".//button[contains(., '详情')]")
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", detail_btn)
                                driver.execute_script("arguments[0].click();", detail_btn)
                                time.sleep(0.4) 
                                
                                card_soup = BeautifulSoup(card.get_attribute("outerHTML"), "html.parser")
                                all_texts = [el.get_text(strip=True) for el in card_soup.find_all(string=True)]
                                
                                found_heroes = []
                                for text in all_texts:
                                    if text in WZRY_HEROES:
                                        if len(found_heroes) == 0 or found_heroes[-1] != text:
                                            found_heroes.append(text)
                                
                                game_heroes = found_heroes[:10]
                                blue_team = ",".join(game_heroes[:5])
                                red_team = ",".join(game_heroes[5:])
                                
                                if len(game_heroes) < 10:
                                    blue_team = ",".join(game_heroes)
                                    red_team = "未集齐10人"
                                
                                writer.writerow([hero_A, hero_B, idx + 1, summary_text, blue_team, red_team])
                                
                            f.flush() # 跑完一组立刻存盘
                            
                        except Exception as e:
                            # 即使某组报错，也只在控制台打一行，不中断大进度
                            print(f"\n⚠️ 组合【{hero_A} vs {hero_B}】遇到异常，已跳过: {e}")
                        
                        finally:
                            # 每一组跑完，更新进度条，并刷新重置页面
                            pbar.update(1)
                            driver.get(url)
                            time.sleep(0.8)
                            
    except Exception as e:
        print(f"\n🚨 全局遇到致命异常: {e}")
    finally:
        print("\n🏁 后台爬取任务全部结束。")
        driver.quit()

if __name__ == "__main__":
    main_spider()