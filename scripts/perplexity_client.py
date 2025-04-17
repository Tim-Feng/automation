#!/usr/bin/env python3

import os
import json
import requests
import re
from opencc import OpenCC
from logger import get_workflow_logger

logger = get_workflow_logger('1', 'perplexity_client')

class PerplexityClient:
    def __init__(self):
        """初始化 Perplexity API 客戶端"""
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("Missing PERPLEXITY_API_KEY in environment variables")
        
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.cc = OpenCC('s2tw')  # 建立繁簡轉換器，s2tw 表示從簡體轉換到繁體（台灣標準）
        
        # 編譯正則表達式
        self.chinese_pattern = re.compile(r'([\u4e00-\u9fff])([\da-zA-Z])')  # 中文後面接英文或數字
        self.reverse_pattern = re.compile(r'([\da-zA-Z])([\u4e00-\u9fff])')  # 英文或數字後面接中文

    def add_spaces(self, text: str) -> str:
        """在中文和英文/數字之間添加空格"""
        # 在中文後面加空格
        text = self.chinese_pattern.sub(r'\1 \2', text)
        # 在中文前面加空格
        text = self.reverse_pattern.sub(r'\1 \2', text)
        return text

    def format_response(self, response: str) -> str:
        """格式化回應"""
        # 先進行繁簡轉換
        response = self.cc.convert(response)
        
        # 移除 markdown 粗體標記
        response = response.replace('**', '')
        
        # 處理中英文和數字之間的空格
        response = self.add_spaces(response)
        
        # 將內容轉換為古騰堡格式
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        formatted_content = []
        
        for p in paragraphs:
            formatted_content.append(f"<!-- wp:paragraph -->\n<p>{p}</p>\n<!-- /wp:paragraph -->")
        
        return '\n\n'.join(formatted_content)

    def search(self, title: str) -> str:
        """使用影片標題進行搜索並返回格式化的內容（含指數退避重試）"""
        import time
        prompt = f"""請想像這是一個專業廣告影片平台的作品介紹，需要吸引觀眾又傳達重要資訊。所有資訊必須準確且有來源依據，並使用流暢的敘事方式，描述以下這支廣告影片：

{title}

連結和來源：
 - 文章中不要出現引用來源
 - 所有的引用來源都請放在段落結束後，以「參考來源」開始一個新段落，並將每個來源轉換為可點擊的連結，連結名稱為網站名稱，例如 <a href="https://example.com">網站名稱</a>。

寫作風格要求：
1. 基本格式：
   - 使用正體中文台灣用語撰寫
   - 中文與英文之間加入半形空白
   - 中文與阿拉伯數字之間加入半形空白
   - 不要使用粗體字加強，直接使用純文字

2. 譯名標注規則（重要！）：
   A. 日文人名：
      - 譯名和漢字相同時直接寫：「新垣結衣」
      - 譯名和漢字不同時標註原文：「淺田政志（浅田政志）」
      - 有假名時標註假名：「森田輝（森田ひかる）」
   B. 英文人名：
      - 中文譯名標註英文：「羅溫·艾金森（Rowan Atkinson）」
   C. 影視作品：
      - 必須使用台灣官方翻譯並標注英文：「《傲慢與偏見》（Pride and Prejudice）」「《怪奇物語：第四季》（Stranger Things: Season 4）」
      - 如果作品原名為日文或韓文，則可標示「日文/韓文+英文」：「《進擊的巨人》（進撃の巨人 / Attack on Titan）」「《葬送的芙莉蓮》（葬送のフリーレン / Frieren: Beyond Journey's End）」「《魷魚遊戲》（오징어 게임 / Squid Game）」

3. 內容結構：
   - 內容需要像在說一個吸引人的故事
   - 避免使用條列式
   - 以段落方式描述影片背景、目的、主題和重點內容
   - 如果有幕後製作團隊和特色也請列出
   - 直接以內容描述開始，不需要標題

嚴格檢查：
回覆前再次確認所有資訊與格式是否符合以上規範，尤其需要避免使用中國用語和翻譯。"""

        retry_intervals = [5, 10, 20, 40, 80]  # 秒，指數退避
        last_exception = None
        for attempt, wait_time in enumerate(retry_intervals, 1):
            try:
                payload = {
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                if response.status_code == 200:
                    response_data = response.json()
                    formatted_content = self.format_response(response_data['choices'][0]['message']['content'])
                    logger.debug(f"成功獲取並格式化「{title}」的相關資訊")
                    return formatted_content
                else:
                    logger.error(f"[重試 {attempt}/5] Perplexity API 請求失敗: {response.status_code}")
                    logger.error(f"[重試 {attempt}/5] 錯誤訊息: {response.text}")
            except Exception as e:
                logger.error(f"[重試 {attempt}/5] 搜索過程發生錯誤: {str(e)}")
                last_exception = e
            if attempt < len(retry_intervals):
                logger.info(f"{wait_time} 秒後重試...")
                time.sleep(wait_time)
        # 全部重試失敗，寫入 failed_jobs.json
        self._record_failed_job(title, last_exception)
        return None

    def _record_failed_job(self, title, exception):
        """將失敗的搜尋任務記錄到 failed_jobs.json"""
        import datetime
        failed_job = {
            "title": title,
            "error": str(exception) if exception else "Unknown error",
            "timestamp": datetime.datetime.now().isoformat()
        }
        failed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../logs/failed_jobs.json')
        try:
            if os.path.exists(failed_path):
                with open(failed_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
            data.append(failed_job)
            with open(failed_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.error(f"已寫入失敗任務至 failed_jobs.json: {title}")
        except Exception as e:
            logger.error(f"寫入 failed_jobs.json 時發生錯誤: {str(e)}")


def main():
    """測試用主函數"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python perplexity_client.py <video_title>")
        sys.exit(1)

    try:
        client = PerplexityClient()
        result = client.search(sys.argv[1])
        if result:
            print(result)
        else:
            print("搜索失敗")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
