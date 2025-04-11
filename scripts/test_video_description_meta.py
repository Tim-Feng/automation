#!/usr/bin/env python3
# test_video_description_meta.py

import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from logger import get_workflow_logger

# 設定日誌
logger = get_workflow_logger('1', 'test_video_description')

def check_post_meta(post_id: int):
    """檢查特定文章的 video_description meta 欄位
    
    Args:
        post_id: WordPress 文章 ID
    """
    # 載入環境變數
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    
    # WordPress 認證資訊
    site_url = os.getenv("WP_SITE_URL")
    if not site_url:
        logger.error("未設定 WP_SITE_URL 環境變數")
        return
    
    site_url = site_url.rstrip('/')
    username = os.getenv("WP_USERNAME")
    password = os.getenv("WP_APP_PASSWORD")
    
    if not username or not password:
        logger.error("未設定 WordPress 認證資訊")
        return
    
    # 構建 API 請求
    api_url = f"{site_url}/wp-json/wp/v2/video/{post_id}"
    auth = HTTPBasicAuth(username, password)
    
    logger.info(f"正在檢查文章 ID {post_id} 的 meta 欄位")
    
    try:
        # 發送請求
        response = requests.get(api_url, auth=auth)
        
        if response.status_code == 200:
            data = response.json()
            
            # 顯示完整的回應資料，以便深入分析
            logger.debug(f"完整回應資料: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}...")
            
            # 檢查 meta 欄位
            if 'meta' in data:
                logger.info("成功獲取 meta 欄位")
                
                # 顯示所有可用的 meta 欄位
                logger.info(f"可用的 meta 欄位: {', '.join(data['meta'].keys())}")
                
                if 'video_description' in data['meta']:
                    description = data['meta']['video_description']
                    # 只顯示前 100 個字元，避免日誌過長
                    preview = description[:100] + "..." if len(description) > 100 else description
                    logger.info(f"成功找到 video_description 欄位！")
                    logger.info(f"內容預覽: {preview}")
                    
                    # 將完整內容寫入檔案
                    output_file = f"video_description_{post_id}.txt"
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(description)
                    logger.info(f"完整內容已寫入檔案: {output_file}")
                    
                    return True
                else:
                    logger.warning("未在 meta 欄位中找到 video_description")
                    
                    # 嘗試直接查詢所有 meta 欄位
                    logger.info("嘗試直接查詢所有 meta 欄位...")
                    meta_api_url = f"{site_url}/wp-json/wp/v2/video/{post_id}/meta"
                    try:
                        meta_response = requests.get(meta_api_url, auth=auth)
                        if meta_response.status_code == 200:
                            meta_data = meta_response.json()
                            logger.info(f"所有 meta 欄位: {json.dumps(meta_data, indent=2, ensure_ascii=False)}")
                            
                            if 'video_description' in meta_data:
                                logger.info(f"在完整 meta API 中找到 video_description 欄位!")
                                return True
                        else:
                            logger.warning(f"Meta API 請求失敗: {meta_response.status_code}")
                    except Exception as e:
                        logger.error(f"Meta API 請求錯誤: {str(e)}")
            else:
                logger.warning("回應中沒有 meta 欄位")
                logger.debug(f"回應內容: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        else:
            logger.error(f"API 請求失敗: {response.status_code}")
            logger.error(f"錯誤訊息: {response.text}")
    except Exception as e:
        logger.error(f"檢查過程中發生錯誤: {str(e)}")
    
    return False

def main():
    """主函數"""
    if len(sys.argv) < 2:
        print("使用方式: python test_video_description_meta.py <post_id>")
        sys.exit(1)
    
    try:
        post_id = int(sys.argv[1])
        check_post_meta(post_id)
    except ValueError:
        logger.error(f"無效的文章 ID: {sys.argv[1]}")
        print("文章 ID 必須是一個整數")
        sys.exit(1)

if __name__ == "__main__":
    main()
