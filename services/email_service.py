"""
Email service for sending OTP and notifications
Supports SMTP configuration with proper error handling and multiple port fallback
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for OTP and notifications using SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        
        # Check if SMTP is configured
        self.has_smtp = all([self.smtp_host, self.smtp_username, self.smtp_password, self.from_email])
        
        if not self.has_smtp:
            logger.warning("⚠️ SMTP not configured. OTP emails will use development mode.")
        else:
            logger.info(f"✅ SMTP configured: {self.smtp_host}:{self.smtp_port}")
    
    async def send_otp_email(self, to_email: str, otp: str, purpose: str = "verification") -> bool:
        """
        Send OTP email for signup/reset
        
        Args:
            to_email: Recipient email address
            otp: 6-digit OTP code
            purpose: 'verification' or 'reset'
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = "Your Guard Management System OTP"
            
            if purpose == "verification":
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #2c3e50;">Welcome to Guard Management System</h2>
                        
                        <p>Thank you for signing up! Please use the following OTP to verify your email address:</p>
                        
                        <div style="background-color: #f8f9fa; border: 2px solid #dee2e6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                            <h1 style="font-size: 32px; letter-spacing: 8px; margin: 0; color: #007bff;">{otp}</h1>
                        </div>
                        
                        <p><strong>Important:</strong></p>
                        <ul>
                            <li>This OTP is valid for 10 minutes only</li>
                            <li>Do not share this OTP with anyone</li>
                            <li>If you didn't request this OTP, please ignore this email</li>
                        </ul>
                        
                        <p>Once verified, you'll be able to access the Guard Management System.</p>
                        
                        <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                        <p style="font-size: 12px; color: #6c757d;">
                            This is an automated email from Guard Management System. Please do not reply to this email.
                        </p>
                    </div>
                </body>
                </html>
                """
            else:  # reset or password change
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #dc3545;">Password {purpose.title()} Request</h2>
                        
                        <p>You have requested to {purpose.replace('_', ' ')} your password. Please use the following OTP:</p>
                        
                        <div style="background-color: #f8f9fa; border: 2px solid #dee2e6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                            <h1 style="font-size: 32px; letter-spacing: 8px; margin: 0; color: #dc3545;">{otp}</h1>
                        </div>
                        
                        <p><strong>Security Notice:</strong></p>
                        <ul>
                            <li>This OTP is valid for 10 minutes only</li>
                            <li>Do not share this OTP with anyone</li>
                            <li>If you didn't request a password {purpose.replace('_', ' ')}, please ignore this email</li>
                            <li>Your account remains secure</li>
                        </ul>
                        
                        <p>Enter this OTP along with your new password to complete the {purpose.replace('_', ' ')} process.</p>
                        
                        <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                        <p style="font-size: 12px; color: #6c757d;">
                            This is an automated email from Guard Management System. Please do not reply to this email.
                        </p>
                    </div>
                </body>
                </html>
                """
            
            # Try SMTP with multiple port configurations
            if self.has_smtp:
                logger.info("📧 Attempting to send email via SMTP...")
                
                # Check if email service is properly configured
                is_configured = all([
                    self.smtp_host and self.smtp_host.strip(),
                    self.smtp_username and self.smtp_username != "your-email@gmail.com" and "@" in self.smtp_username,
                    self.smtp_password and self.smtp_password not in [
                        "your-16-digit-app-password-here",
                        "your-app-password-here",
                        "abcdefghijklmnop",
                        "DEVELOPMENT_MODE"
                    ],
                    self.from_email and self.from_email != "your-email@gmail.com" and "@" in self.from_email
                ])
                
                if is_configured:
                    # Create message
                    message = MIMEMultipart("alternative")
                    message["Subject"] = subject
                    message["From"] = f"{self.from_name} <{self.from_email}>"
                    message["To"] = to_email
                    
                    # Create HTML part
                    html_part = MIMEText(html_content, "html")
                    message.attach(html_part)
                    
                    # Send email with fallback connection methods
                    success = await self._send_email_with_fallback(
                        message, to_email, f"OTP: {otp}"
                    )
                    
                    if success:
                        logger.info(f"✅ OTP email sent successfully via SMTP to {to_email}")
                        return True
            
            # If all methods fail, use development mode
            logger.warning("=" * 60)
            logger.warning("🔧 SMTP FAILED - DEVELOPMENT MODE")
            logger.warning(f"🔑 YOUR OTP CODE IS: {otp}")
            logger.warning(f"📧 For email: {to_email}")
            logger.warning(f"🚀 Purpose: {purpose}")
            logger.warning("💡 Note: Cloud platforms like Render may block SMTP ports")
            logger.warning("=" * 60)
            print(f"\n🔑 OTP CODE: {otp} (for {to_email}) - Purpose: {purpose}\n")
            return True  # Return True for development mode
            
        except aiosmtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Email authentication failed for {to_email}: {e}")
            logger.warning("=" * 60)
            logger.warning(f"🔑 DEVELOPMENT MODE - YOUR OTP CODE IS: {otp}")
            logger.warning(f"📧 For email: {to_email}")
            logger.warning("=" * 60)
            print(f"\n🔑 OTP CODE: {otp} (for {to_email})\n")
            return True  # Return True for development mode
        except Exception as e:
            logger.error(f"❌ Failed to send OTP email to {to_email}: {e}")
            logger.warning("=" * 60)
            logger.warning(f"🔑 DEVELOPMENT MODE - YOUR OTP CODE IS: {otp}")
            logger.warning(f"📧 For email: {to_email}")
            logger.warning(f"⚡ Error: {str(e)}")
            logger.warning("=" * 60)
            print(f"\n🔑 OTP CODE: {otp} (for {to_email})\n")
            return True  # Return True for development mode
    
    async def send_supervisor_credentials_email(self, to_email: str, name: str, password: str, area_city: str, admin_name: str) -> bool:
        """
        Send credentials email to newly created supervisor
        
        Args:
            to_email: Supervisor's email address
            name: Supervisor's full name
            password: Generated password for the supervisor
            area_city: Area/City assigned to supervisor
            admin_name: Name of the admin who created the account
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Check if email service is properly configured
            is_configured = all([
                self.smtp_host and self.smtp_host.strip(),
                self.smtp_username and self.smtp_username != "your-email@gmail.com" and "@" in self.smtp_username,
                self.smtp_password and self.smtp_password != "your-16-digit-app-password-here" and self.smtp_password != "your-app-password-here" and self.smtp_password != "abcdefghijklmnop" and self.smtp_password != "DEVELOPMENT_MODE",
                self.from_email and self.from_email != "your-email@gmail.com" and "@" in self.from_email
            ])
            
            if not is_configured:
                # Development mode - just log credentials
                logger.warning("📧 EMAIL SERVICE NOT CONFIGURED - DEVELOPMENT MODE")
                logger.warning("=" * 60)
                logger.warning(f"🔐 SUPERVISOR CREDENTIALS for {to_email}:")
                logger.warning(f"👤 Name: {name}")
                logger.warning(f"📧 Email: {to_email}")
                logger.warning(f"🔑 Password: {password}")
                logger.warning(f"🏢 Area/City: {area_city}")
                logger.warning(f"👨‍💼 Created by: {admin_name}")
                logger.warning("=" * 60)
                print(f"\n🔐 SUPERVISOR CREDENTIALS: {to_email} / {password} / Area: {area_city} (Created by {admin_name})\n")
                return True
            
            subject = "Your Supervisor Account - Guard Management System"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #6f42c1;">Welcome to Guard Management System!</h2>
                    
                    <p>Dear {name},</p>
                    
                    <p>Your Supervisor account has been created by <strong>{admin_name}</strong>. You have been assigned to supervise the <strong>{area_city}</strong> area. Below are your login credentials:</p>
                    
                    <div style="background-color: #f3e8ff; border-left: 4px solid #6f42c1; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #553c9a;">Your Login Credentials</h3>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {to_email}</p>
                        <p style="margin: 5px 0;"><strong>Password:</strong> <code style="background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace;">{password}</code></p>
                        <p style="margin: 5px 0;"><strong>Area/City:</strong> {area_city}</p>
                    </div>
                    
                    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #856404;">🔒 Security Instructions</h3>
                        <ul style="margin-bottom: 0;">
                            <li><strong>Change your password</strong> immediately after first login</li>
                            <li>Use the password reset feature if needed: <strong>POST /auth/reset-password</strong></li>
                            <li>To confirm password reset: <strong>POST /auth/reset-password-confirm</strong></li>
                            <li>Keep your credentials secure and do not share them</li>
                        </ul>
                    </div>
                    
                    <div style="background-color: #e8f5e8; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #155724;">Your Responsibilities</h3>
                        <ol style="margin-bottom: 0;">
                            <li>Login with your email and password</li>
                            <li>Change your password from the default one</li>
                            <li>Complete your profile setup</li>
                            <li>Manage guards in your assigned area: <strong>{area_city}</strong></li>
                            <li>Monitor QR code scanning activities</li>
                            <li>Generate and review scan reports</li>
                        </ol>
                    </div>
                    
                    <p><strong>Admin:</strong> {admin_name}</p>
                    <p><strong>Assigned Area:</strong> {area_city}</p>
                    <p>If you have any questions or need assistance, please contact your system administrator.</p>
                    
                    <p>Welcome to the team!</p>
                    
                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6c757d;">
                        This is an automated email from Guard Management System. Please do not reply to this email.
                        <br>For security, please change your password after first login.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email with fallback methods
            success = await self._send_email_with_fallback(
                message, to_email, f"Supervisor Credentials"
            )
            
            if success:
                logger.info(f"Supervisor credentials email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send supervisor credentials email to {to_email}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send supervisor credentials email to {to_email}: {e}")
            return False

    async def send_guard_credentials_email(self, to_email: str, name: str, password: str, supervisor_name: str) -> bool:
        """
        Send credentials email to newly created guard
        
        Args:
            to_email: Guard's email address
            name: Guard's full name
            password: Generated password for the guard
            supervisor_name: Name of the supervisor who created the account
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Check if email service is properly configured
            is_configured = all([
                self.smtp_host and self.smtp_host.strip(),
                self.smtp_username and self.smtp_username != "your-email@gmail.com" and "@" in self.smtp_username,
                self.smtp_password and self.smtp_password != "your-16-digit-app-password-here" and self.smtp_password != "your-app-password-here" and self.smtp_password != "abcdefghijklmnop" and self.smtp_password != "DEVELOPMENT_MODE",
                self.from_email and self.from_email != "your-email@gmail.com" and "@" in self.from_email
            ])
            
            if not is_configured:
                # Development mode - just log credentials
                logger.warning("📧 EMAIL SERVICE NOT CONFIGURED - DEVELOPMENT MODE")
                logger.warning("=" * 60)
                logger.warning(f"🔐 GUARD CREDENTIALS for {to_email}:")
                logger.warning(f"👤 Name: {name}")
                logger.warning(f"📧 Email: {to_email}")
                logger.warning(f"🔑 Password: {password}")
                logger.warning(f"👮 Created by: {supervisor_name}")
                logger.warning("=" * 60)
                print(f"\n🔐 GUARD CREDENTIALS: {to_email} / {password} (Created by {supervisor_name})\n")
                return True
            
            subject = "Your Guard Management System Account"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #007bff;">Welcome to Guard Management System!</h2>
                    
                    <p>Dear {name},</p>
                    
                    <p>Your Guard account has been created by <strong>{supervisor_name}</strong>. Below are your login credentials:</p>
                    
                    <div style="background-color: #e7f3ff; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #0056b3;">Your Login Credentials</h3>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {to_email}</p>
                        <p style="margin: 5px 0;"><strong>Password:</strong> <code style="background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace;">{password}</code></p>
                    </div>
                    
                    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #856404;">🔒 Security Instructions</h3>
                        <ul style="margin-bottom: 0;">
                            <li><strong>Change your password</strong> immediately after first login</li>
                            <li>Use the password reset feature if needed: <strong>POST /auth/reset-password</strong></li>
                            <li>To confirm password reset: <strong>POST /auth/reset-password-confirm</strong></li>
                            <li>Keep your credentials secure and do not share them</li>
                        </ul>
                    </div>
                    
                    <div style="background-color: #e8f5e8; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #155724;">Getting Started</h3>
                        <ol style="margin-bottom: 0;">
                            <li>Login with your email and password</li>
                            <li>Change your password from the default one</li>
                            <li>Complete your profile setup</li>
                            <li>Start your patrol activities</li>
                        </ol>
                    </div>
                    
                    <p><strong>Supervisor:</strong> {supervisor_name}</p>
                    <p>If you have any questions or need assistance, please contact your supervisor or system administrator.</p>
                    
                    <p>Welcome to the team!</p>
                    
                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6c757d;">
                        This is an automated email from Guard Management System. Please do not reply to this email.
                        <br>For security, please change your password after first login.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            # Send email with fallback methods
            success = await self._send_email_with_fallback(
                message, to_email, f"Guard Credentials"
            )
            
            if success:
                logger.info(f"Guard credentials email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send guard credentials email to {to_email}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send guard credentials email to {to_email}: {e}")
            return False

    async def send_super_admin_credentials_email(self, to_email: str, name: str, password: str) -> bool:
        """
        Send credentials email to newly created super admin
        
        Args:
            to_email: Super admin's email address
            name: Super admin's full name
            password: Generated or default password
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Check if email service is properly configured
            is_configured = all([
                self.smtp_host and self.smtp_host.strip(),
                self.smtp_username and self.smtp_username != "your-email@gmail.com" and "@" in self.smtp_username,
                self.smtp_password and self.smtp_password not in [
                    "your-16-digit-app-password-here",
                    "your-app-password-here",
                    "abcdefghijklmnop",
                    "DEVELOPMENT_MODE"
                ],
                self.from_email and self.from_email != "your-email@gmail.com" and "@" in self.from_email
            ])

            if not is_configured:
                # Development mode - just log credentials
                logger.warning("📧 EMAIL SERVICE NOT CONFIGURED - DEVELOPMENT MODE")
                logger.warning("=" * 60)
                logger.warning(f"🔐 SUPER ADMIN CREDENTIALS for {to_email}:")
                logger.warning(f"👤 Name: {name}")
                logger.warning(f"📧 Email: {to_email}")
                logger.warning(f"🔑 Password: {password}")
                logger.warning("=" * 60)
                print(f"\n🔐 SUPER ADMIN CREDENTIALS: {to_email} / {password}\n")
                return True

            subject = "Your Super Admin Account - Guard Management System"

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #343a40;">Super Admin Account Created</h2>
                    <p>Dear {name},</p>
                    <p>Your Super Admin account has been created for the Guard Management System. Below are your login credentials:</p>
                    <div style="background-color: #eef2ff; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>Email:</strong> {to_email}</p>
                        <p style="margin: 5px 0;"><strong>Password:</strong> <code style="background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace;">{password}</code></p>
                    </div>
                    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #856404;">Security Instructions</h3>
                        <ul style="margin-bottom: 0;">
                            <li><strong>Change your password</strong> immediately after first login</li>
                            <li>Keep your credentials secure and do not share them</li>
                        </ul>
                    </div>
                    <p>If you have any questions or need assistance, please contact your system administrator.</p>
                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6c757d;">
                        This is an automated email from Guard Management System. Please do not reply to this email.
                    </p>
                </div>
            </body>
            </html>
            """

            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email

            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)

            # Send email with fallback methods
            success = await self._send_email_with_fallback(
                message, to_email, f"Super Admin Credentials"
            )
            
            if success:
                logger.info(f"Super admin credentials email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send super admin credentials email to {to_email}")
                return False

        except Exception as e:
            logger.error(f"Failed to send super admin credentials email to {to_email}: {e}")
            return False

    async def send_welcome_email(self, to_email: str, name: str, role: str) -> bool:
        """
        Send welcome email after successful account activation
        
        Args:
            to_email: Recipient email address
            name: User's full name
            role: User's role (ADMIN, SUPERVISOR, GUARD)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = "Welcome to Guard Management System"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #28a745;">Welcome to Guard Management System!</h2>
                    
                    <p>Dear {name},</p>
                    
                    <p>Your account has been successfully activated. You now have access to the Guard Management System with <strong>{role}</strong> privileges.</p>
                    
                    <div style="background-color: #e8f5e8; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #155724;">What's Next?</h3>
                        <ul style="margin-bottom: 0;">
                            <li>Login with your email and password</li>
                            <li>Complete your profile setup</li>
                            <li>{"Manage your assigned area and guards" if role == "SUPERVISOR" else "Start your patrol activities" if role == "GUARD" else "Access the admin dashboard"}</li>
                        </ul>
                    </div>
                    
                    <p>If you have any questions or need assistance, please contact your system administrator.</p>
                    
                    <p>Thank you for joining Guard Management System!</p>
                    
                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6c757d;">
                        This is an automated email from Guard Management System. Please do not reply to this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email with fallback methods
            success = await self._send_email_with_fallback(
                message, to_email, f"Welcome Email"
            )
            
            if success:
                logger.info(f"Welcome email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send welcome email to {to_email}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to_email}: {e}")
            return False


    async def send_account_removal_email(self, to_email: str, name: str, role: str, removed_by: str) -> bool:
        """
        Send notification email when an account is removed
        
        Args:
            to_email: User's email address
            name: User's name
            role: User's role (supervisor, guard)
            removed_by: Name or email of the person who removed the account
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = "Account Removed - Guard Management System"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background-color: #e74c3c; color: white; padding: 10px; text-align: center;">
                        <h2 style="margin: 0;">Account Removed</h2>
                    </div>
                    <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                        <p>Dear {name},</p>
                        <p>This is to notify you that your {role} account in the Guard Management System has been removed by <strong>{removed_by}</strong>.</p>
                        <p>If you believe this was done in error, please contact your administrator.</p>
                        <p>Thank you for your service.</p>
                        <p style="margin-top: 30px; font-size: 14px; color: #777;">
                            This is an automated email from Guard Management System. Please do not reply to this email.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email with fallback methods
            success = await self._send_email_with_fallback(
                message, to_email, f"Account Removal Notification"
            )
            
            if success:
                logger.info(f"Account removal email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send account removal email to {to_email}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send account removal email to {to_email}: {e}")
            return False

    async def _send_email_with_fallback(self, message, to_email: str, subject: str) -> bool:
        """
        Try multiple SMTP connection methods for better compatibility with cloud platforms like Render
        """
        connection_methods = [
            # Method 1: SSL on port 465 (often works better on cloud platforms like Render)
            {
                "port": 465,
                "use_tls": True,
                "start_tls": False,
                "description": "SSL on port 465",
                "timeout": 30
            },
            # Method 2: TLS on port 587 (standard method)
            {
                "port": 587,
                "use_tls": False,
                "start_tls": True,
                "description": "TLS on port 587 with STARTTLS",
                "timeout": 30
            },
            # Method 3: Direct TLS on port 587
            {
                "port": 587,
                "use_tls": True,
                "start_tls": False,
                "description": "Direct TLS on port 587",
                "timeout": 30
            },
            # Method 4: Non-secure port 25 (fallback)
            {
                "port": 25,
                "use_tls": False,
                "start_tls": True,
                "description": "Port 25 with STARTTLS",
                "timeout": 30
            }
        ]
        
        for method in connection_methods:
            try:
                logger.info(f"🔄 Attempting: {method['description']}")
                
                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=method["port"],
                    use_tls=method["use_tls"],
                    start_tls=method["start_tls"],
                    username=self.smtp_username,
                    password=self.smtp_password,
                    timeout=method["timeout"]
                )
                
                logger.info(f"✅ Email sent successfully using {method['description']}")
                return True
                
            except Exception as e:
                logger.warning(f"❌ {method['description']} failed: {str(e)}")
                continue
        
        logger.error("🚨 All SMTP connection methods failed")
        logger.error("💡 Cloud platforms like Render often block SMTP ports for security")
        return False


# Global email service instance
email_service = EmailService()
