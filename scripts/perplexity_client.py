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
        
        # 載入 prompt 模板
        self.load_prompt_template()

    def load_prompt_template(self):
        """載入並組合 prompt 模板"""
        prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../prompts/perplexity/content_generation.json')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.prompt_config = json.load(f)
                logger.debug("成功載入 prompt 設定")
                
        except Exception as e:
            logger.error(f"載入 prompt 模板時發生錯誤: {str(e)}")
            raise

    def _build_prompt(self, title: str) -> str:
        """根據設定建立完整的 prompt
        
        Args:
            title: 影片標題
            
        Returns:
            str: 完整的 prompt 字串
        """
        data = self.prompt_config
        prompt = []
        
        # 1. 添加開場白
        prompt.append(data['intro']['content'].format(title=title))
        prompt.append("")  # 空行
        
        rules = data['rules']
        
        # 2. 添加規則
        # 連結和來源規則
        source = rules['source']
        prompt.append(f"{source['title']}：")
        for item in source['items']:
            prompt.append(f"- {item}")
        prompt.append(f"例如：{source['example']}")
        prompt.append("")
        
        # 寫作風格規則
        style = rules['writing_style']
        prompt.append(f"{style['title']}：")
        for i, item in enumerate(style['items'], 1):
            prompt.append(f"{i}. {item}")
        prompt.append("")
        
        # 譯名標注規則
        name_format = rules['name_format']
        prompt.append(f"{name_format['title']}（重要！）：")
        
        # 日文人名
        jp = name_format['japanese_name']
        prompt.append(f"A. {jp['title']}：")
        for item in jp['items']:
            rule_line = "   - {}：「{}」".format(item['rule'], item['example'])
            prompt.append(rule_line)
        prompt.append("")
        
        # 外國人名
        foreign = name_format['foreign_name']
        prompt.append(f"B. {foreign['title']}：")
        for rule_set in foreign['rules']:
            prompt.append(f"   - {rule_set['type']}：{rule_set['rule']}")
            examples = ["「{}」".format(ex) for ex in rule_set['examples']]
            prompt.append("     例如：" + "、".join(examples))
            prompt.append("")
        
        # 品牌名稱
        brand = name_format['brand_name']
        prompt.append(f"C. {brand['title']}：")
        for rule_set in brand['rules']:
            prompt.append(f"   - {rule_set['type']}：{rule_set['rule']}")
            examples = ["「{}」".format(ex) for ex in rule_set['examples']]
            prompt.append("     例如：" + "、".join(examples))
            prompt.append("")
        
        # 影視作品規則
        work = rules['work_format']
        prompt.append(f"D. {work['title']}：")
        for rule in work['rules']:
            prompt.append(f"   - {rule['type']}：{rule['rule']}")
            examples = ["「{}」".format(ex) for ex in rule['examples']]
            prompt.append("     例如：" + "、".join(examples))
            prompt.append("")
        
        # 內容結構規則
        structure = rules['content_structure']
        prompt.append(f"{structure['title']}：")
        for item in structure['items']:
            prompt.append(f"- {item}")
        prompt.append("")
        
        # 嚴格檢查
        final = rules['final_check']
        prompt.append(f"{final['title']}：")
        prompt.append(final['content'])
        
        # 3. 添加範例
        if data.get('examples'):
            prompt.append("")  # 添加空行
            prompt.append("實際範例參考：")
            for example in data['examples']:
                title_line = "輸入標題：" + example['input']
                content_line = "輸出內容：\n" + example['output']
                prompt.append(title_line)
                prompt.append(content_line)
        
        return "\n".join(prompt)

    def add_spaces(self, text: str) -> str:
        """在中文和英文/數字之間添加空格"""
        # 在中文後面加空格
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', text)
        # 在中文前面加空格
        text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', text)
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
            formatted_content.append("<!-- wp:paragraph -->\n<p>{}</p>\n<!-- /wp:paragraph -->".format(p))
        
        return '\n\n'.join(formatted_content)

    def search(self, title: str) -> str:
        """使用影片標題進行搜索並返回格式化的內容（含指數退避重試）"""
        import time
        
        # 使用新的方法生成 prompt
        prompt = self._build_prompt(title)

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

    def generate_content(self, title: str, gemini_content: str = None) -> str:
        """生成廣告影片描述內容
        
        Args:
            title: 影片標題
            gemini_content: Gemini 分析的內容（可選）
            
        Returns:
            str: 生成的內容
        """
        try:
            # 生成內容
            content = self._generate_raw_content(title)
            
            # 驗證內容
            is_valid, corrected_content, errors = self.validator.validate_content(
                content, 
                gemini_content
            )
            
            if not is_valid:
                error_message = "內容驗證發現問題：\n{}".format('\n'.join(errors))
                self.logger.warning(error_message)
                # TODO: 實作自動修正或人工審核流程
                return content
            
            return corrected_content
            
        except Exception as e:
            self.logger.error(f"生成內容時發生錯誤: {str(e)}")
            raise

    def _generate_raw_content(self, title: str) -> str:
        """使用 Perplexity 生成原始內容"""
        # ... existing generate_content code ...

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
