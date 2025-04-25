#!/usr/bin/env python3

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# 將父目錄加入 sys.path，以便導入 gemini_video_analyzer
sys.path.append(str(Path(__file__).parent.parent))

from gemini_video_analyzer import GeminiVideoAnalyzer
from logger import get_workflow_logger
from dotenv import load_dotenv

# 設定日誌
logger = get_workflow_logger('test', 'gemini_versions')

class GeminiVersionTester(GeminiVideoAnalyzer):
    """用於測試不同 Gemini 版本的類別"""
    
    def __init__(self, model_version):
        """初始化測試類別
        
        Args:
            model_version: Gemini 模型版本
        """
        super().__init__()
        self.model = model_version
        logger.info(f"初始化 Gemini 測試器，使用模型: {self.model}")
    
    def test_analyze_youtube(self, youtube_url, title=""):
        """測試 YouTube 影片分析
        
        Args:
            youtube_url: YouTube 影片網址
            title: 影片標題，可選
            
        Returns:
            包含測試結果的字典
        """
        start_time = time.time()
        try:
            logger.info(f"開始使用 {self.model} 分析影片: {youtube_url}")
            result = self.analyze_youtube_video(youtube_url, title)
            end_time = time.time()
            
            if result:
                # 計算結果統計
                word_count = len(result.split())
                char_count = len(result)
                
                return {
                    "model": self.model,
                    "success": True,
                    "duration_seconds": round(end_time - start_time, 2),
                    "word_count": word_count,
                    "char_count": char_count,
                    "result": result
                }
            else:
                end_time = time.time()
                return {
                    "model": self.model,
                    "success": False,
                    "duration_seconds": round(end_time - start_time, 2),
                    "error": "分析結果為空"
                }
                
        except Exception as e:
            end_time = time.time()
            logger.error(f"使用 {self.model} 分析時發生錯誤: {str(e)}")
            return {
                "model": self.model,
                "success": False,
                "duration_seconds": round(end_time - start_time, 2),
                "error": str(e)
            }

def save_results(results, youtube_url):
    """儲存測試結果到檔案
    
    Args:
        results: 測試結果列表
        youtube_url: 測試的 YouTube 網址
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(__file__).parent.parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    # 從 URL 中提取影片 ID
    if "youtu.be/" in youtube_url:
        video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
    elif "v=" in youtube_url:
        video_id = youtube_url.split("v=")[1].split("&")[0]
    else:
        video_id = "unknown"
    
    filename = f"gemini_test_{video_id}_{timestamp}.json"
    filepath = results_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"測試結果已儲存至: {filepath}")
    return filepath

def compare_results(results):
    """比較不同模型的測試結果
    
    Args:
        results: 測試結果列表
    
    Returns:
        比較結果摘要
    """
    if not results:
        return "沒有測試結果可供比較"
    
    # 篩選成功的結果
    successful_results = [r for r in results if r.get("success", False)]
    if not successful_results:
        return "所有測試都失敗了"
    
    # 比較回應時間
    fastest = min(successful_results, key=lambda x: x["duration_seconds"])
    slowest = max(successful_results, key=lambda x: x["duration_seconds"])
    
    # 比較內容長度
    if all("char_count" in r for r in successful_results):
        most_detailed = max(successful_results, key=lambda x: x["char_count"])
        least_detailed = min(successful_results, key=lambda x: x["char_count"])
    else:
        most_detailed = {"model": "無法判斷"}
        least_detailed = {"model": "無法判斷"}
    
    summary = f"""測試結果比較:
最快回應: {fastest['model']} ({fastest['duration_seconds']}秒)
最慢回應: {slowest['model']} ({slowest['duration_seconds']}秒)
最詳細內容: {most_detailed['model']} ({most_detailed.get('char_count', '未知')}字元)
最簡短內容: {least_detailed['model']} ({least_detailed.get('char_count', '未知')}字元)

成功率: {len(successful_results)}/{len(results)} ({len(successful_results)/len(results)*100:.1f}%)
"""
    return summary

def main():
    """主函數"""
    # 載入環境變數
    dotenv_path = Path(__file__).parent.parent.parent / "config" / ".env"
    load_dotenv(dotenv_path)
    
    if len(sys.argv) < 2:
        print("使用方式: python test_gemini_versions.py <youtube_url> [title]")
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    
    # 檢查 URL 格式
    if not youtube_url.startswith(('http://', 'https://')):
        print("請提供有效的 YouTube 影片網址")
        sys.exit(1)
    
    if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
        print("目前只支援 YouTube 影片網址")
        sys.exit(1)
    
    # 要測試的模型版本
    models = [
        "gemini-1.5-flash",  # 目前使用的版本
        "gemini-2.0-flash",  # 目前在 file_client 中使用的版本
        "gemini-2.5-flash"   # 要測試的新版本
    ]
    
    results = []
    
    # 依序測試每個模型
    for model in models:
        print(f"\n===== 測試 {model} =====")
        tester = GeminiVersionTester(model)
        
        # 執行測試
        result = tester.test_analyze_youtube(youtube_url, title)
        results.append(result)
        
        # 顯示測試結果摘要
        if result["success"]:
            print(f"✅ 成功 - 耗時: {result['duration_seconds']}秒, 內容長度: {result.get('char_count', '未知')}字元")
            # 顯示結果的前 200 個字元
            content_preview = result["result"][:200] + "..." if len(result["result"]) > 200 else result["result"]
            print(f"內容預覽: {content_preview}")
        else:
            print(f"❌ 失敗 - 耗時: {result['duration_seconds']}秒, 錯誤: {result.get('error', '未知錯誤')}")
        
        # 在測試之間等待一段時間，避免頻率限制
        if model != models[-1]:
            wait_time = 30  # 等待 30 秒
            print(f"等待 {wait_time} 秒後測試下一個模型...")
            time.sleep(wait_time)
    
    # 儲存測試結果
    results_file = save_results(results, youtube_url)
    
    # 比較結果
    comparison = compare_results(results)
    print("\n" + comparison)
    
    print(f"\n完整測試結果已儲存至: {results_file}")

if __name__ == "__main__":
    main()
