from typing import Dict, List, Tuple
import io
import logging
from pathlib import Path
from openai import OpenAI
import os
from .openai_agent import OpenAIAgent

# Setup logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI()

# Constants for file validation
MAX_FILE_SIZE_MB = 100  # Increased for video files
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for reading
SUPPORTED_VIDEO_FORMATS = ['mp4', 'mpeg', 'm4v', 'mov', 'avi', 'wmv']

class FileValidationError(Exception):
    """Custom exception for file validation errors"""
    pass

async def validate_file_with_streaming(file_stream: io.BytesIO) -> Tuple[bool, str]:
    """
    Validate file size using streaming to handle large files efficiently
    """
    try:
        size = 0
        while chunk := file_stream.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise FileValidationError(
                    f"File size exceeds {MAX_FILE_SIZE_MB}MB limit. Please upload a smaller file."
                )
        
        # Reset stream position
        file_stream.seek(0)
        return True, ""
    except FileValidationError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"Error validating file: {str(e)}")
        return False, f"Error validating file: {str(e)}"

def validate_video_format(filename: str) -> Tuple[bool, str]:
    """
    Validate if the file is a supported video format
    """
    try:
        ext = Path(filename).suffix.lower().strip('.')
        if ext not in SUPPORTED_VIDEO_FORMATS:
            return False, f"Unsupported video format. Supported formats are: {', '.join(SUPPORTED_VIDEO_FORMATS)}"
        return True, ""
    except Exception as e:
        logger.error(f"Error validating video format: {str(e)}")
        return False, f"Error validating video format: {str(e)}"

async def process_video_for_transcript(file_path: str) -> Tuple[bool, str]:
    """
    Process video file and get transcript using OpenAI
    """
    try:
        with open(file_path, "rb") as video_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=video_file,
                response_format="text"
            )
            return True, transcript
    except Exception as e:
        logger.error(f"Error processing video transcript: {str(e)}")
        return False, f"Error processing video transcript: {str(e)}"

async def save_temp_video(file_stream: io.BytesIO, filename: str) -> Tuple[bool, str]:
    """
    Save uploaded video to temporary location
    """
    try:
        temp_dir = Path("temp_videos")
        temp_dir.mkdir(exist_ok=True)
        
        file_path = temp_dir / filename
        with open(file_path, "wb") as f:
            f.write(file_stream.getvalue())
            
        return True, str(file_path)
    except Exception as e:
        logger.error(f"Error saving temporary video: {str(e)}")
        return False, f"Error saving temporary video: {str(e)}"

async def cleanup_temp_video(file_path: str):
    """
    Clean up temporary video file
    """
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error cleaning up temporary video: {str(e)}")