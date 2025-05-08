from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from .utils.openai_agent import process_document_with_openai

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Release Notes Generator")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-release-notes")
async def generate_release_notes(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
            
        # Process the document with OpenAI
        result = await process_document_with_openai(content, file.filename)
        
        return {
            "success": True,
            "content": result
        }
        
    except Exception as e:
        logger.error(f"Error generating release notes: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to generate release notes: {str(e)}"
        }
