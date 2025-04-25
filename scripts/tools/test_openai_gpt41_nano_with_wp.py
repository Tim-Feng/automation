#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import re
import logging
from datetime import datetime

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('/Users/Mac/GitHub/automation/logs/automation_workflow.log'),
        logging.StreamHandler()
    ]
)

# 創建日誌記錄器
logger = logging.getLogger('Stage-test')
logger.setLevel(logging.INFO)

# 添加一個 emoji 格式化器
class EmojiFormatter(logging.Formatter):
    def format(self, record):
        level_emoji = {
            logging.DEBUG: '🔍',
            logging.INFO: 'ℹ️',
            logging.WARNING: '⚠️',
            logging.ERROR: '❌',
            logging.CRITICAL: '🔥'
        }
        record.emoji = level_emoji.get(record.levelno, '🔧')
        return super().format(record)

# 設置格式化器
formatter = EmojiFormatter('%(asctime)s %(emoji)s [Stage-test] [openai_gpt41_nano] [%(levelname)s] %(message)s')

# 應用到所有處理器
for handler in logger.handlers:
    handler.setFormatter(formatter)

for handler in logging.getLogger().handlers:
    handler.setFormatter(formatter)

class WordPressClient:
    def __init__(self):
        """初始化 WordPress 客戶端"""
        self.site_url = os.getenv("WP_SITE_URL")
        self.username = os.getenv("WP_USERNAME")
        self.password = os.getenv("WP_APP_PASSWORD")
        
        if not self.site_url or not self.username or not self.password:
            raise ValueError("請設置 WordPress API 相關環境變數")
            
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = (self.username, self.password)
        self.headers = {'Content-Type': 'application/json'}
        logger.info(f"初始化 WordPress 客戶端，API 基礎網址: {self.api_base}")
        
    def get_post(self, post_id):
        """獲取指定 ID 的文章"""
        logger.info(f"獲取文章 ID: {post_id}")
        endpoint = f"{self.api_base}/video/{post_id}"
        response = requests.get(endpoint, auth=self.auth, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"獲取文章 {post_id} 失敗: {response.status_code} - {response.text}")
            raise Exception(f"獲取文章失敗: {response.status_code} - {response.text}")
            
        logger.info(f"成功獲取文章 {post_id}")
        return response.json()
        
    def get_post_meta(self, post_id, meta_key):
        """獲取指定文章的中繼資料"""
        logger.info(f"獲取文章 {post_id} 的中繼資料: {meta_key}")
        endpoint = f"{self.api_base}/video/{post_id}"
        response = requests.get(endpoint, auth=self.auth, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"獲取文章 {post_id} 的中繼資料失敗: {response.status_code} - {response.text}")
            raise Exception(f"獲取文章中繼資料失敗: {response.status_code} - {response.text}")
            
        data = response.json()
        meta_value = data.get('meta', {}).get(meta_key, "")
        logger.info(f"成功獲取文章 {post_id} 的 {meta_key}")
        return meta_value

class OpenAIAssistantTester:
    def __init__(self, model_version):
        self.model = model_version
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("請設置 OPENAI_API_KEY 環境變數")
        self.client = OpenAI(api_key=api_key)  # 明確傳入 API 金鑰
        logger.info(f"初始化 OpenAI Assistant 測試器，使用模型: {self.model}")
        
        # 取得專案根目錄
        self.project_root = Path(__file__).parent.parent.parent
        
        # 載入系統提示詞
        system_prompt_path = self.project_root / "prompts" / "openai" / "system_prompt.txt"
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()
            
        # 載入 function schema
        function_schema_path = self.project_root / "prompts" / "openai" / "function_schema.json"
        with open(function_schema_path, 'r', encoding='utf-8') as f:
            self.function_schema = json.load(f)
            
        # 測試結果
        self.results = {
            "model": model_version,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": False,
            "processing_time": 0,
            "openai_processing_time": 0,
            "tag_count": 0,
            "tags": {},
            "estimated_tokens": {
                "input": 0,
                "output": 0,
                "total": 0
            },
            "estimated_cost": {
                "input": 0,
                "output": 0,
                "total": 0
            },
            "error": None,
            "raw_response": None
        }
    
    def create_test_assistant(self):
        """創建測試用 Assistant"""
        try:
            # 確保 function schema 格式正確
            function_def = self.function_schema["functions"][0]
            
            # 創建 Assistant
            assistant = self.client.beta.assistants.create(
                name=f"Tag Suggestion Tester - {self.model}",
                instructions=self.system_prompt,
                model=self.model,
                tools=[{"type": "function", "function": function_def}]
            )
            logger.info(f"成功建立測試用 Assistant: {assistant.id}")
            return assistant
        except Exception as e:
            logger.error(f"建立 Assistant 時發生錯誤: {str(e)}")
            raise
    
    def delete_assistant(self, assistant_id):
        """刪除測試用 Assistant"""
        try:
            self.client.beta.assistants.delete(assistant_id)
            logger.info(f"成功刪除測試用 Assistant: {assistant_id}")
        except Exception as e:
            logger.error(f"刪除 Assistant 時發生錯誤: {str(e)}")
    
    def wait_for_completion(self, thread_id, run_id, timeout=120):
        """等待處理完成並返回結果
        
        Args:
            thread_id: 對話執行緒 ID
            run_id: 執行 ID
            timeout: 超時時間（秒）
            
        Returns:
            處理結果
        """
        start_time = time.time()
        
        while True:
            # 檢查是否超時
            if time.time() - start_time > timeout:
                logger.error(f"標籤生成超時，已等待 {timeout} 秒")
                raise TimeoutError(f"Tag suggestion timeout after {timeout} seconds")
                
            # 獲取執行狀態
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            if run.status == "completed":
                # 獲取最後一條消息
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                last_message = messages.data[0]
                
                # 嘗試解析 JSON
                raw_content = last_message.content[0].text.value
                logger.info(f"原始回應內容長度: {len(raw_content)} 字元")
                
                print(f"\n原始回應內容: {raw_content}\n")
                
                # 嘗試解析 JSON
                try:
                    # 嘗試直接解析
                    tags = json.loads(raw_content)
                    return tags
                except json.JSONDecodeError:
                    logger.warning("回應不是有效的 JSON，嘗試尋找 JSON 部分")
                    
                    # 嘗試從代碼塊中提取 JSON
                    json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
                    json_match = re.search(json_pattern, raw_content)
                    
                    if json_match:
                        try:
                            tags = json.loads(json_match.group(1))
                            return tags
                        except json.JSONDecodeError:
                            logger.warning("代碼塊中的內容不是有效的 JSON")
                    
                    # 嘗試從文本中提取 JSON 物件
                    json_object_pattern = r'\{[\s\S]*?\}'
                    json_object_match = re.search(json_object_pattern, raw_content)
                    
                    if json_object_match:
                        try:
                            tags = json.loads(json_object_match.group(0))
                            return tags
                        except json.JSONDecodeError:
                            logger.warning("找到的 JSON 物件不是有效的 JSON")
                    
                    # 如果無法解析 JSON，嘗試從文本中提取標籤
                    structured_tags = {}
                    current_category = None
                    
                    # 從文本中提取標籤
                    for line in raw_content.split('\n'):
                        # 移除 Markdown 標記和空白
                        line = line.strip()
                        if not line:
                            continue
                            
                        # 檢查是否是類別標題
                        if line.startswith('###') or line.startswith('#'):
                            category_match = re.search(r'#+ *(.*?)$', line)
                            if category_match:
                                current_category = category_match.group(1).strip()
                                structured_tags[current_category] = []
                        # 檢查是否是標籤項目
                        elif line.startswith('-') or line.startswith('*') or ':' in line:
                            if current_category:
                                # 提取標籤
                                tag_match = re.search(r'[-*] *(.*?)$', line)
                                if tag_match:
                                    tag = tag_match.group(1).strip()
                                    structured_tags[current_category].append(tag)
                                else:
                                    # 嘗試從冒號分隔的格式提取
                                    tag_match = re.search(r'(.*?): *(.*?)$', line)
                                    if tag_match:
                                        sub_category = tag_match.group(1).strip()
                                        tags = tag_match.group(2).strip()
                                        if sub_category and tags:
                                            if sub_category not in structured_tags:
                                                structured_tags[sub_category] = []
                                            structured_tags[sub_category].append(tags)
                    
                    # 如果成功提取到標籤
                    if structured_tags:
                        logger.info("從文本中提取到結構化標籤")
                        return structured_tags
                    
                    # 如果所有嘗試都失敗，返回原始文本
                    return {"raw_text": raw_content}
            
            elif run.status == "failed":
                logger.error(f"標籤生成失敗: {run.last_error}")
                raise Exception(f"標籤生成失敗: {run.last_error}")
                
            # 等待一段時間再檢查
            time.sleep(1)
    
    def test_tag_suggestion(self, content):
        """測試標籤建議功能
        
        Args:
            content: 要分析的內容
            
        Returns:
            測試結果
        """
        start_time = time.time()
        assistant = None
        thread = None
        
        try:
            # 創建 Assistant
            assistant = self.create_test_assistant()
            
            # 創建對話執行緒
            thread = self.client.beta.threads.create()
            
            # 添加用戶消息
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=content
            )
            
            # 執行 Assistant
            openai_start_time = time.time()
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id
            )
            
            # 等待處理完成
            tags = self.wait_for_completion(thread.id, run.id)
            openai_processing_time = time.time() - openai_start_time
            
            # 計算標籤數量
            tag_count = 0
            for category, tag_list in tags.items():
                if isinstance(tag_list, list):
                    tag_count += len(tag_list)
                elif isinstance(tag_list, str):
                    tag_count += 1
            
            # 估算 token 使用量和成本
            input_tokens = len(content) / 4  # 粗略估算
            output_tokens = len(json.dumps(tags, ensure_ascii=False)) / 4  # 粗略估算
            
            # 根據模型計算成本
            input_cost_per_token = 0.00015  # 預設值
            output_cost_per_token = 0.0006  # 預設值
            
            if self.model == "gpt-4o-mini":
                input_cost_per_token = 0.00015
                output_cost_per_token = 0.0006
            elif self.model == "gpt-4.1-mini":
                input_cost_per_token = 0.0001
                output_cost_per_token = 0.0003
            elif self.model == "gpt-4.1-nano":
                input_cost_per_token = 0.000025
                output_cost_per_token = 0.000075
            
            input_cost = input_tokens * input_cost_per_token
            output_cost = output_tokens * output_cost_per_token
            total_cost = input_cost + output_cost
            
            # 更新結果
            self.results["success"] = True
            self.results["processing_time"] = time.time() - start_time
            self.results["openai_processing_time"] = openai_processing_time
            self.results["tag_count"] = tag_count
            self.results["tags"] = tags
            self.results["estimated_tokens"] = {
                "input": int(input_tokens),
                "output": int(output_tokens),
                "total": int(input_tokens + output_tokens)
            }
            self.results["estimated_cost"] = {
                "input": input_cost,
                "output": output_cost,
                "total": total_cost
            }
            self.results["raw_response"] = tags
            
            return self.results
            
        except Exception as e:
            logger.error(f"測試標籤建議時發生錯誤: {str(e)}")
            self.results["success"] = False
            self.results["processing_time"] = time.time() - start_time
            self.results["error"] = str(e)
            return self.results
            
        finally:
            # 清理資源
            if assistant:
                self.delete_assistant(assistant.id)

def format_tag_preview(tags):
    """格式化標籤預覽"""
    preview = ""
    
    # 預定義的標籤類別
    categories = [
        "人.名人", "人.職業", "人.身份", "人.關聯/關係",
        "事.公共議題", "事.活動", "事.運動", "事.狀態/心態",
        "時.背景年代", "時.特殊時長區間", "時.年度節日", "時.特殊時間點",
        "地.國家", "地.地區", "地.情境場域",
        "物.品牌/組織", "物.產品名稱", "物.道具/物品", "物.素材"
    ]
    
    # 將標籤映射到預定義類別
    mapped_tags = {category: "" for category in categories}
    
    for category, items in tags.items():
        if isinstance(items, list):
            # 處理標籤列表
            for item in items:
                # 嘗試映射到預定義類別
                mapped = False
                for predefined in categories:
                    if category.lower() in predefined.lower() or any(keyword in predefined.lower() for keyword in category.lower().split()):
                        if mapped_tags[predefined]:
                            mapped_tags[predefined] += ", " + item
                        else:
                            mapped_tags[predefined] = item
                        mapped = True
                        break
                
                # 如果無法映射，添加到最接近的類別
                if not mapped:
                    if "人" in category.lower() or "名人" in category.lower() or "職業" in category.lower():
                        if mapped_tags["人.名人"]:
                            mapped_tags["人.名人"] += ", " + item
                        else:
                            mapped_tags["人.名人"] = item
                    elif "事" in category.lower() or "活動" in category.lower() or "狀態" in category.lower():
                        if mapped_tags["事.活動"]:
                            mapped_tags["事.活動"] += ", " + item
                        else:
                            mapped_tags["事.活動"] = item
                    elif "時" in category.lower() or "時間" in category.lower() or "年代" in category.lower():
                        if mapped_tags["時.特殊時間點"]:
                            mapped_tags["時.特殊時間點"] += ", " + item
                        else:
                            mapped_tags["時.特殊時間點"] = item
                    elif "地" in category.lower() or "場所" in category.lower() or "場域" in category.lower():
                        if mapped_tags["地.情境場域"]:
                            mapped_tags["地.情境場域"] += ", " + item
                        else:
                            mapped_tags["地.情境場域"] = item
                    elif "物" in category.lower() or "品牌" in category.lower() or "產品" in category.lower():
                        if mapped_tags["物.品牌/組織"]:
                            mapped_tags["物.品牌/組織"] += ", " + item
                        else:
                            mapped_tags["物.品牌/組織"] = item
        elif isinstance(items, str):
            # 處理單一標籤
            for predefined in categories:
                if category.lower() in predefined.lower():
                    mapped_tags[predefined] = items
                    break
    
    # 生成預覽
    for category in categories:
        preview += f"  {category}: {mapped_tags[category]}\n"
    
    return preview

def save_results(results, test_name):
    """儲存測試結果"""
    # 創建結果目錄
    results_dir = Path(__file__).parent.parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    # 生成檔案名稱
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"openai_gpt41_nano_test_{test_name}_{timestamp}.json"
    
    # 儲存結果
    with open(results_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"測試結果已儲存至: {results_dir / filename}")
    return str(results_dir / filename)

def main():
    """主函數"""
    # 解析命令列參數
    parser = argparse.ArgumentParser(description='測試 OpenAI GPT-4.1-nano 與 WordPress 整合')
    parser.add_argument('--post-id', type=int, required=True, help='WordPress 文章 ID')
    parser.add_argument('--test-name', type=str, default='tag_suggestion', help='測試名稱')
    parser.add_argument('--models', nargs='+', help='要測試的模型列表')
    args = parser.parse_args()
    
    # 載入環境變數
    dotenv_path = Path(__file__).parent.parent.parent / "config" / ".env"
    load_dotenv(dotenv_path, override=True)
    
    # 確認 API 金鑰已設定
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("錯誤: 未設定 OPENAI_API_KEY 環境變數")
        sys.exit(1)
    print(f"成功載入 API 金鑰: {api_key[:5]}...{api_key[-5:]}")
    
    # 檢查 WP 相關環境變數
    if not os.getenv("WP_SITE_URL") or not os.getenv("WP_USERNAME") or not os.getenv("WP_APP_PASSWORD"):
        print("錯誤: 未設定 WordPress API 相關環境變數")
        sys.exit(1)
    
    # 獲取 WordPress 文章內容
    wp_client = WordPressClient()
    post = wp_client.get_post(args.post_id)
    video_description = wp_client.get_post_meta(args.post_id, 'video_description')
    
    # 檢查 video_description
    if not video_description:
        print(f"錯誤: 文章 {args.post_id} 沒有 video_description")
        sys.exit(1)
    
    print(f"成功獲取文章 {args.post_id} 的 video_description，長度: {len(video_description)} 字元")
    
    # 準備測試內容
    content = f"標題: {post['title']['rendered']}\n\n內容描述:\n{video_description}"
    
    # 設定要測試的模型
    models = args.models if args.models else ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4o-mini"]
    
    # 儲存所有測試結果
    all_results = []
    successful_results = []
    
    # 測試每個模型
    for model in models:
        print(f"\n===== 測試 {model} =====")
        tester = OpenAIAssistantTester(model)
        result = tester.test_tag_suggestion(content)
        all_results.append(result)
        
        if result["success"]:
            print(f"✅ 成功 - 總耗時: {result['processing_time']:.2f}秒")
            print(f"  OpenAI 處理耗時: {result['openai_processing_time']:.2f}秒")
            print(f"標籤數量: {result['tag_count']} 個")
            print(f"估算 Token 使用量: {result['estimated_tokens']['total']} (輸入: {result['estimated_tokens']['input']}, 輸出: {result['estimated_tokens']['output']})")
            print("標籤預覽:")
            print(format_tag_preview(result["tags"]))
            successful_results.append(result)
        else:
            print(f"❌ 失敗 - 耗時: {result['processing_time']:.2f}秒, 錯誤: {result['error']}")
    
    # 儲存結果
    results_file = save_results(all_results, args.test_name)
    print(f"\n測試結果已儲存至: {results_file}\n")
    
    # 如果所有測試都失敗，直接退出
    if not successful_results:
        print("所有測試都失敗了")
        sys.exit(1)
    
    # 比較結果
    print("測試結果比較:")
    print(f"總處理時間最快: {min(successful_results, key=lambda x: x['processing_time'])['model']} ({min(successful_results, key=lambda x: x['processing_time'])['processing_time']:.2f}秒)")
    print(f"總處理時間最慢: {max(successful_results, key=lambda x: x['processing_time'])['model']} ({max(successful_results, key=lambda x: x['processing_time'])['processing_time']:.2f}秒)")
    print(f"OpenAI 處理最快: {min(successful_results, key=lambda x: x['openai_processing_time'])['model']} ({min(successful_results, key=lambda x: x['openai_processing_time'])['openai_processing_time']:.2f}秒)")
    print(f"OpenAI 處理最慢: {max(successful_results, key=lambda x: x['openai_processing_time'])['model']} ({max(successful_results, key=lambda x: x['openai_processing_time'])['openai_processing_time']:.2f}秒)")
    print(f"最多標籤: {max(successful_results, key=lambda x: x['tag_count'])['model']} ({max(successful_results, key=lambda x: x['tag_count'])['tag_count']} 個)")
    print(f"最少標籤: {min(successful_results, key=lambda x: x['tag_count'])['model']} ({min(successful_results, key=lambda x: x['tag_count'])['tag_count']} 個)")
    print(f"估算最多 Token: {max(successful_results, key=lambda x: x['estimated_tokens']['total'])['model']} ({max(successful_results, key=lambda x: x['estimated_tokens']['total'])['estimated_tokens']['total']} tokens)")
    print(f"估算最少 Token: {min(successful_results, key=lambda x: x['estimated_tokens']['total'])['model']} ({min(successful_results, key=lambda x: x['estimated_tokens']['total'])['estimated_tokens']['total']} tokens)")
    
    # 計算成功率
    success_rate = len(successful_results) / len(all_results) * 100
    print(f"\n成功率: {len(successful_results)}/{len(all_results)} ({success_rate:.1f}%)\n")
    
    # 顯示成本估算
    print("成本估算 (每百萬 token):")
    for result in successful_results:
        print(f"{result['model']}: ${result['estimated_cost']['total']:.6f} (輸入: ${result['estimated_cost']['input']:.6f}, 輸出: ${result['estimated_cost']['output']:.6f})")

if __name__ == "__main__":
    main()
