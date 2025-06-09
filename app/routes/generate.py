from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, BackgroundTasks
from app.utils.openai_agent import OpenAIAgent
from app.database import get_db, Release
from sqlalchemy.orm import Session
from datetime import datetime
import os
import io
import logging
import asyncio
from fastapi.responses import JSONResponse
from typing import List

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize the agent
agent = OpenAIAgent()

# Maximum file size in bytes (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  

@router.post("/generate-release-notes")
async def generate_release_notes(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user_id: int = None
):
    """Generate release notes from uploaded files"""
    try:
        combined_content = ""

        for file in files:
            logger.info(f"Starting to process file: {file.filename}")

            # Check file size
            file.file.seek(0, 2)  # Seek to end of file
            file_size = file.file.tell()
            file.file.seek(0)  # Reset file position

            logger.info(f"File size: {file_size / 1024 / 1024:.2f}MB")

            if file_size > MAX_FILE_SIZE:
                logger.warning(f"File size too large: {file_size / 1024 / 1024:.2f}MB")
                raise HTTPException(
                    status_code=400,
                    detail=f"File size too large for file {file.filename}. Maximum allowed size is 100MB"
                )

            # Verify file type
            file_extension = file.filename.split('.')[-1].lower()
            logger.info(f"File extension: {file_extension}")

            if file_extension not in ['txt', 'pdf', 'docx', 'doc']:
                logger.warning(f"Unsupported file type: {file_extension}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type for file {file.filename}"
                )

            # Create a copy of the file in memory
            logger.info("Creating memory copy of file")
            file_copy = io.BytesIO()
            contents = await file.read()
            file_copy.write(contents)
            file_copy.seek(0)

            # Extract content and combine
            openai_agent = OpenAIAgent()
            success, content = openai_agent.extract_text_from_memory(file_copy, file.filename)
            if not success:
                logger.error(f"Failed to extract content from file: {file.filename}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract content from file: {file.filename}"
                )

            combined_content += content + "\n\n"

        # Generate release notes from combined content
        logger.info("Generating release notes from combined content")

        success, result = await openai_agent.generate_release_notes_async(
            [io.BytesIO(combined_content.encode('utf-8'))],
            ["combined_content.txt"]
        )

        if not success:
            logger.error(f"OpenAI agent failed to generate release notes: {result}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate release notes: {result}"
            )

        logger.info("Successfully generated release notes")

        if success and user_id:
            # Store in database
            try:
                logger.info(f"Storing results in database for user_id: {user_id}")
                now = datetime.utcnow()
                release = Release(
                    user_id=user_id,
                    transcripts=combined_content,
                    generated_release_notes=result,
                    generated_at=now
                )
                db.add(release)
                db.commit()
                logger.info("Successfully stored in database")
            except Exception as e:
                logger.error(f"Failed to store in database: {str(e)}", exc_info=True)
                # Continue even if database storage fails

        return {
            "success": True,
            "content": result,
            "token_usage": openai_agent.last_token_usage  # Include token usage in response
        }

    except HTTPException as http_error:
        logger.error(f"HTTP error generating release notes: {str(http_error.detail)}")
        raise http_error
    except Exception as e:
        error_msg = f"Unexpected error generating release notes: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
