import pandas as pd
import ast
import time
from pyzotero import zotero

# ==========================================
# 1. 请在此处填入你的 Zotero 认证信息
# ==========================================
API_KEY = '在此处粘贴你的API_KEY'
LIBRARY_ID = '在此处填入你的纯数字userID' 
LIBRARY_TYPE = 'user' # 如果是给群组文献库打标签，改成 'group'

zot = zotero.Zotero(LIBRARY_ID, LIBRARY_TYPE, API_KEY)

# 辅助函数：智能解析 CSV 里的标签格式
def parse_tags(tag_str):
    tag_str = str(tag_str).strip()
    if tag_str == 'nan' or not tag_str:
        return []
    # 如果 CSV 里是列表字符串格式 (如 "['@大规模MIMO', '#波束赋形']")
    if tag_str.startswith('[') and tag_str.endswith(']'):
        try:
            return ast.literal_eval(tag_str)
        except:
            pass
    # 如果 CSV 里是逗号或空格隔开的格式 (如 "@大规模MIMO, #波束赋形")
    tag_str = tag_str.replace('，', ',') # 兼容中文逗号
    return [t.strip() for t in tag_str.split(',') if t.strip()]

def main():
    # ==========================================
    # 2. 读取本地 CSV 文件
    # ==========================================
    try:
        df = pd.read_csv('tags.csv')
        print(f"📄 成功读取本地 tags.csv，包含 {len(df)} 条记录。")
    except FileNotFoundError:
        print("❌ 错误：未找到 tags.csv 文件，请检查文件是否在当前目录下。")
        return

    # ==========================================
    # 3. 从云端拉取 Zotero 完整文献库
    # ==========================================
    print("⏳ 正在连接 Zotero 获取文献库（可能需要几十秒）...")
    items = zot.everything(zot.items())
    items_to_update = []

    # 建立【统一小写标题 -> Zotero对象】的字典，无缝匹配
    zotero_items_dict = {}
    for item in items:
        if item['data']['itemType'] not in ['attachment', 'note']:
            title = item['data'].get('title', '').strip().lower()
            zotero_items_dict[title] = item

    print(f"☁️ 成功从云端获取 {len(zotero_items_dict)} 篇文献，开始执行匹配与标签更新...")

    # ==========================================
    # 4. 匹配标题 -> 删除旧 # 标签 -> 注入新标签
    # ==========================================
    for index, row in df.iterrows():
        csv_title = str(row.get('Title', '')).strip().lower()
        new_tags = parse_tags(row.get('Tags', ''))
        
        if not csv_title or csv_title == 'nan':
            continue

        if csv_title in zotero_items_dict:
            item = zotero_items_dict[csv_title]
            
            # 步骤 A：获取这篇文章在 Zotero 里现有的所有旧标签
            current_tags = [t['tag'] for t in item['data'].get('tags', [])]
            
            # 步骤 B：核心清理逻辑 -> 过滤掉所有以 '#' 开头的旧标签，保留其他的
            kept_tags = [t for t in current_tags if not str(t).startswith('#')]
            
            # 步骤 C：将保留下来的旧标签，与 CSV 里提取的新标签合并，并用 set() 去重
            updated_tags = list(set(kept_tags + new_tags))
            
            # 判断标签是否真的发生了变化，避免无效的网络请求
            if sorted(current_tags) != sorted(updated_tags):
                item['data']['tags'] = [{'tag': t} for t in updated_tags]
                items_to_update.append(item)
                print(f"✅ 更新成功: 《{row['Title'][:30]}...》\n   清理前: {current_tags}\n   更新后: {updated_tags}")
            else:
                print(f"⚡ 无需修改: 《{row['Title'][:30]}...》 标签已是最新。")
        else:
            print(f"❌ 未找到匹配文献: 《{row['Title'][:30]}...》")

    # ==========================================
    # 5. 批量同步更新到 Zotero 云端
    # ==========================================
    if items_to_update:
        print(f"\n🚀 准备将 {len(items_to_update)} 篇文献的新状态同步至 Zotero...")
        
        # 【修改点1】将批处理大小从 50 降低到 20
        batch_size = 20 
        
        for i in range(0, len(items_to_update), batch_size):
            batch = items_to_update[i:i+batch_size]
            
            # 【修改点2】加入自动重试机制（最多重试 3 次）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 尝试上传这一批次
                    zot.update_items(batch)
                    print(f"   -> ✅ 已成功同步第 {i+1} 到 {i+len(batch)} 篇。")
                    break  # 如果成功了，就跳出重试循环，处理下一批
                    
                except Exception as e:
                    print(f"   -> ⚠️ 第 {i+1} 到 {i+len(batch)} 篇遇到网络波动 ({type(e).__name__})")
                    if attempt < max_retries - 1:
                        print(f"      休息 3 秒后进行第 {attempt + 2} 次重试...")
                        time.sleep(3)  # 暂停 3 秒
                    else:
                        print("      ❌ 重试 3 次均失败，请检查网络代理或稍后单独运行。")
                        
        print("\n🎉 全部操作结束！请打开 Zotero 客户端，点击右上角的绿色同步按钮！")
    else:
        print("\n没有需要更新的条目。")

if __name__ == '__main__':
    main()
