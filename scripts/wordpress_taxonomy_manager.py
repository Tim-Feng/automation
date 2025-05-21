#!/usr/bin/env python3
import os
import sys
import requests
import logging
from typing import List, Dict
import argparse
from urllib.parse import unquote
from dotenv import load_dotenv
from pathlib import Path
from logger import get_workflow_logger

logger = get_workflow_logger('1', 'taxonomy_manager')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class WordPressTaxonomyManager:
    def __init__(self):
        """初始化 WordPress 分類管理工具"""
        base_dir = Path(__file__).resolve().parent.parent
        load_dotenv(base_dir / 'config' / '.env')
        
        self.site_url = os.getenv('WP_SITE_URL')
        self.username = os.getenv('WP_USERNAME')
        self.password = os.getenv('WP_APP_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("請設定 WP_USERNAME 和 WP_APP_PASSWORD 環境變數")
            
        self.auth = (self.username, self.password)
        
    def create_term(self, taxonomy: str, name: str) -> Dict:
        """創建新的分類或標籤
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            name: 分類或標籤的名稱
            
        Returns:
            Dict: 新創建的分類或標籤資訊
        """
        # 使用正確的 REST API 端點
        if taxonomy == 'categories':
            endpoint = 'video_category'
        elif taxonomy == 'tags':
            endpoint = 'video_tag'
        else:
            raise ValueError(f"不支援的分類法: {taxonomy}")
            
        url = f"{self.site_url}/wp-json/wp/v2/{endpoint}"
        data = {
            'name': name,
            'description': ''
        }
        
        logger.info(f"正在創建新的 {taxonomy}...")
        logger.info(f"API 端點: {url}")
        logger.info(f"請求資料: {data}")
        
        try:
            response = requests.post(url, auth=self.auth, json=data, timeout=10)
            logger.info(f"API 回應狀態碼: {response.status_code}")
            logger.info(f"API 回應內容: {response.text}")
            
            if response.status_code != 201:
                logger.error(f"創建 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                raise Exception(f"創建 {taxonomy} 失敗: {response.text}")
                
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("API 請求超時")
            raise Exception("API 請求超時，請稍後再試")
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {str(e)}")
            raise Exception(f"API 請求失敗: {str(e)}")
        
    def get_all_terms(self, taxonomy: str) -> List[Dict]:
        """取得指定分類法的所有項目
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            
        Returns:
            List[Dict]: 分類項目列表
        """
        items = []
        page = 1
        per_page = 100
        
        # 使用正確的 REST API 端點
        if taxonomy == 'categories':
            endpoint = 'video_category'
        elif taxonomy == 'tags':
            endpoint = 'video_tag'
        else:
            raise ValueError(f"不支援的分類法: {taxonomy}")
        
        while True:
            url = f"{self.site_url}/wp-json/wp/v2/{endpoint}?page={page}&per_page={per_page}"
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 400:  # 沒有更多頁面
                break
                
            if response.status_code != 200:
                logger.error(f"取得 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                break
                
            current_items = response.json()
            if not current_items:
                break
                
            current_items = response.json()
            if not current_items:
                break
                
            items.extend(current_items)
            page += 1
            
            # 記錄一些有用的信息
            if page == 1:
                total = response.headers.get('X-WP-Total')
                if total:
                    logger.info(f"總計找到 {total} 個{taxonomy}")
            
        return items
        
    def display_terms(self, items: List[Dict], taxonomy: str):
        """顯示分類項目資訊
        
        Args:
            items: 分類項目列表
            taxonomy: 分類法名稱（用於顯示）
        """
        print(f"\n=== WordPress {taxonomy} 列表 ===")
        print(f"總計: {len(items)} 個項目\n")
        
        for item in items:
            print(f"ID: {item.get('id')}")
            # 如果是分類，則從 title 取得名稱，否則從 name 取得
            name = None
            if taxonomy == 'categories':
                title = item.get('title', {})
                if isinstance(title, dict):
                    name = title.get('rendered')
                else:
                    name = title
            else:
                name = item.get('name')
                
            # URL 解碼名稱和代稱
            display_name = unquote(name if name else item.get('slug'))
            display_slug = unquote(item.get('slug'))
            print(f"名稱: {display_name}")
            print(f"代稱: {display_slug}")
            
            # 如果有 count 欄位才顯示
            count = item.get('count')
            if count is not None:
                print(f"文章數: {count}")
                
            # 如果有描述且不是空的才顯示
            content = None
            if taxonomy == 'categories':
                content_obj = item.get('content', {})
                if isinstance(content_obj, dict):
                    content = content_obj.get('rendered')
                else:
                    content = content_obj
            else:
                content = item.get('description')
                
            if content and str(content).strip():
                print(f"描述: {content}")
                
            print("-" * 30)
            
def main():
    try:
        parser = argparse.ArgumentParser(description='WordPress 分類管理工具')
        parser.add_argument('action', choices=['list', 'create'], help='要執行的操作（list 或 create）')
        parser.add_argument('taxonomy', choices=['categories', 'tags'], help='要管理的分類法（categories 或 tags）')
        parser.add_argument('--name', help='新分類或標籤的名稱（只在 create 時需要）')
        args = parser.parse_args()
        
        wp = WordPressTaxonomyManager()
        
        if args.action == 'list':
            terms = wp.get_all_terms(args.taxonomy)
            wp.display_terms(terms, args.taxonomy)
        elif args.action == 'create':
            if not args.name:
                logger.error('創建新分類或標籤時必須提供 --name 參數')
                sys.exit(1)
            term = wp.create_term(args.taxonomy, args.name)
            print(f"\n=== 創建新的 {args.taxonomy} ===")
            print(f"ID: {term.get('id')}")
            print(f"名稱: {unquote(term.get('name', ''))}")
            print(f"代稱: {unquote(term.get('slug', ''))}")
            print("-" * 30)
        
    except Exception as e:
        logger.error(f"執行時發生錯誤: {e}")
        sys.exit(1)
        
if __name__ == '__main__':
    main()
