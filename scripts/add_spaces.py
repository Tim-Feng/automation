import sys
import os
import logging
import chardet
import re
from logger import get_workflow_logger

# 設定日誌記錄
logger = get_workflow_logger('3', 'subtitle_formatter')  # Stage 3 因為這是字幕處理階段

def convert_to_utf8(input_file, output_file=None):
    """將檔案轉換為 UTF-8 編碼"""
    if not output_file:
        output_file = input_file

    try:
        # 先讀取檔案內容
        with open(input_file, 'rb') as f:
            raw_data = f.read()

        # 嘗試不同的編碼
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'big5', 'gb18030']
        content = None
        
        # 先用 chardet 檢測
        result = chardet.detect(raw_data)
        if result['encoding']:
            encodings.insert(0, result['encoding'])
        
        # 嘗試所有可能的編碼
        for encoding in encodings:
            try:
                content = raw_data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if content is None:
            logger.error(f'無法判斷檔案編碼：{input_file}')
            return False
            
        # 寫入 UTF-8 檔案
        with open(output_file, 'w', encoding='utf-8-sig') as f:
            f.write(content)
            
        return True
        
    except Exception as e:
        logger.error(f'轉換 UTF-8 失敗：{str(e)}')
        return False

def format_subtitle_spacing(input_file, output_file=None):
    """處理字幕檔案的空格格式"""
    if not os.path.exists(input_file):
        logger.error(f"找不到輸入檔案：{input_file}")
        return False

    if output_file is None:
        output_file = input_file

    # 先轉換為 UTF-8
    temp_file = input_file + '.utf8'
    try:
        if not convert_to_utf8(input_file, temp_file):
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

        # 讀取 UTF-8 檔案
        with open(temp_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()

        # 處理每一行
        processed_lines = []
        for line in lines:
            if ' --> ' in line or line.strip().isdigit():
                processed_lines.append(line)
                continue
            
            line = line.replace(r'\N', '__NEWLINE__')
            line = line.replace('……', '⋯⋯')
            
            half_width_punctuation = ['-', '=', '+', '*', '/', '\\']
            for punct in half_width_punctuation:
                line = re.sub(re.escape(punct), f' {punct} ', line)
            
            patterns = [
                (r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2'),
                (r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2'),
                (r'([\u4e00-\u9fff])([0-9])', r'\1 \2'),
                (r'([0-9])([\u4e00-\u9fff])', r'\1 \2')
            ]
            
            for pattern, repl in patterns:
                line = re.sub(pattern, repl, line)
                
            line = line.replace('__NEWLINE__', r'\N')
            line = re.sub(r'\s+', ' ', line)
            processed_lines.append(line.strip() + '\n')

        # 寫入最終檔案
        with open(output_file, 'w', encoding='utf-8-sig') as f:
            f.writelines(processed_lines)

        # 清理暫存檔
        if os.path.exists(temp_file):
            os.remove(temp_file)

        return True

    except Exception as e:
        logger.error(f"處理檔案時發生錯誤：{str(e)}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使用方式: python add_spaces.py <輸入檔案> [輸出檔案]', file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = format_subtitle_spacing(input_file, output_file)
    if not success:
        sys.exit(1)  # 如果處理失敗，返回非零退出碼