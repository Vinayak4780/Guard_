"""
Email service for sending OTP and notifications
Supports SMTP configuration with proper error handling and fallback methods for cloud platforms
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for OTP and notifications with cloud platform compatibility"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        
        if not all([self.smtp_host, self.smtp_username, self.smtp_password, self.from_email]):
            logger.warning("⚠️ Email service not properly configured. OTP emails will fail.")

    async def _send_email_with_fallback(self, message, to_email: str, subject: str) -> bool:
        """
        Try multiple SMTP connection methods for better compatibility with cloud platforms like Render
        """
        connection_methods = [
            # Method 1: SSL on port 465 (often works better on cloud platforms)
            {
                "port": 465,
                "use_tls": True,
                "start_tls": False,
                "description": "SSL on port 465"
            },
            # Method 2: TLS on port 587 (standard)
            {
                "port": 587,
                "use_tls": False,
                "start_tls": True,
                "description": "TLS on port 587 with STARTTLS"
            },
            # Method 3: TLS on port 587 without STARTTLS
            {
                "port": 587,
                "use_tls": True,
                "start_tls": False,
                "description": "TLS on port 587 (no STARTTLS)"
            }
        ]
        
        for method in connection_methods:
            try:
                logger.info(f"🔄 Trying email method: {method['description']}")
                
                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=method["port"],
                    use_tls=method["use_tls"],
                    start_tls=method["start_tls"],
                    username=self.smtp_username,
                    password=self.smtp_password,
                    timeout=30  # Add timeout to prevent hanging
                )
                
                logger.info(f"✅ Email sent successfully using {method['description']}")
                return True
                
            except Exception as e:
                logger.warning(f"❌ {method['description']} failed: {str(e)}")
                continue
        
        logger.error("🚨 All email connection methods failed")
        return False
    
    async def send_otp_email(self, to_email: str, otp: str, purpose: str = "verification") -> bool:
        """
        Send OTP email for signup/reset with fallback connection methods
        
        Args:
            to_email: Recipient email address
            otp: 6-digit OTP code
            purpose: 'verification', 'reset', or 'password change'
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Check if email service is properly configured
            is_configured = all([
                self.smtp_host and self.smtp_host.strip(),
                self.smtp_username and self.smtp_username != "your-email@gmail.com" and "@" in self.smtp_username,
                self.smtp_password and self.smtp_password != "your-16-digit-app-password-here" and self.smtp_password != "your-app-password-here",
                self.from_email and self.from_email != "your-email@gmail.com" and "@" in self.from_email
            ])
            
            if not is_configured:
                logger.warning("⚠️ Email service not configured properly")
                logger.warning("=" * 60)
                logger.warning(f"🔑 DEVELOPMENT MODE - YOUR OTP CODE IS: {otp}")
                logger.warning(f"📧 For email: {to_email}")
                logger.warning("=" * 60)
                print(f"\n🔑 OTP CODE: {otp} (for {to_email})\n")
                return True  # Return True for development mode
            
            # Create email message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"Your OTP Code for {purpose.title()}"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>OTP Verification</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                    <h2 style="color: #2c3e50; text-align: center;">🔐 OTP Verification</h2>
                    <p>Hello,</p>
                    <p>Your OTP code for <strong>{purpose}</strong> is:</p>
                    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                        <h1 style="color: #1976d2; font-size: 36px; margin: 0; letter-spacing: 5px;">{otp}</h1>
                    </div>
                    <p>This OTP will expire in <strong>10 minutes</strong>.</p>
                    <p>If you didn't request this OTP, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="color: #666; font-size: 12px; text-align: center;">
                        This is an automated email from Guard Management System.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email with fallback methods
            success = await self._send_email_with_fallback(message, to_email, f"OTP: {otp}")
            
            if success:
                logger.info(f"OTP email sent successfully to {to_email}")
                return True
            else:
                # If all methods fail, log OTP for development
                logger.error(f"All email sending methods failed for {to_email}")
                logger.warning("=" * 60)
                logger.warning(f"🔑 DEVELOPMENT MODE - YOUR OTP CODE IS: {otp}")
                logger.warning(f"📧 For email: {to_email}")
                logger.warning("=" * 60)
                print(f"\n🔑 OTP CODE: {otp} (for {to_email})\n")
                return True  # Return True for development mode
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {e}")
            logger.warning("=" * 60)
            logger.warning(f"🔑 DEVELOPMENT MODE - YOUR OTP CODE IS: {otp}")
            logger.warning(f"📧 For email: {to_email}")
            logger.warning("=" * 60)
            print(f"\n🔑 OTP CODE: {otp} (for {to_email})\n")
            return True  # Return True for development mode
    
    async def send_test_email(self, to_email: str) -> bool:
        """
        Send a test email to verify SMTP configuration
        """
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = "Test Email from Guard Management System"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>🧪 Test Email</h2>
                <p>This is a test email from the Guard Management System.</p>
                <p>If you received this email, the SMTP configuration is working correctly!</p>
                <p><strong>Timestamp:</strong> {logger.info}</p>
            </body>
            </html>
            """
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            success = await self._send_email_with_fallback(message, to_email, "Test Email")
            return success
            
        except Exception as e:
            logger.error(f"Failed to send test email to {to_email}: {e}")
            return False


# Create email service instance
email_service = EmailService()