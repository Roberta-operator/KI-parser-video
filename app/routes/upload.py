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
    # Validate video format
    is_valid_format, format_error = validate_video_format(file.filename)
    if not is_valid_format:
        raise HTTPException(status_code=400, detail=format_error)

    # Read file into memory for validation
    file_content = await file.read()
    file_stream = io.BytesIO(file_content)

    # Validate file size
    is_valid_size, size_error = await validate_file_with_streaming(file_stream)
    if not is_valid_size:
        raise HTTPException(status_code=400, detail=size_error)

    try:
        # Save video temporarily
        success, file_path = await save_temp_video(file_stream, file.filename)
        if not success:
            raise HTTPException(status_code=500, detail=file_path)

        # Get transcript from video
        success, transcript = await process_video_for_transcript(file_path)
        if not success:
            raise HTTPException(status_code=500, detail=transcript)        # Generate release notes from transcript using OpenAIAgent for consistency
        openai_agent = OpenAIAgent()
        success, release_notes = await openai_agent.generate_release_notes_async(
            io.BytesIO(transcript.encode()),
            "transcript.txt"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=release_notes)

        # Cleanup temporary file
        await cleanup_temp_video(file_path)

        return {
            "message": "Video processed successfully",
            "transcript": transcript,
            "release_notes": release_notes,
            "token_usage": openai_agent.last_token_usage  # Include token usage from the release notes generation
        }

    except Exception as e:
        # Ensure cleanup in case of any error
        if 'file_path' in locals():
            await cleanup_temp_video(file_path)
        raise HTTPException(status_code=500, detail=str(e))
