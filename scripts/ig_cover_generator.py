#!/usr/bin/env python3
import subprocess
import argparse
from pathlib import Path
import glob
import os
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_image_file(video_id: str, directory: str) -> str:
    pattern = str(Path(directory) / f"{video_id}.*")
    logger.debug(f"搜尋圖片: {pattern}")
    image_files = glob.glob(pattern)
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    
    for file in image_files:
        logger.debug(f"找到檔案: {file}")
        if Path(file).suffix.lower() in image_extensions:
            return str(Path(file).absolute())
    return None

def generate_ig_cover(input_image, output_path, text_lines, font_path):
    """
    以 FFmpeg 在 1920×3414 的黑底上置中疊入 `input_image`，
    然後在指定座標疊上兩行文字 (text_lines[0], text_lines[1])。
    """
    filter_complex = f"""
    [1:v]scale=w='min(iw,1920)':h=-1:force_original_aspect_ratio=decrease[scaled];
    [0:v][scaled]overlay=x='(W-w)/2':y='(H-h)/2'[base];
    [base]drawtext=
      fontfile={font_path}:
      text='{text_lines[0]}':
      fontcolor=#f7e7ce:
      fontsize=200:
      x=132:
      y=2030:
      box=1:
      boxcolor=black@0.45:
      boxborderw=56[text1];
    [text1]drawtext=
      fontfile={font_path}:
      text='{text_lines[1]}':
      fontcolor=#f7e7ce:
      fontsize=200:
      x=136:
      y=2336:
      box=1:
      boxcolor=black@0.45:
      boxborderw=56
    """

    cmd = [
        '/usr/local/bin/ffmpeg', '-y',
        # 建立 1920×3414 黑底畫布
        '-f', 'lavfi', '-i', 'color=c=black:s=1920x3414:r=1',
        # 讀取要疊的圖片
        '-i', input_image,
        '-filter_complex', filter_complex,
        '-frames:v', '1',
        '-q:v', '1',  # 調高輸出 JPG 品質(1=高)
        output_path
    ]
    
    subprocess.run(cmd, check=True, capture_output=True, text=True)

def main():
    parser = argparse.ArgumentParser(description='生成 IG 封面圖片(透過命令列文字)')
    parser.add_argument('video_id', help='影片 ID')
    parser.add_argument('text1', help='第一行文字')
    parser.add_argument('text2', help='第二行文字')
    parser.add_argument('output_dir', help='輸出目錄 (也放置同名圖檔)')
    parser.add_argument('--font', help='字體路徑', 
                      default="/Users/Mac/Library/Fonts/SourceHanSansTC-Heavy.otf")
    
    args = parser.parse_args()
    logger.info(f"處理影片 ID: {args.video_id}")
    
    # 找到同目錄下與 video_id 相符的圖片 (e.g. 5418.jpg)
    input_image = find_image_file(args.video_id, args.output_dir)
    if not input_image:
        logger.error(f"找不到 ID {args.video_id} 的圖檔")
        raise FileNotFoundError(f"找不到 ID {args.video_id} 的圖檔")
    
    # 產生輸出路徑 (5418_cover.jpg)
    output_path = str(Path(args.output_dir) / f"{args.video_id}_cover.jpg")
    
    # 呼叫 FFmpeg 產圖
    generate_ig_cover(input_image, output_path, (args.text1, args.text2), args.font)
    logger.info("封面圖片產生完成。")

if __name__ == '__main__':
    main()