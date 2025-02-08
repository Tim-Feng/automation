#!/usr/bin/env python3
import sys
from logger import get_workflow_logger

def log_message(stage, level, message, component=None):
    """
    Bridge function to log messages from AppleScript to the unified logging system
    
    Args:
        stage (str): Workflow stage (1-4)
        level (str): Log level (INFO, ERROR, WARNING, SUCCESS, DEBUG)
        message (str): Log message
        component (str, optional): Component name
    """
    logger = get_workflow_logger(stage, component)
    level = level.lower()
    if hasattr(logger, level):
        getattr(logger, level)(message)
    else:
        logger.info(message)  # Fallback to info if level is not recognized

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: log_bridge.py <stage> <level> <message> [component]")
        sys.exit(1)
    
    stage = sys.argv[1]
    level = sys.argv[2]
    message = sys.argv[3]
    component = sys.argv[4] if len(sys.argv) > 4 else None
    
    log_message(stage, level, message, component)
