import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LEVEL_ICONS = {
    'INFO': 'ℹ️',
    'ERROR': '❌',
    'WARNING': '⚠️',
    'SUCCESS': '✅',
    'DEBUG': '🔍',
}

class WorkflowFormatter(logging.Formatter):
    def format(self, record):
        stage_info = getattr(record, 'stage', 'Unknown')
        component = getattr(record, 'component', record.name)
        
        icon = LEVEL_ICONS.get(record.levelname, '')
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        
        return f"{timestamp} {icon} [Stage-{stage_info}] [{component}] [{record.levelname}] {record.getMessage()}"

class WorkflowLogger:
    _instance = None
    
    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            cls._instance = cls._setup_logger()
        return cls._instance
    
    @staticmethod
    def _setup_logger():
        logger = logging.getLogger('automation_workflow')
        logger.setLevel(logging.INFO)
        
        log_file = Path.home() / "Library/Logs" / "automation_workflow.log"
        handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        handler.setFormatter(WorkflowFormatter())
        logger.addHandler(handler)
        
        return logger

def get_workflow_logger(stage, component=None):
    logger = WorkflowLogger.get_logger()
    
    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.stage = stage
            record.component = component
            return True
    
    for handler in logger.handlers:
        handler.filters = []
        handler.addFilter(ContextFilter())
    
    return logger

def setup_logger(name):
    return get_workflow_logger('Unknown', name)