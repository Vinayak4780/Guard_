"""
Authentication routes for Email-OTP signup and verification
Supports signup with email verification and password reset
"""

from fastapi import APIRouter, HTTPException, status, Depends, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from bson import ObjectId

# Import services and dependencies
from services.jwt_service import jwt_service
from services.email_service import email_service
from services.auth_service import get_current_user
from database import (
    get_users_collection, get_supervisors_collection, get_guards_collection,
    get_otp_tokens_collection
)
from config import settings

# Import models
from models import (
    SignupRequest, VerifyOTPRequest, LoginRequest,
    ResetPasswordRequest, ResetPasswordConfirmRequest,
    SuccessResponse, UserResponse,
    UserRole, OTPPurpose
)

logger = logging.getLogger(__name__)

# Create router
auth_router = APIRouter()

















@auth_router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """
    OAuth2 compatible login with username (email or phone) and password
    Dynamically queries the correct collection based on the role.
    """
    try:
        print(f"🔍 LOGIN ATTEMPT: username={username}")
        
        # Get database collections
        try:
            users_collection = get_users_collection()
            supervisors_collection = get_supervisors_collection()
            guards_collection = get_guards_collection()
            print(f"✅ Collections retrieved successfully")
        except Exception as e:
            print(f"❌ Error getting collections: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error"
            )

        if users_collection is None or supervisors_collection is None or guards_collection is None:
            print(f"❌ One or more collections is None")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database collections not available"
            )

        # Check in users collection (admins) first
        print(f"🔍 Searching in users collection for admin...")
        try:
            user = await users_collection.find_one({"$or": [{"email": username}, {"phone": username}]})
            if user:
                print(f"✅ User found in users collection")
                role = user.get("role", "ADMIN")
            else:
                print(f"❌ Admin user not found in users collection")
                # Check in supervisors collection
                print(f"🔍 Searching in supervisors collection...")
                user = await supervisors_collection.find_one({"$or": [{"email": username}, {"phone": username}]})
                if user:
                    print(f"✅ Supervisor found in supervisors collection")
                    role = "SUPERVISOR"
                else:
                    print(f"❌ Supervisor not found in supervisors collection")
                    # Check in guards collection
                    print(f"🔍 Searching in guards collection...")
                    user = await guards_collection.find_one({"$or": [{"email": username}, {"phone": username}]})
                    if user:
                        print(f"✅ Guard found in guards collection")
                        role = "GUARD"
                    else:
                        print(f"❌ User not found in any collection")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid email/phone or password"
                        )
        except Exception as e:
            print(f"❌ Database query error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database query failed: {str(e)}"
            )

        # Verify password
        print(f"🔍 Verifying password...")
        password_hash = user.get("passwordHash")
        if not password_hash:
            print(f"❌ No passwordHash field found in user document")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User data corrupted - missing password"
            )
        
        # Debug information
        print(f"🔍 Password length: {len(password)} characters")
        print(f"🔍 Password bytes length: {len(password.encode('utf-8'))} bytes")
        print(f"🔍 Hash format looks valid: {password_hash.startswith('$2b$')}")
        
        print(f"🔍 Attempting password verification...")
        print(f"🔍 Hash preview: {password_hash[:20]}...")
        
        password_valid = jwt_service.verify_password(password, password_hash)
        if not password_valid:
            print(f"❌ Password verification failed")
            # Try one more debug attempt with a simple test
            print(f"🔍 Testing with empty password as debug...")
            debug_result = jwt_service.verify_password("", password_hash)
            print(f"🔍 Debug empty password result: {debug_result}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/phone or password"
            )
        print(f"✅ Password verification succeeded")

        # Check if user is active
        print(f"🔍 Checking if user is active...")
        if not user.get("isActive", False):
            print(f"❌ User account is not active")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account not activated. Please contact the administrator."
            )
        print(f"✅ User account is active")

        # Update last login
        print(f"🔍 Updating last login...")
        try:
            collection = {
                "ADMIN": users_collection,
                "SUPERVISOR": supervisors_collection,
                "GUARD": guards_collection
            }[role]
            await collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"lastLogin": datetime.utcnow()}}
            )
            user["lastLogin"] = datetime.utcnow()
            print(f"✅ Last login updated")
        except Exception as e:
            print(f"❌ Failed to update last login: {e}")
            # Continue anyway, this is not critical

        # Create JWT access token
        print(f"🔍 Creating JWT access token...")
        try:
            access_token = jwt_service.create_access_token({
                "user_id": str(user["_id"]),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "role": role
            })
            print(f"✅ JWT token created successfully")
        except Exception as e:
            print(f"❌ JWT token creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token creation failed: {str(e)}"
            )

        # Return OAuth2 compatible response
        print(f"✅ Login successful for {role} user")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user["_id"]),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "name": user["name"],
                "role": role,
                "areaCity": user.get("areaCity"),
                "isActive": user["isActive"],
                "lastLogin": user.get("lastLogin")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ CRITICAL LOGIN ERROR: {e}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during login: {str(e)}"
        )














