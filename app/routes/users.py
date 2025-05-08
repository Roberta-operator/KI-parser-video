from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, Release
from app.auth import create_user, authenticate_user
from app.models import UserCreate, UserLogin
from typing import List
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import JSONResponse

router = APIRouter()

class ReleaseResponse(BaseModel):
    id: int
    transcripts: str
    generated_release_notes: str
    generated_at: datetime

# Register a new user
@router.post("/register/")
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        result = create_user(db, user.username, user.password)
        return JSONResponse(
            content={
                "success": True,
                "username": result.username,
                "user_id": result.id
            },
            status_code=200
        )
    except HTTPException as he:
        return JSONResponse(
            content={"success": False, "message": he.detail},
            status_code=he.status_code
        )

# Login user
@router.post("/login/")
def login(user: UserLogin, db: Session = Depends(get_db)):
    authenticated_user = authenticate_user(db, user.username, user.password)
    if not authenticated_user:
        return JSONResponse(
            content={"success": False, "message": "Invalid credentials"},
            status_code=401
        )
    return JSONResponse(
        content={
            "success": True,
            "message": "Login successful",
            "username": authenticated_user.username,
            "user_id": authenticated_user.id
        },
        status_code=200
    )

# Get user's releases
@router.get("/releases/{user_id}", response_model=List[ReleaseResponse])
def get_user_releases(user_id: int, db: Session = Depends(get_db)):
    try:
        releases = db.query(Release).filter(Release.user_id == user_id).all()
        return releases  # FastAPI will automatically convert this to JSON with the response_model
    except Exception as e:
        return JSONResponse(
            content={"success": False, "message": "Failed to retrieve releases"},
            status_code=500
        )
