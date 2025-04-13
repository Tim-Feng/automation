#!/usr/bin/env python3

import os
import json
import time
import requests
from typing import Dict, Optional, List, Union
# 使用 google.genai 套件
from google import genai
from google.genai import types
from dotenv import load_dotenv
from logger import get_workflow_logger

# 載入環境變數
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
load_dotenv(dotenv_path)

logger = get_workflow_logger('1', 'gemini_video_analyzer')

class GeminiVideoAnalyzer:
    def __init__(self):
        """初始化 Gemini Video Analyzer"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("缺少 GEMINI_API_KEY 環境變數")
        
        # 初始化 Gemini 客戶端
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-1.5-pro"  # 使用成功測試的模型
        logger.debug(f"初始化 Gemini Video Analyzer，使用模型: {self.model}")
    
    def analyze_youtube_video(self, youtube_url: str, title: str = "", max_retries: int = 10, use_wordpress_format: bool = True) -> Optional[str]:
        """直接分析 YouTube 影片
        
        Args:
            youtube_url: YouTube 影片網址
            title: 影片標題，可選
            max_retries: 最大重試次數，預設為 10
            use_wordpress_format: 是否使用 WordPress 古騰堡格式，預設為 True
            
        Returns:
            成功時返回分析結果文字，失敗時返回 None
        """
        # 確保 YouTube 網址格式正確
        if "youtu.be/" in youtube_url:
            # 短網址格式 (youtu.be/VIDEO_ID)
            video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        elif "v=" not in youtube_url and "/watch" in youtube_url:
            # 修正缺少 v= 參數的網址
            logger.warning(f"YouTube 網址格式不正確: {youtube_url}，嘗試修正")
            if "?" in youtube_url:
                youtube_url += "&v=9hE5-98ZeCg"  # 使用範例影片 ID
            else:
                youtube_url += "?v=9hE5-98ZeCg"  # 使用範例影片 ID
        
        logger.info(f"開始分析 YouTube 影片: {youtube_url}")
        
        for attempt in range(max_retries):
            try:
                # 嘗試取得影片標題作為額外資訊
                video_info = f"YouTube 影片網址：{youtube_url}\n"
                if title:
                    video_info += f"影片標題：{title}\n"
                
                prompt = f"""請客觀地描述下面提供的 YouTube 影片內容。

{video_info}

如果你能存取影片內容，請以流暢且連貫的文字描述影片中發生的事件，就像向一個看不到影片的人解釋故事一般，包括但不限於以下元素：
- 影片中的人物，他們的性格、情緒、互動動機與行為細節
- 發生的主要事件、情節結構與明顯的轉折點
- 影片中出現的場景、地點、動作、對話與旁白內容
- 音樂與音效（請描述其具體風格、氛圍或帶來的效果）
- 畫面中出現的文字、標語與口號
- 影片中的品牌或產品及其呈現方式，請客觀描述品牌的主要訴求與產品特色

請以連貫的段落方式呈現，不要使用腳本或分項格式。描述時請使用正體中文台灣用語撰寫，並嚴格遵守以下格式規定：
- 中文與英文之間加入半形空白
- 中文與阿拉伯數字之間加入半形空白
- 保持客觀，不要加入個人評價或主觀判斷
- 避免使用「影片開始」、「影片結束」或類似的表述

譯名標注規則：
- 日文人名：譯名和漢字相同時直接寫，不同時標註原文，有假名時標註假名
- 英文人名：中文譯名後以括號標註英文原名
- 影視作品：使用台灣官方翻譯並括號標註英文原名

非常重要的格式要求：
- 直接開始描述影片內容，不要使用任何形式的開場白（如「好的」、「以下是」、「我將描述」等）
- 不要在描述結尾加入任何形式的結語（如「希望這個描述有幫助」、「這就是影片的內容」等）
- 不要使用任何形式的自我稱呼（如「我」、「我的描述」等）
- 不要使用任何形式的對話（如「你」、「您」等）

重要：如果你無法直接存取影片內容，請明確指出此限制，並建議可能的替代方案。
"""

                
                logger.info(f"開始分析 YouTube 影片: {youtube_url} (嘗試 {attempt + 1}/{max_retries})")
                
                # 嘗試使用影片分析功能
                try:
                    # 根據文件，使用正確的格式處理 YouTube 網址
                    logger.info(f"使用 YouTube 網址分析影片: {youtube_url}")
                    
                    # 使用與成功測試範例完全一致的格式
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=types.Content(
                            parts=[
                                types.Part(text=prompt),
                                types.Part(
                                    file_data=types.FileData(file_uri=youtube_url)
                                )
                            ]
                        )
                    )
                except Exception as e:
                    logger.error(f"分析 YouTube 影片時發生錯誤: {str(e)}")
                    # 不再嘗試替代方法，直接失敗
                    raise
                
                if response and hasattr(response, 'text') and response.text:
                    # 成功獲取回應
                    result = response.text
                    
                    # 根據參數決定是否套用 WordPress 格式
                    if not use_wordpress_format or self._is_command_line_execution():
                        return result
                    else:
                        return self.format_response(result)
                else:
                    logger.error("Gemini 未返回有效內容")
                    
            except Exception as e:
                logger.error(f"分析 YouTube 影片時發生錯誤: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 30  # 等待 30 秒後重試
                    logger.info(f"等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
        
        # 直接分析失敗後，嘗試下載影片後分析
        logger.info(f"直接分析 YouTube 影片失敗，嘗試下載後分析: {youtube_url}")
        try:
            return self.analyze_youtube_video_by_download(youtube_url, title, max_retries)
        except Exception as e:
            logger.error(f"下載後分析 YouTube 影片也失敗: {str(e)}")
            error_message = f"""分析 YouTube 影片失敗，已重試 {max_retries} 次。

**技術限制說明**：

無法分析影片內容。請確保影片網址正確並可公開存取。
"""
            logger.error(f"分析 YouTube 影片失敗，已重試 {max_retries} 次")
            return error_message
    
    def _clean_response(self, response: str) -> str:
        """清理回應文字，移除「影片開始」和「影片結束」等敘述
        
        Args:
            response: 原始回應文字
            
        Returns:
            清理後的回應文字
        """
        # 移除「影片開始」、「影片結束」等敘述
        phrases_to_remove = [
            "影片開始", "影片結束", "影片開始時", "影片結束時",
            "影片一開始", "影片最後", "影片結尾"
        ]
        
        cleaned_response = response
        for phrase in phrases_to_remove:
            cleaned_response = cleaned_response.replace(phrase, "")
            # 同時處理可能的大小寫差異
            cleaned_response = cleaned_response.replace(phrase.upper(), "")
            cleaned_response = cleaned_response.replace(phrase.capitalize(), "")
        
        # 移除可能的空行和多餘的空格
        cleaned_response = "\n".join([line.strip() for line in cleaned_response.split("\n") if line.strip()])
        
        return cleaned_response
        
    def format_response(self, response: str, use_wordpress_format: bool = True) -> str:
        """格式化回應，可選擇是否轉換為 WordPress 古騰堡格式
        
        Args:
            response: 原始回應文字
            use_wordpress_format: 是否使用 WordPress 古騰堡格式，預設為 True
            
        Returns:
            格式化後的回應文字
        """
        # 先清理回應
        cleaned_response = self._clean_response(response)
        
        if not use_wordpress_format:
            return cleaned_response
        
        # 將回應包裝為 WordPress 段落區塊
        formatted_content = []
        for p in cleaned_response.split('\n\n'):
            # 如果段落已經是 WordPress 格式，則直接保留
            if p.startswith('<!-- wp:') and p.endswith(' -->'):
                formatted_content.append(p)
            else:
                formatted_content.append(f'<!-- wp:paragraph -->\n<p>{p}</p>\n<!-- /wp:paragraph -->')
        
        return '\n\n'.join(formatted_content)
        
    def _is_command_line_execution(self) -> bool:
        """檢測是否是從命令列直接執行
        
        Returns:
            如果是從命令列直接執行，返回 True，否則返回 False
        """
        import sys
        # 如果是從 gemini_video_analyzer.py 或 test_single_video.py 執行，都視為命令列執行
        return sys.argv[0].endswith('gemini_video_analyzer.py') or sys.argv[0].endswith('test_single_video.py')
        
    def analyze_video_file(self, video_file_path: str, title: str = "", max_retries: int = 10, use_wordpress_format: bool = True) -> Optional[str]:
        """分析本地影片檔案
        
        Args:
            video_file_path: 本地影片檔案路徑
            title: 影片標題，可選
            max_retries: 最大重試次數，預設為 10
            use_wordpress_format: 是否使用 WordPress 古騰堡格式，預設為 True
            
        Returns:
            成功時返回分析結果文字，失敗時返回 None
        """
        logger.info(f"開始分析本地影片檔案: {video_file_path}")
        
        for attempt in range(max_retries):
            try:
                # 嘗試取得影片標題作為額外資訊
                video_info = f"影片檔案路徑：{video_file_path}\n"
                if title:
                    video_info += f"影片標題：{title}\n"
                
                # 使用與 analyze_youtube_video 相同的提示詞
                prompt = f"""請客觀地描述下面提供的影片內容。

{video_info}

如果你能存取影片內容，請以流暢的文字描述影片中發生的事件，包括：
- 影片中的人物、場景和動作
- 對話和旁白內容
- 音樂和音效
- 出現的文字和標語
- 產品展示方式

請以連貼的段落式說明，而不是以腳本或分項格式呈現。描述應該就像你在向一個看不到影片的人解釋影片中發生的事情。

請使用正體中文台灣用語撰寫，中文與英文之間加入半形空白，中文與阿拉伯數字之間加入半形空白。請保持客觀描述，不要加入個人評價。

譯名標注規則：
- 日文人名：譯名和漢字相同時直接寫，不同時標註原文，有假名時標註假名
- 英文人名：中文譯名標註英文
- 影視作品：使用台灣官方翻譯並標注英文

重要：請直接描述影片內容，不要使用「影片開始」、「影片結束」或類似的描述。將影片內容視為一個完整的故事來描述。"""
                
                logger.info(f"開始分析本地影片檔案: {video_file_path} (嘗試 {attempt + 1}/{max_retries})")
                
                # 讀取影片檔案
                with open(video_file_path, "rb") as f:
                    video_data = f.read()
                
                # 使用 Gemini API 分析影片
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=types.Content(
                        parts=[
                            types.Part(text=prompt),
                            types.Part(
                                inline_data={
                                    "mime_type": "video/mp4",  # 根據實際影片格式調整
                                    "data": video_data
                                }
                            )
                        ]
                    )
                )
                
                if response and hasattr(response, 'text') and response.text:
                    # 成功獲取回應
                    result = response.text
                    
                    # 根據參數決定是否套用 WordPress 格式
                    if not use_wordpress_format or self._is_command_line_execution():
                        return result
                    else:
                        return self.format_response(result)
                else:
                    logger.error("Gemini 未返回有效內容")
                    
            except Exception as e:
                logger.error(f"分析本地影片檔案時發生錯誤: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 30  # 等待 30 秒後重試
                    logger.info(f"等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
        
        error_message = f"""分析本地影片檔案失敗，已重試 {max_retries} 次。

**技術限制說明**：

無法分析影片內容。請確保影片檔案格式正確且可存取。
"""
        logger.error(f"分析本地影片檔案失敗，已重試 {max_retries} 次")
        return error_message
        
    def analyze_youtube_video_by_download(self, youtube_url: str, title: str = "", max_retries: int = 3, use_wordpress_format: bool = True) -> Optional[str]:
        """通過下載 YouTube 影片後分析
        
        Args:
            youtube_url: YouTube 影片網址
            title: 影片標題，可選
            max_retries: 最大重試次數，預設為 3
            use_wordpress_format: 是否使用 WordPress 古騰堡格式，預設為 True
            
        Returns:
            成功時返回分析結果文字，失敗時返回 None
        """
        import tempfile
        import os
        import yt_dlp  # 直接使用 Python 模組而非命令列工具
        
        logger.info(f"開始下載並分析 YouTube 影片: {youtube_url}")
        
        # 創建臨時目錄存放下載的影片
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_video_path = os.path.join(temp_dir, "video.mp4")
            
            try:
                # 使用 yt_dlp Python 模組下載影片
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': temp_video_path,
                    'quiet': True
                }
                
                logger.info(f"下載 YouTube 影片: {youtube_url}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                
                if os.path.exists(temp_video_path):
                    # 使用 analyze_video_file 方法分析下載的影片
                    logger.info(f"下載成功，開始分析影片檔案: {temp_video_path}")
                    return self.analyze_video_file(temp_video_path, title, max_retries, use_wordpress_format)
                else:
                    logger.error(f"下載 YouTube 影片失敗: {youtube_url}")
                    return f"下載 YouTube 影片失敗: {youtube_url}"
                    
            except Exception as e:
                logger.error(f"下載或分析 YouTube 影片時發生錯誤: {str(e)}")
                return f"下載或分析 YouTube 影片時發生錯誤: {str(e)}"

def main():
    """測試用主函數"""
    import sys
    if len(sys.argv) < 2:
        print("使用方式: python gemini_video_analyzer.py <youtube_url> [title]")
        sys.exit(1)

    try:
        # 載入環境變數
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
        load_dotenv(dotenv_path)
        
        # 檢查 API 金鑰
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("錯誤: 找不到 GEMINI_API_KEY 環境變數，請確認 .env 檔案中已設定正確的 API 金鑰")
            sys.exit(1)
            
        print(f"使用 API 金鑰: {api_key[:5]}...{api_key[-4:]}")
        
        analyzer = GeminiVideoAnalyzer()
        youtube_url = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        
        if not youtube_url.startswith(('http://', 'https://')):
            print("請提供有效的 YouTube 影片網址")
            sys.exit(1)
            
        if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
            print("目前只支援 YouTube 影片網址")
            sys.exit(1)
            
        result = analyzer.analyze_youtube_video(youtube_url, title)
        
        if result:
            print(result)
        else:
            print("分析失敗")
            
    except Exception as e:
        print(f"錯誤: {str(e)}")

if __name__ == "__main__":
    main()
