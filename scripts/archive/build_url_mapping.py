#!/usr/bin/env python3
# build_url_mapping.py
#
# 歸檔說明：
# 這是一個建立自定義 slug 到文章 ID 映射表的腳本。
# 創建日期：2025-04-09 之前
# 作者：Cascade
#
# 用途：
# 該腳本通過 WordPress API 獲取所有文章，並從每篇文章的 URL 中提取自定義 slug，
# 建立自定義 slug 到文章 ID 的映射表，並將其保存到 custom_slug_mapping.json 文件。
# 這個映射表用於從 WordPress URL 中提取文章 ID，以便更新 YouTube 連結。
#
# 歸檔原因：
# 我們已經將工作流程修改為在文章創建時直接記錄 ID 到 Google Sheets 的 I 欄位，
# 因此不再需要使用映射表來查找文章 ID。
# 保留此腳本作為參考，以便將來可能需要類似的功能。

import os
import re
import json
import requests
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from logger import get_workflow_logger
from wordpress_api import WordPressAPI

# 設定日誌
logger = get_workflow_logger('1', 'build_url_mapping')

def extract_custom_slug_from_url(url: str) -> Optional[str]:
    """從 WordPress URL 中提取自定義 slug
    
    Args:
        url: WordPress 文章 URL
        
    Returns:
        str: 自定義 slug，如果無法提取則返回 None
    """
    try:
        # 嘗試匹配已發布文章 URL (如 https://referee.ad/video/YRdG5pJaDz/)
        match = re.search(r'/video/([a-zA-Z0-9]+)/?', url)
        if match:
            return match.group(1)
            
        logger.warning(f"無法從 URL 提取自定義 slug: {url}")
        return None
        
    except Exception as e:
        logger.error(f"提取自定義 slug 時發生錯誤: {str(e)}")
        return None

def get_all_posts(wp: WordPressAPI) -> List[Dict]:
    """獲取所有文章
    
    Args:
        wp: WordPressAPI 實例
        
    Returns:
        List[Dict]: 文章列表
    """
    all_posts = []
    page = 1
    per_page = 100
    total_pages = 1
    
    logger.info("開始獲取所有文章...")
    
    while page <= total_pages:
        logger.info(f"獲取第 {page} 頁文章...")
        
        # 構建 API 端點
        endpoint = f"{wp.api_base}/video"
        params = {
            'page': page,
            'per_page': per_page,
            '_fields': 'id,link,slug,title'  # 只獲取需要的欄位，減少數據量
        }
        
        # 發送請求
        response = requests.get(endpoint, auth=wp.auth, params=params)
        
        if response.status_code != 200:
            logger.error(f"獲取文章列表失敗 - Status: {response.status_code}, Response: {response.text}")
            break
            
        # 解析回應
        posts = response.json()
        logger.info(f"獲取到 {len(posts)} 篇文章")
        all_posts.extend(posts)
        
        # 更新總頁數
        if page == 1 and 'X-WP-TotalPages' in response.headers:
            total_pages = int(response.headers['X-WP-TotalPages'])
            logger.info(f"總共有 {total_pages} 頁文章")
            
        page += 1
        
    logger.info(f"共獲取到 {len(all_posts)} 篇文章")
    return all_posts

def build_custom_slug_to_id_mapping(posts: List[Dict]) -> Dict[str, int]:
    """建立自定義 slug 到 ID 的映射表
    
    Args:
        posts: 文章列表
        
    Returns:
        Dict[str, int]: 自定義 slug 到 ID 的映射表
    """
    mapping = {}
    
    for post in posts:
        post_id = post.get('id')
        link = post.get('link', '')
        
        custom_slug = extract_custom_slug_from_url(link)
        if custom_slug:
            mapping[custom_slug] = post_id
            logger.info(f"映射: {custom_slug} -> {post_id}")
            
    logger.info(f"共建立 {len(mapping)} 個映射")
    return mapping

def save_mapping_to_file(mapping: Dict[str, int], filename: str = 'custom_slug_mapping.json'):
    """將映射表保存到文件
    
    Args:
        mapping: 自定義 slug 到 ID 的映射表
        filename: 保存的文件名
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
        logger.info(f"映射表已保存到 {filename}")
        
    except Exception as e:
        logger.error(f"保存映射表時發生錯誤: {str(e)}")

def main():
    """主程序"""
    try:
        # 載入環境變數
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
        load_dotenv(dotenv_path)
        
        # 初始化 WordPress API
        wp = WordPressAPI(logger)
        
        # 獲取所有文章
        posts = get_all_posts(wp)
        
        if not posts:
            logger.error("沒有獲取到任何文章")
            return
            
        # 建立自定義 slug 到 ID 的映射表
        mapping = build_custom_slug_to_id_mapping(posts)
        
        if not mapping:
            logger.error("沒有建立任何映射")
            return
            
        # 保存映射表到文件
        save_mapping_to_file(mapping)
        
        # 顯示一些映射示例
        logger.info("映射示例:")
        count = 0
        for slug, post_id in mapping.items():
            logger.info(f"{slug} -> {post_id}")
            count += 1
            if count >= 5:
                break
                
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {str(e)}")

if __name__ == "__main__":
    main()
