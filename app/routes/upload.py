from fastapi import APIRouter, UploadFile, File, HTTPException
import logging
import magic
import io

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'application/json': '.json'
}

@router.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset position
        
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
            
        # Read file content
        content = await file.read()
        
        # Check MIME type
        mime_type = magic.from_buffer(content, mime=True)
        if (mime_type not in ALLOWED_MIME_TYPES):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Allowed types: PDF, TXT, JSON"
            )
            
        # Create a BytesIO object to pass to the OpenAI agent
        file_obj = io.BytesIO(content)
        file_obj.name = file.filename  # Add name attribute for file type detection
            
        logger.info(f"File validated successfully: {file.filename}")
        return {"filename": file.filename, "file_obj": file_obj}
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
