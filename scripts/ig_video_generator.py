#!/usr/bin/env python3
import subprocess
import argparse
from pathlib import Path
import logging
import os
import re

# 設定日誌輸出到文件
log_file = '/tmp/ig_video_generator.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # 同時輸出到終端
    ]
)
logger = logging.getLogger(__name__)

def generate_ig_video(input_video, output_path, texts, font_path):
    logger.debug(f"開始處理影片：{input_video}")
    logger.debug(f"輸出路徑：{output_path}")
    logger.debug(f"文字內容：{texts}")
    filter_complex = (
        f"[0:v]scale=1920:3414:force_original_aspect_ratio=decrease,pad=1920:3414:(ow-iw)/2:(oh-ih)/2[scaled];"
        f"[scaled]drawtext=fontfile='{font_path}':text='{texts[0]}':fontcolor=black:fontsize=188:"
        f"x=110:y=580:box=1:boxcolor=#f7e7ce@1:boxborderw=30:enable='lt(t,10)'[text1];"
        f"[text1]drawtext=fontfile='{font_path}':text='{texts[1]}':fontcolor=#f7e7ce:fontsize=188:"
        f"x=110:y=830:enable='lt(t,10)'[text2];"
        f"[text2]drawtext=fontfile='{font_path}':text='{texts[2]}':fontcolor=#f7e7ce:fontsize=76:"
        f"x=110:y=2600:enable='lt(t,10)'[final]"
    )

    cmd = [
        '/usr/local/bin/ffmpeg', '-y',
        '-i', str(input_video),
        '-filter_complex', filter_complex,
        '-q:v', '1',
        '-map', '[final]',  # 映射視頻流
        '-map', '0:a',      # 映射原始音頻流
        '-c:a', 'copy',     # 直接複製音頻，不重新編碼
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.debug(f"FFmpeg 輸出：{result.stdout}")
        if result.stderr:
            logger.debug(f"FFmpeg 錯誤輸出：{result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 執行失敗：{e.stderr}")
        raise

def get_video_id(input_path: str) -> str:
    """從輸入路徑中提取影片 ID"""
    filename = Path(input_path).stem
    
    # 先檢查是否為範圍或組合影片
    range_match = re.match(r'^(\d+[-+]\d+)-\d+\*\d+(?:-[a-z]+)?$', filename)
    if range_match:
        return range_match.group(1)
    
    # 如果不是範圍或組合影片，則檢查是否為單支影片
    single_match = re.match(r'^(\d+)-\d+\*\d+(?:-[a-z]+)?$', filename)
    if single_match:
        return single_match.group(1)
    
    return filename

def main():
    parser = argparse.ArgumentParser(description='生成 IG 影片')
    parser.add_argument('input_video', help='輸入影片路徑')
    parser.add_argument('title1', help='大標題第一行')
    parser.add_argument('title2', help='大標題第二行')
    parser.add_argument('footer', help='底部小字')
    parser.add_argument('--font', help='字體路徑', 
                       default="/Users/Mac/Library/Fonts/jf-jinxuan-medium.otf")
    parser.add_argument('--output_dir', help='輸出目錄', default=os.getcwd())

    args = parser.parse_args()
    logger.info(f"處理影片：{args.input_video}")
    
    input_path = Path(args.input_video)
    output_dir = Path(args.output_dir)
    
    # 從輸入檔名中提取影片 ID，並生成新的輸出檔名
    video_id = get_video_id(input_path)
    output_filename = f"{video_id}-1920*3414-zh.mp4"
    output_path = output_dir / output_filename
    
    if not input_path.exists():
        logger.error(f"輸入影片不存在：{input_path}")
        raise FileNotFoundError(f"找不到影片文件：{input_path}")
    
    generate_ig_video(input_path, output_path, 
                     (args.title1, args.title2, args.footer), args.font)
    logger.info(f"影片處理完成，輸出檔案：{output_path}")

if __name__ == '__main__':
    main()