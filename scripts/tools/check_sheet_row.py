#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import argparse
from dotenv import load_dotenv

# 將上層目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 載入環境變數
load_dotenv('./config/.env')

# 引入專案中的 Google Sheets 模組
from scripts.google_sheets import setup_google_sheets

# 開啟試算表
try:
    sheet = setup_google_sheets()
    print("Google Sheets 連接成功")
except Exception as e:
    print(f"Google Sheets 連接失敗: {str(e)}")
    sys.exit(1)

# 設定命令行參數
def parse_args():
    parser = argparse.ArgumentParser(description='檢查 Google Sheets 中特定列的資料')
    parser.add_argument('row_number', type=int, help='要檢查的列號')
    return parser.parse_args()

# 取得命令行參數
args = parse_args()
row_number = args.row_number

try:
    # 獲取指定列的資料
    row_data = sheet.row_values(row_number)
    print(f'第 {row_number} 列資料成功獲取')
    print(f'欄位數量: {len(row_data)}')
    
    # 顯示各欄位內容
    print(f'\n各欄位內容:')
    for i, cell in enumerate(row_data):
        print(f'{chr(65+i)}: {cell}')
    
    # 檢查欄位對應
    column_mapping = {
        'youtube_link': 'D',  # YouTube 連結
        'wp_link': 'H',       # WP 文章連結
        'wp_id': 'I',         # WP 文章 ID
        'video_description_status': 'L',
        'tags_from_description_status': 'M'
    }
    
    print("\n欄位對應檢查:")
    for field, column in column_mapping.items():
        idx = ord(column) - ord('A')
        if idx < len(row_data):
            value = row_data[idx]
            print(f"{field} ({column}列): '{value}'")
        else:
            print(f"{field} ({column}列): 超出範圍 (需要索引 {idx}, 但列表長度只有 {len(row_data)})")
    
    # 檢查列表索引與欄位對應的關係
    print("\n欄位對應分析:")
    l_index = ord('L') - ord('A')
    m_index = ord('M') - ord('A')
    print(f"L 欄索引: {l_index}, M 欄索引: {m_index}")
    print(f"列表長度: {len(row_data)}")
    
    # 檢查列表中是否有空值
    print("\n空值檢查:")
    for i, cell in enumerate(row_data):
        if not cell:
            print(f"{chr(65+i)}: 空值")
    
    # 顯示原始 JSON 格式的資料
    print("\n原始資料 (JSON 格式):")
    print(json.dumps(row_data, ensure_ascii=False, indent=2))
    
    # 檢查工作表的其他資訊
    print("\n工作表資訊:")
    print(f"工作表標題: {sheet.title}")
    print(f"工作表總列數: {sheet.row_count}")
    print(f"工作表總欄數: {sheet.col_count}")
    
    # 檢查標題列
    header_row = sheet.row_values(1)
    print("\n標題列:")
    for i, header in enumerate(header_row):
        print(f"{chr(65+i)}: {header}")
except Exception as e:
    print(f"檢查第 {row_number} 列資料時發生錯誤: {str(e)}")
