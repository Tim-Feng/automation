#!/usr/bin/env python3
# extract_script_data.py

import os
import sys
import json
import requests
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from requests.auth import HTTPBasicAuth

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s \u2139\uFE0F [Stage-1] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/script_extraction.log', encoding='utf-8')
    ]
)

logger = logging.getLogger('script_extractor')

class ScriptExtractor:
    """從 WordPress 文章中擷取腳本資料（內文、影片描述、字幕）"""

    def __init__(self):
        """初始化 ScriptExtractor"""
        self.site_url = os.getenv("WP_SITE_URL")
        if not self.site_url:
            self.site_url = "https://referee.ad"  # 預設網址
        self.site_url = self.site_url.rstrip('/')
        
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.username = os.getenv("WP_USERNAME")
        self.password = os.getenv("WP_APP_PASSWORD")
        
        if not self.username or not self.password:
            logger.warning("未設定 WordPress 認證資訊，將使用未認證的請求")
            self.auth = None
        else:
            self.auth = HTTPBasicAuth(self.username, self.password)
            
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # 不再建立輸出目錄，直接返回資料
        pass

    def get_post(self, post_id: int) -> Optional[Dict]:
        """取得文章資料
        
        Args:
            post_id: 文章 ID
            
        Returns:
            Dict: 文章資料或 None（如果取得失敗）
        """
        endpoint = f"{self.api_base}/video/{post_id}"
        
        try:
            response = requests.get(endpoint, auth=self.auth, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"取得文章失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            return response.json()
            
        except Exception as e:
            logger.error(f"取得文章時發生錯誤: {str(e)}")
            return None

    def extract_content(self, post_data: Dict) -> str:
        """從文章資料中擷取內文
        
        Args:
            post_data: 文章資料
            
        Returns:
            str: 文章內文（已移除 HTML 標籤）
        """
        content = post_data.get('content', {}).get('rendered', '')
        
        # 移除 HTML 標籤
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除多餘的空白和換行
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return content

    def extract_video_description(self, post_data: Dict) -> str:
        """從文章資料中擷取影片描述
        
        Args:
            post_data: 文章資料
            
        Returns:
            str: 影片描述（已移除 WordPress 標籤）
        """
        meta = post_data.get('meta', {})
        description = meta.get('video_description', '')
        
        # 移除 WordPress Gutenberg 區塊標籤
        description = re.sub(r'<!-- wp:[^>]+-->', '', description)
        description = re.sub(r'<!-- /wp:[^>]+-->', '', description)
        
        # 移除 HTML 標籤
        description = re.sub(r'<[^>]+>', '', description)
        
        # 移除多餘的空白和換行
        description = re.sub(r'\n\s*\n', '\n\n', description)
        description = description.strip()
        
        return description

    def get_subtitle_url(self, post_data: Dict) -> Optional[str]:
        """從文章資料中擷取字幕 URL
        
        Args:
            post_data: 文章資料
            
        Returns:
            str: 字幕 URL 或 None（如果沒有字幕）
        """
        meta = post_data.get('meta', {})
        text_tracks = meta.get('text_tracks', {})
        
        sources = text_tracks.get('sources', [])
        if sources and isinstance(sources, list) and len(sources) > 0:
            return sources[0]
        
        return None

    def download_subtitle(self, url: str) -> Optional[str]:
        """下載字幕檔案
        
        Args:
            url: 字幕 URL
            
        Returns:
            str: 字幕內容或 None（如果下載失敗）
        """
        try:
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"下載字幕失敗 - Status: {response.status_code}")
                return None
                
            return response.text
            
        except Exception as e:
            logger.error(f"下載字幕時發生錯誤: {str(e)}")
            return None

    def parse_vtt(self, vtt_content: str) -> str:
        """解析 VTT 字幕檔案，提取純文字內容
        
        Args:
            vtt_content: VTT 字幕內容
            
        Returns:
            str: 純文字字幕內容
        """
        # 移除 WEBVTT 標頭和時間碼
        lines = vtt_content.split('\n')
        text_lines = []
        
        for line in lines:
            # 跳過空行、WEBVTT 標頭和時間碼
            if not line.strip() or line.startswith('WEBVTT') or re.match(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', line):
                continue
                
            # 跳過只包含數字的行（通常是字幕編號）
            if re.match(r'^\d+$', line.strip()):
                continue
                
            text_lines.append(line.strip())
            
        return '\n'.join(text_lines)

    def extract_script_data(self, post_id: int) -> Tuple[bool, Dict]:
        """從文章中擷取腳本資料
        
        Args:
            post_id: 文章 ID
            
        Returns:
            Tuple[bool, Dict]: (成功與否, 腳本資料)
        """
        # 取得文章資料
        post_data = self.get_post(post_id)
        if not post_data:
            return False, {}
            
        # 擷取內文
        content = self.extract_content(post_data)
        logger.info(f"成功擷取文章內文，長度: {len(content)} 字元")
        
        # 擷取影片描述
        video_description = self.extract_video_description(post_data)
        if video_description:
            logger.info(f"成功擷取影片描述，長度: {len(video_description)} 字元")
        else:
            logger.warning("文章沒有影片描述")
            
        # 擷取字幕
        subtitle_text = ""
        subtitle_url = self.get_subtitle_url(post_data)
        
        if subtitle_url:
            logger.info(f"找到字幕 URL: {subtitle_url}")
            subtitle_content = self.download_subtitle(subtitle_url)
            
            if subtitle_content:
                subtitle_text = self.parse_vtt(subtitle_content)
                logger.info(f"成功解析字幕，長度: {len(subtitle_text)} 字元")
            else:
                logger.warning("無法下載字幕")
        else:
            logger.warning("文章沒有字幕")
            
        # 建立腳本資料
        script_data = {
            'post_id': post_id,
            'title': post_data.get('title', {}).get('rendered', ''),
            'content': content,
            'video_description': video_description,
            'subtitle': subtitle_text,
            'video_url': post_data.get('meta', {}).get('video_url', '')
        }
        
        # 儲存腳本資料
        self.save_script_data(post_id, script_data)
        
        return True, script_data

    def save_script_data(self, post_id: int, script_data: Dict) -> Dict:
        """處理腳本資料，不再儲存檔案，而是直接返回資料
        
        Args:
            post_id: 文章 ID
            script_data: 腳本資料
            
        Returns:
            Dict: 腳本資料
        """
        # 記錄腳本資料已處理完成
        logger.info(f"文章 {post_id} 的腳本資料已處理完成，標題: {script_data['title']}")
        
        # 直接返回資料，不儲存檔案
        return script_data


def main():
    if len(sys.argv) < 2:
        print("用法: python extract_script_data.py <post_id>")
        return
        
    try:
        post_id = int(sys.argv[1])
    except ValueError:
        print(f"錯誤: 文章 ID 必須是數字，收到的是 '{sys.argv[1]}'")
        return
        
    extractor = ScriptExtractor()
    success, script_data = extractor.extract_script_data(post_id)
    
    if success:
        # 直接輸出腳本資料，不儲存檔案
        print(f"成功從文章 {post_id} 擷取腳本資料")
        print(json.dumps(script_data, ensure_ascii=False, indent=2))
    else:
        print(f"從文章 {post_id} 擷取腳本資料失敗")


if __name__ == "__main__":
    main()
