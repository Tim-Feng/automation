"""
Dependency management utilities for the automation pipeline.
"""
import subprocess
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def check_and_update_ytdlp() -> Tuple[bool, str]:
    """
    Check if yt-dlp needs update and perform the update if necessary.
    
    Returns:
        Tuple[bool, str]: (success, message)
            - success: True if check/update was successful
            - message: Status or error message
    """
    try:
        # Check current version
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        current_version = result.stdout.strip()
        
        # Try to update
        logger.info(f"Current yt-dlp version: {current_version}")
        logger.info("Checking for yt-dlp updates...")
        
        update_result = subprocess.run(['pip', 'install', '--upgrade', 'yt-dlp'],
                                     capture_output=True,
                                     text=True)
        
        if update_result.returncode == 0:
            # Check new version after update
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            new_version = result.stdout.strip()
            
            if new_version != current_version:
                msg = f"yt-dlp updated from {current_version} to {new_version}"
                logger.info(msg)
            else:
                msg = f"yt-dlp is already at the latest version ({current_version})"
                logger.info(msg)
            return True, msg
        else:
            error_msg = f"Failed to update yt-dlp: {update_result.stderr}"
            logger.error(error_msg)
            return False, error_msg
            
    except subprocess.CalledProcessError as e:
        error_msg = f"Error checking/updating yt-dlp: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
