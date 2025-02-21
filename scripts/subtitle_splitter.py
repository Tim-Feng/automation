import os
import sys
import re
from typing import List
from datetime import timedelta
from logger import get_workflow_logger

logger = get_workflow_logger('3', 'subtitle_splitter')  # Stage 3 因為這是字幕處理階段

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
    if not blocks:
        logger.error("沒有可分割的字幕")
        return []
        
    if not durations:
        logger.error("沒有提供分割時長")
        return []
    
    result = []
    current_blocks = []
    current_duration = timedelta(seconds=0)
    duration_index = 0
    total_duration = sum(durations)
    
    try:
        for block in blocks:
            block_end_time = block['end'].total_seconds()
            
            # 如果已經用完所有時長，將剩餘字幕加入最後一個影片
            if duration_index >= len(durations):
                adjusted_block = block.copy()
                adjusted_block['start'] = block['start'] - current_duration
                adjusted_block['end'] = block['end'] - current_duration
                current_blocks.append(adjusted_block)
                continue
            
            # 計算當前影片的結束時間點
            current_video_end = sum(durations[:duration_index + 1])
            
            if block_end_time <= current_video_end:
                # 區塊屬於當前影片
                adjusted_block = block.copy()
                adjusted_block['start'] = block['start'] - current_duration
                adjusted_block['end'] = block['end'] - current_duration
                current_blocks.append(adjusted_block)
            else:
                # 需要開始新的影片
                if current_blocks:
                    result.append(current_blocks)
                    current_blocks = []
                
                current_duration = timedelta(seconds=current_video_end)
                duration_index += 1
                
                adjusted_block = block.copy()
                adjusted_block['start'] = timedelta(seconds=0)
                adjusted_block['end'] = block['end'] - current_duration
                current_blocks.append(adjusted_block)
    
    except Exception as e:
        logger.error(f"分割字幕時發生錯誤：{str(e)}")
        return []
    
    # 加入最後一個影片的字幕
    if current_blocks:
        result.append(current_blocks)
    
    # 驗證結果
    expected_videos = len(durations) + 1
    if len(result) != expected_videos:
        logger.warning(f"預期產生 {expected_videos} 個影片，但實際產生 {len(result)} 個")
    
    # 驗證每個影片的字幕時間戳
    for i, video_blocks in enumerate(result):
        if not video_blocks:
            logger.warning(f"影片 {i} 沒有字幕")
            continue
        
        video_duration = durations[i] if i < len(durations) else None
        last_block_end = video_blocks[-1]['end'].total_seconds()
        
        if video_duration and last_block_end > video_duration:
            logger.warning(f"影片 {i} 的字幕超出影片時長：{last_block_end}s > {video_duration}s")
    
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
        logger.error('使用方式：subtitle_splitter.py <輸入檔案> <輸出資料夾> [時長1 時長2 ...]')
        return

    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    durations = [int(d) for d in sys.argv[3:]] if len(sys.argv) > 3 else []

    filename = os.path.basename(input_file)
    video_ids = get_video_ids(filename)
    
    if len(video_ids) > 1 and len(durations) != len(video_ids) - 1:
        logger.error(f'時長數量需要比影片數量少 1（目前有 {len(durations)} 個時長，但有 {len(video_ids)} 個影片）')
        return

    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        logger.error(f'讀取檔案失敗：{str(e)}')
        return

    blocks = parse_srt(content)
    os.makedirs(output_dir, exist_ok=True)
    
    if len(video_ids) == 1:
        output_path = os.path.join(output_dir, f"{video_ids[0]}-zh.vtt")
        write_vtt(blocks, output_path)
    else:
        split_blocks = split_subtitles(blocks, durations)
        if not split_blocks:
            logger.error("字幕裁切失敗")
            return
            
        for video_id, blocks in zip(video_ids, split_blocks):
            output_path = os.path.join(output_dir, f"{video_id}-zh.vtt")
            write_vtt(blocks, output_path)

if __name__ == '__main__':
   main()