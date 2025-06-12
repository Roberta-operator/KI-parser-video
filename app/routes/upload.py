from fastapi import APIRouter, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
import io
import logging
from ..utils.file_processor import (
    validate_file_with_streaming,
    validate_video_format,
    save_temp_video,
    process_video_for_transcript,
    cleanup_temp_video
)
from ..utils.openai_agent import OpenAIAgent

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload-video")
async def upload_video(file: UploadFile) -> Dict:
    """
    Handle video upload, transcription, and release notes generation
    """
    logger.info(f"Received video upload request for file: {file.filename}")
    logger.info(f"File content type: {file.content_type}")

    # Check if filename exists
    if not file.filename:
        logger.error("No filename provided")
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate video format
    is_valid_format, format_error = validate_video_format(str(file.filename))
    if not is_valid_format:
        logger.error(f"Invalid video format: {format_error}")
        raise HTTPException(status_code=400, detail=format_error)

    # Read file into memory for validation
    logger.info("Reading file into memory")
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(f"File size in memory: {file_size} bytes")
    
    file_stream = io.BytesIO(file_content)
    
    # Validate file size
    is_valid_size, size_error = await validate_file_with_streaming(file_stream)
    if not is_valid_size:
        logger.error(f"Invalid file size: {size_error}")
        raise HTTPException(status_code=400, detail=size_error)

    try:
        # Save video temporarily
        logger.info("Saving video to temporary location")
        success, file_path = await save_temp_video(file_stream, str(file.filename))
        if not success:
            logger.error(f"Failed to save video: {file_path}")
            raise HTTPException(status_code=500, detail=file_path)

        # Get transcript from video
        logger.info("Processing video for transcript")
        success, transcript = await process_video_for_transcript(file_path)
        if not success:
            logger.error(f"Failed to generate transcript: {transcript}")
            raise HTTPException(status_code=500, detail=transcript)
            
        # Generate release notes from transcript using OpenAIAgent with template
        logger.info("Generating release notes from transcript")
        openai_agent = OpenAIAgent()
        success, release_notes = await openai_agent.generate_release_notes_async(
            [io.BytesIO(transcript.encode())],
            ["transcript.txt"]
        )
        
        if not success:
            logger.error(f"Failed to generate release notes: {release_notes}")
            raise HTTPException(status_code=500, detail=release_notes)

        # Cleanup temporary file
        logger.info("Cleaning up temporary files")
        await cleanup_temp_video(file_path)

        logger.info("Video processing completed successfully")
        return {
            "message": "Video processed successfully",
            "transcript": transcript,
            "release_notes": release_notes,
            "token_usage": openai_agent.last_token_usage
        }

    except Exception as e:
        logger.error(f"Unexpected error processing video: {str(e)}")
        # Ensure cleanup in case of any error
        if 'file_path' in locals():
            await cleanup_temp_video(file_path)
        raise HTTPException(status_code=500, detail=str(e))
