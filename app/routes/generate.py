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

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize the agent
agent = OpenAIAgent()

@router.post("/generate-release-notes")
async def generate_release_notes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = None
):
    """Generate release notes from uploaded file"""
    if not file:
        return JSONResponse(
            content={"success": False, "message": "No file uploaded"},
            status_code=400
        )
    
    try:
        # Read file contents
        contents = await file.read()
        file_obj = io.BytesIO(contents)
        file_obj.name = file.filename
        
        # First get the original text content for database storage
        success, transcripts = agent.extract_text_from_memory(file_obj)
        if not success:
            return JSONResponse(
                content={"success": False, "message": "Failed to process file"},
                status_code=400
            )

        # Reset file pointer and generate notes
        file_obj.seek(0)
        
        try:
            success, result = await asyncio.wait_for(
                asyncio.create_task(agent.generate_release_notes_async(file_obj)),
                timeout=90.0  # 90 second timeout for generation
            )
        except asyncio.TimeoutError:
            logger.error("OpenAI API call timed out")
            return JSONResponse(
                content={
                    "success": False, 
                    "message": "The generation process took too long. Please try again."
                },
                status_code=504
            )
        
        if not success:
            return JSONResponse(
                content={"success": False, "message": result},
                status_code=400
            )
        
        if success and user_id:
            # Store in database
            try:
                now = datetime.utcnow()
                release = Release(
                    user_id=user_id,
                    transcripts=transcripts,
                    generated_release_notes=result,
                    generated_at=now
                )
                db.add(release)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to store in database: {str(e)}")
                # Continue even if database storage fails
        
        return JSONResponse(
            content={"success": True, "content": result},
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error in generate_release_notes: {str(e)}")
        return JSONResponse(
            content={"success": False, "message": "An unexpected error occurred"},
            status_code=500
        )
