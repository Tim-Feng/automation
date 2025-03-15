#!/usr/bin/env python3

import os
import json
import requests
import re
import pathlib
from typing import Optional, Dict, Any, List
from opencc import OpenCC
from google.generativeai import GenerativeModel
import google.generativeai as genai
from logger import get_workflow_logger
from dotenv import load_dotenv

# 載入環境變數
config_path = os.path.join(pathlib.Path(__file__).parent.parent, 'config', '.env')
load_dotenv(config_path)

logger = get_workflow_logger('1', 'gemini_file_client')

class GeminiFileClient:
    def __init__(self):
        """初始化 Google Gemini File API 客戶端"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("缺少環境變數 GEMINI_API_KEY")
        
        # 初始化 Gemini API
        genai.configure(api_key=self.api_key)
        
        # 設定模型
        self.model = "gemini-2.0-flash"
        self.client = genai
        
        # 建立繁簡轉換器，s2tw 表示從簡體轉換到繁體（台灣標準）
        self.cc = OpenCC('s2tw')
        
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
        """格式化 Gemini API 的回應內容
        
        Args:
            response: Gemini API 的原始回應文本
            
        Returns:
            經過格式化的文本，包含：
            1. 繁簡轉換
            2. 清理 markdown 標記
            3. 修正中英文空格
            4. 段落格式整理
        """
        # 繁簡轉換
        response = self.cc.convert(response)
        
        # 移除 markdown 粗體標記
        response = response.replace('**', '')
        
        # 處理中英文和數字之間的空格
        response = self.add_spaces(response)
        
        # 清理多餘的空白行並保持段落結構
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        
        # 使用空行分隔段落
        return '\n\n'.join(paragraphs)

    def analyze_video(self, youtube_url: str, max_retries: int = 3) -> Optional[str]:
        """分析 YouTube 影片並返回詳細描述
        
        Args:
            youtube_url: YouTube 影片連結
            max_retries: 最大重試次數
            
        Returns:
            格式化的影片分析內容，如果失敗則返回 None
        """
        prompt = """請分析這個 YouTube 影片的視覺和音訊內容，提供詳細的描述。
        
分析要點：
1. 影片的主要視覺元素和場景
2. 出現的人物、產品或品牌
3. 音樂風格和語音內容
4. 整體氛圍和情感表達
5. 廣告訴求和目標受眾

回應格式要求：
- 使用正體中文台灣用語撰寫
- 中文與英文之間加入半形空白
- 中文與阿拉伯數字之間加入半形空白
- 以流暢的敘事方式描述，避免使用條列式
- 內容需要像在說一個吸引人的故事

請提供全面且詳細的分析，讓讀者即使沒有看過影片也能理解其內容和訴求。"""

        for attempt in range(max_retries):
            try:
                # 建立生成式模型
                model = GenerativeModel(self.model)
                
                # 發送請求
                response = model.generate_content(
                    contents=[
                        {"text": prompt},
                        {"file_data": {"file_uri": youtube_url}}
                    ]
                )
                
                # 檢查回應
                if not response or not hasattr(response, 'text'):
                    logger.error(f"Gemini API 回應無效（嘗試 {attempt + 1}/{max_retries}）")
                    continue
                
                # 格式化回應
                formatted_content = self.format_response(response.text)
                logger.debug(f"成功分析影片：{youtube_url}")
                return formatted_content
                
            except Exception as e:
                logger.error(f"影片分析過程發生錯誤（嘗試 {attempt + 1}/{max_retries}）: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"5 秒後重試...")
                    import time
                    time.sleep(5)
                else:
                    logger.error(f"已達最大重試次數，分析失敗")
                    return None
        
        return None

def main():
    """測試用主函數"""
    import sys
    if len(sys.argv) < 2:
        print("用法: python gemini_file_client.py <youtube_url>")
        sys.exit(1)

    try:
        # 確認 API 金鑰是否存在
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"錯誤: 環境變數 GEMINI_API_KEY 未設定或無法讀取，請確認 .env 檔案路徑: {config_path}")
            sys.exit(1)
            
        client = GeminiFileClient()
        result = client.analyze_video(sys.argv[1])
        if result:
            print(result)
        else:
            print("影片分析失敗")
    except Exception as e:
        print(f"錯誤: {str(e)}")

if __name__ == "__main__":
    main()
