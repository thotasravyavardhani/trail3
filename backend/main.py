"""
QuMail Secure Email Client - Main FastAPI Application
Quantum-secure email client with OTP, AES-256-GCM, and PQC encryption
"""

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from typing import List, Optional
from contextlib import asynccontextmanager
import logging
import asyncio
import json
import os

from db import get_db, init_db
from models import User, Email, Attachment
from crypto_utils import CryptoManager
from email_service import EmailService
from km_mock import KeyManagerMock
from logger import setup_logger

# Initialize services
crypto_manager = CryptoManager()
km_mock = KeyManagerMock()
email_service = EmailService()
logger = setup_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    await init_db()
    await km_mock.start()
    logger.info("QuMail backend started successfully")
    
    yield
    
    # Shutdown
    await km_mock.stop()
    logger.info("QuMail backend shutdown")

# Initialize FastAPI app
app = FastAPI(
    title="QuMail Secure Email Client",
    description="Quantum-secure email client with end-to-end encryption",
    version="1.0.0",
    lifespan=lifespan
)

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": f"Validation error: {exc.errors()}"}
    )

# CORS middleware for React frontend - Allow all origins for Replit proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Auth endpoints
@app.post("/api/auth/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    imap_server: str = Form(...),
    smtp_server: str = Form(...),
    imap_port: int = Form(default=993),
    smtp_port: int = Form(default=587),
    db: Session = Depends(get_db)
):
    """Authenticate user with email provider and KM"""
    try:
        logger.info(f"Login attempt for email: {email}, imap_server: {imap_server}, smtp_server: {smtp_server}")
        # Validate email credentials
        email_validated = await email_service.validate_credentials(
            email, password, imap_server, smtp_server, imap_port, smtp_port
        )
        
        if not email_validated:
            raise HTTPException(status_code=401, detail="Invalid email credentials")
        
        # Authenticate with KM
        km_session = await km_mock.authenticate(email)
        
        # Create or get user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                imap_server=imap_server,
                smtp_server=smtp_server,
                imap_port=imap_port,
                smtp_port=smtp_port,
                km_session_id=km_session["session_id"]
            )
            db.add(user)
            db.commit()
        
        # Generate JWT token
        token = crypto_manager.generate_jwt_token(str(user.email))
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "email": user.email,
                "km_session_id": user.km_session_id
            }
        }
        
    except Exception as e:
        logger.error(f"Login failed for {email}: {str(e)}")
        import traceback
        logger.error(f"Login traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.get("/api/auth/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current authenticated user"""
    try:
        payload = crypto_manager.verify_jwt_token(credentials.credentials)
        email = payload.get("sub")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"email": user.email, "km_session_id": user.km_session_id}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# Email endpoints
@app.get("/api/emails/inbox")
async def get_inbox(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Fetch and decrypt inbox emails"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        # Fetch emails from IMAP
        emails = await email_service.fetch_inbox(user_obj)
        
        # Decrypt emails
        decrypted_emails = []
        for email_data in emails:
            try:
                # Get KM key if needed
                km_key = None
                if email_data.get("encryption_mode") in ["OTP", "AES"] and user_obj and user_obj.km_session_id:
                    km_key = await km_mock.get_key(str(user_obj.km_session_id))
                
                # Decrypt email
                decrypted = await crypto_manager.decrypt_email(
                    email_data, km_key
                )
                decrypted_emails.append(decrypted)
                
            except Exception as e:
                logger.error(f"Failed to decrypt email {email_data.get('uid', 'unknown')}: {str(e)}")
                # Add with error status
                email_data["decryption_status"] = "error"
                email_data["decryption_error"] = "Failed to decrypt"
                decrypted_emails.append(email_data)
        
        return {"emails": decrypted_emails}
        
    except Exception as e:
        logger.error(f"Failed to fetch inbox: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch inbox")

@app.get("/api/emails/sent")
async def get_sent(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Fetch sent emails"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        emails = await email_service.fetch_sent(user_obj)
        return {"emails": emails}
        
    except Exception as e:
        logger.error(f"Failed to fetch sent emails: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sent emails")

@app.get("/api/emails/outbox")
async def get_outbox(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Fetch outbox (queued) emails"""
    try:
        user = await get_current_user(credentials, db)
        
        # Get queued emails from database
        emails = db.query(Email).filter(
            Email.sender == user["email"],
            Email.status == "queued"
        ).all()
        
        return {"emails": [email.to_dict() for email in emails]}
        
    except Exception as e:
        logger.error(f"Failed to fetch outbox: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch outbox")

@app.post("/api/emails/compose")
async def compose_email(
    to: str = Form(...),
    cc: str = Form(""),
    bcc: str = Form(""),
    subject: str = Form(...),
    body: str = Form(...),
    encryption_mode: str = Form("AES"),
    attachments: List[UploadFile] = File(default=[]),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Compose and send encrypted email"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        # Get KM key if needed
        km_key = None
        if encryption_mode in ["OTP", "AES"] and user_obj and user_obj.km_session_id:
            km_key = await km_mock.get_key(str(user_obj.km_session_id))
        
        # Process attachments
        attachment_data = []
        for attachment in attachments:
            if attachment.filename:
                content = await attachment.read()
                attachment_data.append({
                    "filename": attachment.filename,
                    "content": content,
                    "content_type": attachment.content_type
                })
        
        # Encrypt email
        encrypted_email = await crypto_manager.encrypt_email(
            {
                "to": to,
                "cc": cc,
                "bcc": bcc,
                "subject": subject,
                "body": body,
                "attachments": attachment_data
            },
            encryption_mode,
            km_key
        )
        
        # Send email
        success = await email_service.send_email(user_obj, encrypted_email)
        
        if success:
            # Save to sent folder
            await email_service.save_to_sent(user_obj, encrypted_email)
            return {"status": "sent", "message": "Email sent successfully"}
        else:
            # Save to outbox for retry
            email_record = Email(
                sender=str(user_obj.email) if user_obj and user_obj.email else "",
                recipients=to,
                subject=subject,
                body=encrypted_email["body"],
                encryption_mode=encryption_mode,
                status="queued"
            )
            db.add(email_record)
            db.commit()
            return {"status": "queued", "message": "Email queued for retry"}
            
    except Exception as e:
        logger.error(f"Failed to compose email: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send email")

@app.post("/api/emails/retry-outbox")
async def retry_outbox(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Retry sending queued emails"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        # Get queued emails
        queued_emails = db.query(Email).filter(
            Email.sender == user["email"],
            Email.status == "queued"
        ).all()
        
        sent_count = 0
        for email in queued_emails:
            try:
                success = await email_service.send_email(user_obj, email.to_dict())
                if success:
                    setattr(email, 'status', 'sent')
                    sent_count += 1
            except Exception as e:
                logger.error(f"Failed to retry email {email.id}: {str(e)}")
        
        db.commit()
        return {"sent_count": sent_count, "total_queued": len(queued_emails)}
        
    except Exception as e:
        logger.error(f"Failed to retry outbox: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry outbox")

# Settings endpoints
@app.get("/api/settings")
async def get_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get user settings"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        default_encryption = "AES"
        km_endpoint = "http://localhost:8001"
        auto_decrypt = True
        
        if user_obj:
            if hasattr(user_obj, 'default_encryption_mode') and user_obj.default_encryption_mode:
                default_encryption = str(user_obj.default_encryption_mode)
            if hasattr(user_obj, 'km_endpoint') and user_obj.km_endpoint:
                km_endpoint = str(user_obj.km_endpoint)
            if hasattr(user_obj, 'auto_decrypt') and user_obj.auto_decrypt is not None:
                auto_decrypt = bool(user_obj.auto_decrypt)
        
        return {
            "default_encryption": default_encryption,
            "km_endpoint": km_endpoint,
            "auto_decrypt": auto_decrypt
        }
        
    except Exception as e:
        logger.error(f"Failed to get settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get settings")

@app.post("/api/settings")
async def update_settings(
    default_encryption: str = Form(...),
    km_endpoint: str = Form(...),
    auto_decrypt: bool = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    try:
        user = await get_current_user(credentials, db)
        user_obj = db.query(User).filter(User.email == user["email"]).first()
        
        setattr(user_obj, 'default_encryption_mode', default_encryption)
        setattr(user_obj, 'km_endpoint', km_endpoint)
        setattr(user_obj, 'auto_decrypt', auto_decrypt)
        
        db.commit()
        return {"message": "Settings updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update settings")

# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    km_status = await km_mock.health_check()
    return {
        "status": "healthy",
        "km_status": km_status,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)