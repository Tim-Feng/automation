import os
import sys
import re
from typing import List
from datetime import timedelta
from logger import setup_logger

logger = setup_logger('subtitle_splitter')

def parse_timestamp(timestamp: str) -> timedelta:
    """Parse SRT timestamp to timedelta"""
    time_parts = timestamp.replace(',', '.').split(':')
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = float(time_parts[2])
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def format_vtt_timestamp(td: timedelta) -> str:
    """Format timedelta to VTT timestamp"""
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

def parse_srt(content: str) -> List[dict]:
    """Parse SRT content into a list of subtitle blocks"""
    blocks = []
    current_block = {}
    
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            if current_block:
                blocks.append(current_block)
                current_block = {}
            continue
            
        if not current_block:
            current_block['index'] = int(line)
        elif ' --> ' in line:
            start, end = line.split(' --> ')
            current_block['start'] = parse_timestamp(start)
            current_block['end'] = parse_timestamp(end)
        else:
            if 'text' not in current_block:
                current_block['text'] = []
            current_block['text'].append(line)
            
    if current_block:
        blocks.append(current_block)
        
    return blocks

def get_video_ids(filename: str) -> List[str]:
   """從檔名解析影片 ID"""
   # 移除副檔名和 -zh 後綴
   base_name = os.path.splitext(filename)[0]
   if base_name.endswith('-zh'):
       base_name = base_name[:-3]
   
   if '+' in base_name:
       return base_name.split('+')
   elif '-' in base_name:
       start_id, end_id = map(int, base_name.split('-'))
       return [str(i) for i in range(start_id, end_id + 1)]
   else:
       return [base_name]

def split_subtitles(blocks: List[dict], durations: List[int]) -> List[List[dict]]:
    """Split subtitles based on video durations"""
    result = []
    current_blocks = []
    current_duration = timedelta(seconds=0)
    duration_index = 0
    
    for block in blocks:
        # 如果是最後一個時長，將剩餘字幕全部加入
        if duration_index >= len(durations):
            adjusted_block = block.copy()
            adjusted_block['start'] = block['start'] - current_duration
            adjusted_block['end'] = block['end'] - current_duration
            current_blocks.append(adjusted_block)
            continue
            
        block_duration = block['end'] - current_duration
        if block_duration.total_seconds() <= durations[duration_index]:
            adjusted_block = block.copy()
            adjusted_block['start'] = block['start'] - current_duration
            adjusted_block['end'] = block['end'] - current_duration
            current_blocks.append(adjusted_block)
        else:
            result.append(current_blocks)
            current_blocks = []
            current_duration = block['start']
            duration_index += 1
            
            adjusted_block = block.copy()
            adjusted_block['start'] = timedelta(seconds=0)
            adjusted_block['end'] = block['end'] - current_duration
            current_blocks.append(adjusted_block)
    
    if current_blocks:
        result.append(current_blocks)
        
    return result

def write_vtt(blocks: List[dict], output_path: str):
    """Write subtitle blocks to VTT file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('WEBVTT\n\n')
        for block in blocks:
            f.write(f"{format_vtt_timestamp(block['start'])} --> {format_vtt_timestamp(block['end'])}\n")
            f.write('\n'.join(block['text']) + '\n\n')

def main():
   if len(sys.argv) < 3:
       logger.error('Usage: subtitle_splitter.py <input_file> <output_dir> [duration1 duration2 ...]')
       return

   input_file = sys.argv[1]
   output_dir = sys.argv[2]
   durations = [int(d) for d in sys.argv[3:]] if len(sys.argv) > 3 else []

   filename = os.path.basename(input_file)
   video_ids = get_video_ids(filename)
   
   if len(video_ids) > 1 and len(durations) != len(video_ids) - 1:
       logger.error('時長數量需要比影片數量少 1')
       return

   try:
       with open(input_file, 'r', encoding='utf-8-sig') as f:
           content = f.read()
   except Exception as e:
       logger.error(f'讀取檔案失敗: {str(e)}')
       return

   blocks = parse_srt(content)
   
   if len(video_ids) == 1:
       os.makedirs(output_dir, exist_ok=True)
       output_path = os.path.join(output_dir, f"{video_ids[0]}-zh.vtt")
       write_vtt(blocks, output_path)
       logger.info(f"已生成字幕檔: {output_path}")
   else:
       split_blocks = split_subtitles(blocks, durations)
       os.makedirs(output_dir, exist_ok=True)
       for video_id, blocks in zip(video_ids, split_blocks):
           output_path = os.path.join(output_dir, f"{video_id}-zh.vtt")
           write_vtt(blocks, output_path)
           logger.info(f"已生成字幕檔: {output_path}")

if __name__ == '__main__':
   main()