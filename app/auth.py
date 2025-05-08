from fastapi import Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .database import get_db, User
import logging
import re

logger = logging.getLogger(__name__)

# Enhanced password settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Increased rounds for better security
)

def validate_password(password: str) -> bool:
    """
    Validate password strength
    - At least 8 characters
    - Contains uppercase and lowercase letters
    - Contains numbers
    - Contains special characters
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def create_user(db: Session, username: str, password: str):
    try:
        # Check if user already exists
        if db.query(User).filter(User.username == username).first():
            logger.warning(f"Attempted to create duplicate username: {username}")
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # Validate password strength
        if not validate_password(password):
            logger.warning(f"Weak password attempt for username: {username}")
            raise HTTPException(
                status_code=400, 
                detail="Password must be at least 8 characters and contain uppercase, lowercase, numbers, and special characters"
            )
        
        # Hash password and create user
        hashed_pw = pwd_context.hash(password)
        user = User(username=username, hashed_password=hashed_pw)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Successfully created new user: {username}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user {username}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

def authenticate_user(db: Session, username: str, password: str):
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"Login attempt with non-existent username: {username}")
            return False
        
        if not pwd_context.verify(password, user.hashed_password):
            logger.warning(f"Failed login attempt for user: {username}")
            return False
        
        logger.info(f"Successful login for user: {username}")
        return user
        
    except Exception as e:
        logger.error(f"Error during authentication for {username}: {str(e)}")
        return False
