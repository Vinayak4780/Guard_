"""
Debug endpoint for troubleshooting email issues on Render
Add this to your main.py or create a separate debug route
"""

from fastapi import APIRouter, HTTPException, status, Depends
from services.email_service import email_service
from services.auth_service import get_current_super_admin
from config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
debug_router = APIRouter()

@debug_router.get("/debug/email-config")
async def debug_email_config(
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    DEBUG: Check email configuration (Super Admin only)
    Use this to troubleshoot email issues on Render
    """
    try:
        # Check environment variables (masked for security)
        config_status = {
            "smtp_host": settings.SMTP_HOST if settings.SMTP_HOST else "❌ NOT SET",
            "smtp_port": settings.SMTP_PORT if settings.SMTP_PORT else "❌ NOT SET",
            "smtp_username": f"{settings.SMTP_USERNAME[:3]}***{settings.SMTP_USERNAME[-8:]}" if settings.SMTP_USERNAME else "❌ NOT SET",
            "smtp_password": "✅ SET" if settings.SMTP_PASSWORD else "❌ NOT SET",
            "smtp_from_email": settings.SMTP_FROM_EMAIL if settings.SMTP_FROM_EMAIL else "❌ NOT SET",
            "smtp_from_name": settings.SMTP_FROM_NAME if settings.SMTP_FROM_NAME else "❌ NOT SET"
        }
        
        # Check email service initialization
        email_service_status = {
            "host": email_service.smtp_host,
            "port": email_service.smtp_port,
            "username_set": bool(email_service.smtp_username),
            "password_set": bool(email_service.smtp_password),
            "from_email": email_service.from_email,
            "from_name": email_service.from_name
        }
        
        return {
            "message": "Email configuration debug info",
            "environment_variables": config_status,
            "email_service": email_service_status,
            "tips": [
                "Check if all environment variables are set in Render dashboard",
                "Verify Gmail App Password is correct (16 characters)",
                "Ensure 2FA is enabled on Gmail account",
                "Check Render logs for SMTP connection errors"
            ]
        }
        
    except Exception as e:
        logger.error(f"Debug email config error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug failed: {str(e)}"
        )


@debug_router.post("/debug/test-email")
async def test_email_sending(
    test_email: str,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    DEBUG: Test email sending (Super Admin only)
    Send a test OTP to verify email functionality on Render
    """
    try:
        logger.info(f"🧪 Testing email send to: {test_email}")
        
        # Try sending a test OTP
        test_otp = "123456"
        result = await email_service.send_otp_email(test_email, test_otp, "test")
        
        if result:
            logger.info(f"✅ Test email sent successfully to {test_email}")
            return {
                "message": f"Test email sent successfully to {test_email}",
                "result": True,
                "otp_sent": test_otp
            }
        else:
            logger.error(f"❌ Test email failed to send to {test_email}")
            return {
                "message": f"Test email failed to send to {test_email}",
                "result": False,
                "tip": "Check Render logs for SMTP errors"
            }
            
    except Exception as e:
        logger.error(f"Test email error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test email failed: {str(e)}"
        )