import os
import logging
import sys
import subprocess

# 檢查並安裝 pysubs2
try:
    import pysubs2
except ImportError:
    logging.info("正在安裝 pysubs2...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pysubs2"])
    import pysubs2

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 輸出到控制台
        logging.FileHandler(os.path.expanduser("~/Library/Logs/subtitle_converter.log"))  # 保存到用戶的 Logs 目錄
    ]
)
logger = logging.getLogger(__name__)

def convert_subtitle(srt_path):
    """
    Convert SRT to ASS with specific formatting
    
    Args:
        srt_path (str): Path to the input SRT file
    """
    try:
        # 確認輸入文件是否存在
        if not os.path.exists(srt_path):
            logger.error(f"Input file not found: {srt_path}")
            return None
            
        logger.info(f"Processing subtitle file: {srt_path}")
        
        # Load the subtitle
        subs = pysubs2.load(srt_path)
        logger.info("Successfully loaded subtitle file")
        
        # Create a new style
        style = pysubs2.SSAStyle(
            fontname="PingFang TC",
            fontsize=120,
            bold=True,
            italic=False,
            underline=False,
            strikeout=False,
            primarycolor=pysubs2.Color(255, 255, 255, 0),  # &H00FFFFFF
            outline=2.7,
            shadow=0.1,
            alignment=8,   # 頂端置中
            marginl=10,
            marginr=10,
            marginv=1095,  # 距頂端的距離
            scalex=100,
            scaley=100,
            spacing=0,
            angle=0,
            borderstyle=1,
            encoding=1
        )
        
        # Add the style with name "蘋方 1340"
        subs.styles["蘋方 1340"] = style
        logger.info("Style applied successfully")
        
        # Set all events to use this style
        for line in subs:
            line.style = "蘋方 1340"
        logger.info("Applied style to all subtitle lines")
        
        # Set script info
        subs.info["PlayResX"] = "1920"
        subs.info["PlayResY"] = "1340"
        
        # Generate output filename
        directory = os.path.dirname(srt_path)
        filename = os.path.basename(srt_path)
        base_name = filename.replace("-zh.srt", "")  # 移除 -zh.srt
        output_path = os.path.join(directory, f"{base_name}-1920*1340-zh.ass")
        
        logger.info(f"Saving to: {output_path}")
        
        # Save as ASS
        subs.save(output_path)
        logger.info(f"Successfully saved ASS file: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error converting subtitle: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

if __name__ == "__main__":
    # 檢查是否提供了輸入文件路徑
    if len(sys.argv) != 2:
        print("Usage: python3 srt_to_ass_with_style.py <path_to_srt_file>")
        sys.exit(1)
    
    srt_path = sys.argv[1]
    logger.info(f"Starting conversion for: {srt_path}")
    
    # 執行轉換
    output_file = convert_subtitle(srt_path)
    
    if output_file:
        logger.info(f"Conversion completed successfully. Output file: {output_file}")
    else:
        logger.error("Conversion failed")
        sys.exit(1)