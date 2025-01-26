# scripts/logger.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LEVEL_ICONS = {
    'INFO': 'ℹ️',
    'ERROR': '❌',
    'SUCCESS': '✓',
}

class IconFormatter(logging.Formatter):
    def format(self, record):
        icon = LEVEL_ICONS.get(record.levelname, '')
        return f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} {icon} [{record.levelname}] {record.getMessage()}"

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    log_file = Path.home() / "Library/Logs" / f"{name}.log"
    handler = RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=5)
    handler.setFormatter(IconFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    return logger