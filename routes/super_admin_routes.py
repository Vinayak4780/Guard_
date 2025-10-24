"""
Super Admin routes for managing state-wise admins
SUPER_ADMIN role only - manage state-wise admins and system configuration
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from bson import ObjectId

# Import services and dependencies
from services.auth_service import get_current_super_admin
from services.jwt_service import jwt_service
from services.email_service import email_service
from services.perplexity_service import perplexity_service
from database import get_users_collection, get_scan_events_collection, get_guards_collection, get_supervisors_collection, get_otp_tokens_collection
from config import settings

# Import models
from models import (
    SuperAdminAddAdminRequest, StateAdminResponse, SuperAdminChangePasswordRequest, 
    ChangePasswordRequest, UserSearchRequest, UserSearchResponse, SuperAdminChangeOwnPasswordRequest,
    OTPPurpose, WeatherForecastRequest, WeatherForecastResponse,
    SiteNewsIntelligenceRequest, SiteNewsIntelligenceResponse
)

logger = logging.getLogger(__name__)

# Create router
super_admin_router = APIRouter()




# ============================================================================
# SUPER ADMIN: Add State-wise Admin API
# ============================================================================

@super_admin_router.post("/add-admin")
async def add_state_admin(
    admin_data: SuperAdminAddAdminRequest,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Add a new state-wise admin to the system
    Creates admin account with state assignment (one admin per state)
    """
    try:
        users_collection = get_users_collection()

        if users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        super_admin_id = str(current_super_admin["_id"])
        super_admin_name = current_super_admin.get("name", current_super_admin.get("email", "Super Admin"))

        # Check contact methods provided
        has_email = admin_data.email and admin_data.email.strip()
        has_phone = admin_data.phone and admin_data.phone.strip()
        
        if not has_email and not has_phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least email or phone must be provided"
            )

        # Check if admin already exists for this state
        existing_admin = await users_collection.find_one({
            "role": "ADMIN",
            "state": admin_data.state
        })

        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Admin already exists for state '{admin_data.state}'. Only one admin per state is allowed."
            )

        # Check if email/phone already exists
        or_conditions = []
        
        if has_email:
            or_conditions.append({"email": admin_data.email.strip()})
        
        if has_phone:
            or_conditions.append({"phone": admin_data.phone.strip()})
        
        if or_conditions:
            existing_user = await users_collection.find_one({
                "$or": or_conditions
            })

            if existing_user:
                if has_email and existing_user.get("email") == admin_data.email.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"User with email {admin_data.email} already exists"
                    )
                elif has_phone and existing_user.get("phone") == admin_data.phone.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"User with phone {admin_data.phone} already exists"
                    )

        # Hash the password
        hashed_password = jwt_service.hash_password(admin_data.password)

        # Create admin record
        admin_record = {
            "name": admin_data.name,
            "role": "ADMIN",
            "state": admin_data.state,
            "isActive": True,
            "isEmailVerified": True,  # Admin is pre-verified
            "createdBy": super_admin_id,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            "passwordHash": hashed_password
        }

        # Add email or phone to admin record (only if not empty)
        if has_email:
            admin_record["email"] = admin_data.email.strip()
        if has_phone:
            admin_record["phone"] = admin_data.phone.strip()

        # Insert admin
        admin_result = await users_collection.insert_one(admin_record)

        # Construct response
        response_admin = {
            "id": str(admin_result.inserted_id),
            "name": admin_data.name,
            "state": admin_data.state,
            "createdBy": super_admin_name
        }
        
        # Add email and phone only if they were provided
        if has_email:
            response_admin["email"] = admin_data.email.strip()
        if has_phone:
            response_admin["phone"] = admin_data.phone.strip()
        
        logger.info(f"Super admin {super_admin_name} created state admin for {admin_data.state}: {admin_data.name}")
        
        return {
            "message": "State-wise admin added successfully",
            "admin": response_admin
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding state admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add state admin: {str(e)}"
        )


# ============================================================================
# SUPER ADMIN: List State-wise Admins API
# ============================================================================

@super_admin_router.get("/state-admins")
async def list_state_admins(
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: List all state-wise admins in the system
    """
    try:
        users_collection = get_users_collection()
        
        if users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Get all admins
        admins_cursor = users_collection.find({"role": "ADMIN"}).sort("createdAt", -1)
        
        admins = []
        async for admin in admins_cursor:
            admin_data = {
                "id": str(admin["_id"]),
                "name": admin.get("name", "Unknown"),
                "email": admin.get("email"),
                "phone": admin.get("phone"),
                "state": admin.get("state", "Unknown State"),
                "isActive": admin.get("isActive", True),
                "createdAt": admin.get("createdAt"),
                "updatedAt": admin.get("updatedAt"),
                "lastLogin": admin.get("lastLogin"),
                "createdBy": admin.get("createdBy", "System")
            }
            admins.append(admin_data)
        
        return {
            "admins": admins,
            "total": len(admins)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing state admins: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list state admins: {str(e)}"
        )


# ============================================================================
# SUPER ADMIN: Delete State-wise Admin API
# ============================================================================

@super_admin_router.delete("/delete-admin")
async def delete_state_admin(
    name: str,
    area: str,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Delete a state-wise admin from the system by name and area
    """
    try:
        users_collection = get_users_collection()

        if users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Clean inputs
        name = name.strip()
        area = area.strip()

        # Build search criteria
        search_criteria = {
            "role": "ADMIN",
            "name": name,
            "state": area
        }

        # Find admin by name and area
        admin = await users_collection.find_one(search_criteria)

        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"State admin with name '{name}' in area '{area}' not found"
            )

        admin_id = str(admin["_id"])
        admin_name = admin.get("name", "Unknown")
        admin_state = admin.get("state", "Unknown State")

        # Delete admin
        admin_result = await users_collection.delete_one({"_id": admin["_id"]})

        if admin_result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete admin"
            )

        logger.info(f"Super admin {current_super_admin.get('email')} deleted state admin {admin_id} ({admin_name}, area: {area}, {admin_state})")

        return {
            "message": "State admin deleted successfully",
            "admin_id": admin_id,
            "name": admin_name,
            "area": area,
            "state": admin_state
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting state admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete state admin: {str(e)}"
        )



# ============================================================================
# SUPER ADMIN: Area-wise Excel Reports (mirrors admin endpoint)
# ============================================================================

from fastapi import Query

@super_admin_router.get("/excel/area-wise-reports")
async def super_admin_get_area_wise_excel_reports(
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin),
    days_back: int = Query(7, ge=1, le=30, description="Number of days to include in report"),
    area: Optional[str] = Query(None, description="Specific area/state to filter (optional)"),
    site: Optional[str] = Query(None, description="Name of the site to filter (optional)")
):
    """
    Generate area-wise Excel reports for all areas or a specific area (SUPER_ADMIN)
    """
    try:
        scan_events_collection = get_scan_events_collection()
        guards_collection = get_guards_collection()
        if scan_events_collection is None or guards_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Calculate date range using IST
        from utils.timezone_utils import parse_ist_date_range, format_excel_datetime
        start_date, end_date = parse_ist_date_range(days_back)

        # Build base filter for date range
        base_filter = {
            "scannedAt": {"$gte": start_date, "$lte": end_date}
        }

        # Add area filter if specified (case-insensitive)
        if area:
            base_filter["$or"] = [
                {"site": {"$regex": area, "$options": "i"}},
                {"address": {"$regex": area, "$options": "i"}},
                {"formatted_address": {"$regex": area, "$options": "i"}}
            ]

        # Add site filter if specified (case-insensitive)
        if site:
            base_filter["site"] = {"$regex": site, "$options": "i"}

        # Fetch scan data
        scans = await scan_events_collection.find(base_filter).to_list(length=None)

        if not scans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No scan data found in the specified date range"
            )

        # Group data by area with improved organization and site display
        area_data = {}
        for scan in scans:
            # Fetch guard details using guardId
            guard_id = scan.get("guardId")
            guard_email = "Unknown Email"
            guard_phone = "Unknown Phone"

            if guard_id:
                try:
                    from bson import ObjectId
                    guard_id_obj = ObjectId(guard_id)
                    guard = await guards_collection.find_one({"_id": guard_id_obj})
                    if guard:
                        guard_email = guard.get("email") if guard and guard.get("email") else None
                        guard_phone = guard.get("phone") if guard and guard.get("phone") else "Unknown Phone"
                except Exception as e:
                    logger.error(f"Error fetching guard details for guardId {guard_id}: {e}")

            # Use guard email if available, otherwise fallback to phone number
            guard_contact = guard_email if guard_email else guard_phone

            area_name = scan.get("formatted_address") or scan.get("address", "Unknown Area")
            site_name = scan.get("site", "Unknown Site")
            guard_name = scan.get("guardName", "Unknown Guard")

            if area_name not in area_data:
                area_data[area_name] = []

            area_data[area_name].append({
                "timestamp": scan.get("scannedAt"),
                "site": site_name,
                "guard_name": guard_name,
                "guard_contact": guard_contact,
                "address": area_name,
                "coordinates": {
                    "lat": scan.get("deviceLat"),
                    "lng": scan.get("deviceLng")
                }
            })

        # Generate Excel response
        import io
        import pandas as pd
        from fastapi.responses import StreamingResponse

        # Prepare data for Excel
        excel_data = []
        for area_name, scans_list in area_data.items():
            for scan_data in scans_list:
                excel_data.append({
                    "Area": area_name,
                    "Site": scan_data["site"],
                    "Guard Name": scan_data["guard_name"],
                    "Guard Contact": scan_data["guard_contact"],
                    "Timestamp (IST)": format_excel_datetime(scan_data["timestamp"]),
                    "Latitude": scan_data["coordinates"]["lat"],
                    "Longitude": scan_data["coordinates"]["lng"],
                    "Address": scan_data["address"]
                })

        if not excel_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No scan data available for Excel generation"
            )

        # Create Excel file in memory
        output = io.BytesIO()
        df = pd.DataFrame(excel_data)
        df.to_excel(output, index=False, sheet_name="Area Wise Report")
        output.seek(0)

        # Generate filename
        area_suffix = f"_{area.replace(' ', '_')}" if area else "_all_areas"
        site_suffix = f"_{site.replace(' ', '_')}" if site else ""
        filename = f"area_report{area_suffix}{site_suffix}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        
        headers = {
            "Content-Disposition": f"attachment; filename={filename}"
        }
        
        logger.info(f"[SUPER_ADMIN] Area-wise Excel report generated: {filename}, Records: {len(excel_data)}")
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating area-wise Excel report (SUPER_ADMIN): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel report: {str(e)}"
        )


# ============================================================================
# SUPER ADMIN: Change Any User Password API
# ============================================================================

@super_admin_router.put("/change-user-password")
async def change_user_password(
    request: SuperAdminChangePasswordRequest,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Change password for any user (admin, supervisor, guard)
    """
    try:
        users_collection = get_users_collection()
        supervisors_collection = get_supervisors_collection()
        guards_collection = get_guards_collection()

        if (users_collection is None or supervisors_collection is None or 
            guards_collection is None):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Hash the new password
        new_password_hash = jwt_service.hash_password(request.newPassword)

        # Build search criteria (email OR phone)
        search_criteria = {}
        if request.userEmail:
            search_criteria["email"] = request.userEmail
        elif request.userPhone:
            search_criteria["phone"] = request.userPhone

        # Try to find user in all collections and update
        user_found = False
        user_type = None
        contact_info = request.userEmail or request.userPhone

        # Check and update in users collection (admins and super admins)
        user = await users_collection.find_one(search_criteria)
        if user:
            await users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "passwordHash": new_password_hash,
                        "updatedAt": datetime.utcnow()
                    }
                }
            )
            user_found = True
            user_type = "admin"

        # Check and update in supervisors collection
        supervisor = await supervisors_collection.find_one(search_criteria)
        if supervisor:
            await supervisors_collection.update_one(
                {"_id": supervisor["_id"]},
                {
                    "$set": {
                        "passwordHash": new_password_hash,
                        "updatedAt": datetime.utcnow()
                    }
                }
            )
            user_found = True
            user_type = "supervisor"

        # Check and update in guards collection
        guard = await guards_collection.find_one(search_criteria)
        if guard:
            await guards_collection.update_one(
                {"_id": guard["_id"]},
                {
                    "$set": {
                        "passwordHash": new_password_hash,
                        "updatedAt": datetime.utcnow()
                    }
                }
            )
            user_found = True
            user_type = "guard"

        if not user_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with contact {contact_info} not found in any collection"
            )

        logger.info(f"Super Admin {current_super_admin.get('name', 'Unknown')} changed password for {user_type} {contact_info}")

        return {
            "message": f"Password changed successfully for {user_type} {contact_info}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing user password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change user password: {str(e)}"
        )


# ============================================================================
# SUPER ADMIN: Request Password Change OTP API
# ============================================================================

@super_admin_router.post("/request-password-change-otp")
async def request_password_change_otp(
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN: Request OTP for password change via email
    """
    try:
        otp_collection = get_otp_tokens_collection()
        if otp_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        super_admin_email = current_super_admin.get("email")
        if not super_admin_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Super admin email not found"
            )

        # Check rate limiting - allow one OTP per minute per email
        recent_otp = await otp_collection.find_one({
            "email": super_admin_email,
            "purpose": "PASSWORD_CHANGE",
            "createdAt": {"$gte": datetime.utcnow() - timedelta(minutes=1)}
        })
        
        if recent_otp:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait 1 minute before requesting another OTP"
            )

        # Generate OTP
        otp = jwt_service.generate_otp()
        otp_hash = jwt_service.hash_otp(otp)
        
        # Store OTP in database
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # 10 minutes expiry
        
        otp_data = {
            "email": super_admin_email,
            "otpHash": otp_hash,
            "purpose": "PASSWORD_CHANGE",
            "expiresAt": expires_at,
            "attempts": 0,
            "createdAt": datetime.utcnow()
        }
        
        # Remove any existing OTP for this email and purpose
        await otp_collection.delete_many({"email": super_admin_email, "purpose": "PASSWORD_CHANGE"})
        
        # Insert new OTP
        await otp_collection.insert_one(otp_data)
        
        # Send email
        email_sent = await email_service.send_otp_email(super_admin_email, otp, "password change")
        
        if not email_sent:
            # Clean up if email failed
            await otp_collection.delete_one({"email": super_admin_email, "purpose": "PASSWORD_CHANGE"})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email. Please try again."
            )
        
        logger.info(f"Password change OTP sent to super admin: {super_admin_email}")
        
        return {
            "message": f"OTP sent to {super_admin_email}. Please check your email. OTP expires in 10 minutes."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send password change OTP: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )


# ============================================================================
# SUPER ADMIN: Change Own Password API (Updated with OTP)
# ============================================================================

@super_admin_router.put("/change-password")
async def change_super_admin_password(
    request: SuperAdminChangeOwnPasswordRequest,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN: Change own password using email OTP verification
    """
    try:
        users_collection = get_users_collection()
        otp_collection = get_otp_tokens_collection()

        if users_collection is None or otp_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        super_admin_email = current_super_admin.get("email")
        if not super_admin_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Super admin email not found"
            )

        # Verify OTP
        otp_record = await otp_collection.find_one({
            "email": super_admin_email,
            "purpose": "PASSWORD_CHANGE"
        })
        
        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP found. Please request an OTP first."
            )
        
        # Check if OTP has expired
        if datetime.utcnow() > otp_record["expiresAt"]:
            await otp_collection.delete_one({"_id": otp_record["_id"]})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new OTP."
            )
        
        # Check attempt limit
        if otp_record["attempts"] >= 3:
            await otp_collection.delete_one({"_id": otp_record["_id"]})
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum OTP attempts exceeded. Please request a new OTP."
            )
        
        # Verify OTP
        if not jwt_service.verify_otp(request.otp, otp_record["otpHash"]):
            # Increment attempt counter
            await otp_collection.update_one(
                {"_id": otp_record["_id"]},
                {"$inc": {"attempts": 1}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP. Please check and try again."
            )

        # OTP is valid - remove it and change password
        await otp_collection.delete_one({"_id": otp_record["_id"]})

        # Hash the new password
        new_password_hash = jwt_service.hash_password(request.newPassword)

        # Update password in users collection
        super_admin_id = current_super_admin["_id"]
        await users_collection.update_one(
            {"_id": super_admin_id},
            {
                "$set": {
                    "passwordHash": new_password_hash,
                    "updatedAt": datetime.utcnow()
                }
            }
        )

        logger.info(f"Super Admin {current_super_admin.get('name', 'Unknown')} changed own password using OTP")

        return {
            "message": "Password changed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing super admin password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )


# ============================================================================
# SUPER ADMIN: Search Users API
# ============================================================================

@super_admin_router.get("/search-users")
async def search_users(
    query: Optional[str] = Query(None, description="Search by name, email, or phone"),
    state: Optional[str] = Query(None, description="Filter by state"),
    role: Optional[str] = Query(None, description="Filter by role: 'supervisor', 'guard', 'admin'"),
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Search for users across all collections by name, email, phone, or state
    Simple role filtering: 'supervisor', 'guard', 'admin'
    """
    try:
        users_collection = get_users_collection()
        supervisors_collection = get_supervisors_collection()
        guards_collection = get_guards_collection()

        if (users_collection is None or supervisors_collection is None or 
            guards_collection is None):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        all_users = []

        # Build search criteria
        search_criteria = {}
        
        # Handle role-based filtering
        role_filter = None
        if role:
            role_lower = role.lower()
            if role_lower == "supervisor":
                role_filter = "supervisors"
            elif role_lower == "guard":
                role_filter = "guards"
            elif role_lower == "admin":
                role_filter = "admins"
        
        # Also check query parameter for role keywords (backward compatibility)
        if query and not role_filter:
            query_lower = query.lower()
            if query_lower == "supervisor":
                role_filter = "supervisors"
            elif query_lower == "guard":
                role_filter = "guards"
            elif query_lower == "admin":
                role_filter = "admins"

        # Build text search criteria if query is provided and not a role keyword
        if query and not role_filter:
            search_criteria["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
                {"phone": {"$regex": query, "$options": "i"}}
            ]
        
        # Add state filter if provided
        if state:
            search_criteria["areaCity"] = {"$regex": state, "$options": "i"}

        # Search based on role filter or all collections
        if role_filter == "supervisors":
            # Search only in supervisors collection
            supervisors_cursor = supervisors_collection.find(search_criteria)
            async for supervisor in supervisors_cursor:
                supervisor_data = {
                    "id": str(supervisor["_id"]),
                    "name": supervisor.get("name", ""),
                    "email": supervisor.get("email", ""),
                    "phone": supervisor.get("phone", ""),
                    "role": "SUPERVISOR",
                    "areaCity": supervisor.get("areaCity", ""),
                    "isActive": supervisor.get("isActive", True),
                    "createdAt": supervisor.get("createdAt"),
                    "lastLogin": supervisor.get("lastLogin"),
                    "collection": "supervisors",
                    "code": supervisor.get("code", "")
                }
                all_users.append(supervisor_data)
                
        elif role_filter == "guards":
            # Search only in guards collection  
            guards_cursor = guards_collection.find(search_criteria)
            async for guard in guards_cursor:
                guard_data = {
                    "id": str(guard["_id"]),
                    "name": guard.get("name", ""),
                    "email": guard.get("email", ""),
                    "phone": guard.get("phone", ""),
                    "role": "GUARD",
                    "areaCity": guard.get("areaCity", ""),
                    "isActive": guard.get("isActive", True),
                    "createdAt": guard.get("createdAt"),
                    "lastLogin": guard.get("lastLogin"),
                    "collection": "guards",
                    "employeeCode": guard.get("employeeCode", ""),
                    "supervisorId": guard.get("supervisorId", "")
                }
                all_users.append(guard_data)
                
        elif role_filter == "admins":
            # Search only in users collection for ADMIN role
            admin_criteria = {**search_criteria, "role": "ADMIN"}
            users_cursor = users_collection.find(admin_criteria)
            async for user in users_cursor:
                user_data = {
                    "id": str(user["_id"]),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "phone": user.get("phone", ""),
                    "role": user.get("role", ""),
                    "areaCity": user.get("areaCity", ""),
                    "isActive": user.get("isActive", True),
                    "createdAt": user.get("createdAt"),
                    "lastLogin": user.get("lastLogin"),
                    "collection": "users"
                }
                all_users.append(user_data)
        
        else:
            # Search all collections when no specific role filter is applied
            await search_all_collections(users_collection, supervisors_collection, guards_collection, search_criteria, all_users)

        # Sort by creation date (newest first)
        all_users.sort(key=lambda x: x.get("createdAt") or datetime.min, reverse=True)

        # Format dates for response
        for user in all_users:
            if user.get("createdAt"):
                if hasattr(user["createdAt"], 'isoformat'):
                    user["createdAt"] = user["createdAt"].isoformat()
            if user.get("lastLogin"):
                if hasattr(user["lastLogin"], 'isoformat'):
                    user["lastLogin"] = user["lastLogin"].isoformat()

        return {
            "users": all_users,
            "total": len(all_users),
            "filters": {
                "query": query,
                "state": state
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search users: {str(e)}"
        )


async def search_all_collections(users_collection, supervisors_collection, guards_collection, search_criteria, all_users):
    """Helper function to search across all collections (excludes super admins)"""
    # Search in users collection (admins only, exclude super admins)
    admin_criteria = {**search_criteria, "role": "ADMIN"}
    users_cursor = users_collection.find(admin_criteria)
    async for user in users_cursor:
        user_data = {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "role": user.get("role", "ADMIN"),
            "areaCity": user.get("areaCity", ""),
            "isActive": user.get("isActive", True),
            "createdAt": user.get("createdAt"),
            "lastLogin": user.get("lastLogin"),
            "collection": "users"
        }
        all_users.append(user_data)

    # Search in supervisors collection
    supervisors_cursor = supervisors_collection.find(search_criteria)
    async for supervisor in supervisors_cursor:
        supervisor_data = {
            "id": str(supervisor["_id"]),
            "name": supervisor.get("name", ""),
            "email": supervisor.get("email", ""),
            "phone": supervisor.get("phone", ""),
            "role": "SUPERVISOR",
            "areaCity": supervisor.get("areaCity", ""),
            "isActive": supervisor.get("isActive", True),
            "createdAt": supervisor.get("createdAt"),
            "lastLogin": supervisor.get("lastLogin"),
            "collection": "supervisors",
            "code": supervisor.get("code", "")
        }
        all_users.append(supervisor_data)

    # Search in guards collection
    guards_cursor = guards_collection.find(search_criteria)
    async for guard in guards_cursor:
        guard_data = {
            "id": str(guard["_id"]),
            "name": guard.get("name", ""),
            "email": guard.get("email", ""),
            "phone": guard.get("phone", ""),
            "role": "GUARD",
            "areaCity": guard.get("areaCity", ""),
            "isActive": guard.get("isActive", True),
            "createdAt": guard.get("createdAt"),
            "lastLogin": guard.get("lastLogin"),
            "collection": "guards",
            "employeeCode": guard.get("employeeCode", ""),
            "supervisorId": guard.get("supervisorId", "")
        }
        all_users.append(guard_data)


# ============================================================================
# SUPER ADMIN: Comprehensive Dashboard API
# ============================================================================

@super_admin_router.get("/dashboard")
async def get_super_admin_dashboard(
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Comprehensive dashboard with all system statistics and detailed data
    Includes all features previously in admin dashboard plus super admin capabilities
    """
    try:
        users_collection = get_users_collection()
        supervisors_collection = get_supervisors_collection()
        guards_collection = get_guards_collection()
        scan_events_collection = get_scan_events_collection()
        
        if not all([
            users_collection is not None, 
            supervisors_collection is not None, 
            guards_collection is not None, 
            scan_events_collection is not None
        ]):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Get comprehensive counts (exclude super admins from user count)
        total_users = await users_collection.count_documents({"role": {"$ne": "SUPER_ADMIN"}})
        total_supervisors = await supervisors_collection.count_documents({})
        total_guards = await guards_collection.count_documents({})
        
        # Get today's scans count with improved logic
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total_scans_today = await scan_events_collection.count_documents({
            "scannedAt": {"$gte": today_start}
        })
        
        # Get supervisor scans today
        supervisor_scans_today = await scan_events_collection.count_documents({
            "scannedAt": {"$gte": today_start},
            "scannedBy": "SUPERVISOR"
        })
        
        # Get guard scans today (including legacy records without scannedBy field)
        guard_scans_today = await scan_events_collection.count_documents({
            "scannedAt": {"$gte": today_start},
            "$or": [
                {"scannedBy": "GUARD"},
                {"scannedBy": {"$exists": False}}  # Legacy records
            ]
        })
        
        # Get comprehensive lists with detailed information
        users_list = []
        supervisors_list = []
        guards_list = []
        
        # Get all users with detailed information (exclude super admins)
        users_cursor = users_collection.find({"role": {"$ne": "SUPER_ADMIN"}})
        async for user in users_cursor:
            user_data = {
                "name": user.get("name", ""),
                "contact": user.get("email", "") or user.get("phone", ""),
                "role": user.get("role", ""),
                "area": user.get("state", "N/A")
            }
            users_list.append(user_data)
        
        # Get all supervisors with basic details
        supervisors_cursor = supervisors_collection.find({})
        async for supervisor in supervisors_cursor:
            supervisor_data = {
                "name": supervisor.get("name", ""),
                "contact": supervisor.get("email", "") or supervisor.get("phone", ""),
                "area": supervisor.get("areaCity", "N/A")
            }
            supervisors_list.append(supervisor_data)
        
        # Get all guards with basic details
        guards_cursor = guards_collection.find({})
        async for guard in guards_cursor:
            guard_data = {
                "name": guard.get("name", ""),
                "contact": guard.get("email", "") or guard.get("phone", ""),
                "area": guard.get("areaCity", "N/A")
            }
            guards_list.append(guard_data)
        
        # Get recent activity with comprehensive data display
        recent_scans_cursor = scan_events_collection.find({}) \
            .sort("scannedAt", -1) \
            .limit(15)  # More items for super admin
        
        recent_scans = []
        async for scan in recent_scans_cursor:
            # Get site information
            site = scan.get("site", "Unknown Site") 
            scanned_by = scan.get("scannedBy", "GUARD")  # Default to GUARD for legacy records
            
            if scanned_by == "SUPERVISOR":
                scanner_name = scan.get("supervisorName", scan.get("supervisorEmail", "Unknown Supervisor"))
                scanner_id = str(scan.get("supervisorId", ""))
                scanner_email = scan.get("supervisorEmail", "")
            else:
                scanner_name = scan.get("guardName", scan.get("guardEmail", "Unknown Guard"))
                scanner_id = str(scan.get("guardId", ""))
                scanner_email = scan.get("guardEmail", "")
            
            scan_data = {
                "_id": str(scan["_id"]),
                "scannerId": scanner_id,
                "scannerEmail": scanner_email,
                "scannerName": scanner_name,
                "scannerType": scanned_by,
                "site": site,
                "post": scan.get("post", ""),
                "qrType": scan.get("qrType", "REGULAR"),
                "scannedAt": scan.get("scannedAt"),
                "deviceLat": scan.get("deviceLat"),
                "deviceLng": scan.get("deviceLng"),
                "address": scan.get("address", "")
            }
            recent_scans.append(scan_data)
        
        # Convert super admin ObjectIds to strings
        super_admin_info = {
            "_id": str(current_super_admin["_id"]),
            "email": current_super_admin["email"],
            "name": current_super_admin.get("name", "Super Admin"),
            "role": current_super_admin.get("role", "SUPER_ADMIN")
        }
        
        # Include comprehensive data in response
        response_data = {
            "stats": {
                "totalUsers": total_users,
                "totalSupervisors": total_supervisors,
                "totalGuards": total_guards,
                "scansToday": total_scans_today,
                "supervisorScansToday": supervisor_scans_today,
                "guardScansToday": guard_scans_today
            },
            "recentActivity": recent_scans,
            "superAdminInfo": super_admin_info,
            "users": users_list,
            "supervisors": supervisors_list,
            "guards": guards_list
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Super Admin Dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load super admin dashboard"
        )


# ============================================================================
# SUPER ADMIN: AI Intelligence APIs - Weather & News
# ============================================================================

@super_admin_router.post("/weather-forecast", response_model=WeatherForecastResponse)
async def get_weather_forecast(
    request: WeatherForecastRequest,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Get AI-powered hourly weather forecast for a specific site location and date
    
    Uses Perplexity AI to provide detailed weather information including:
    - Hourly temperature and conditions
    - Humidity, wind speed, UV index
    - Precipitation probability
    - Weather alerts and recommendations
    
    Perfect for planning security patrol routes and operations at client sites.
    """
    try:
        logger.info(f"Weather forecast requested by super admin: {current_super_admin.get('email')} for {request.site_name} in {request.location} on {request.date}")
        
        # Get weather forecast from Perplexity AI
        forecast_data = await perplexity_service.get_weather_forecast(
            site_name=request.site_name,
            location=request.location,
            date=request.date
        )
        
        if forecast_data.get("success"):
            logger.info(f"Weather forecast generated successfully for {request.site_name} in {request.location}")
        else:
            logger.warning(f"Weather forecast failed: {forecast_data.get('error')}")
        
        return WeatherForecastResponse(**forecast_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Weather forecast error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get weather forecast: {str(e)}"
        )


@super_admin_router.post("/site-news-intelligence", response_model=SiteNewsIntelligenceResponse)
async def get_site_news_intelligence(
    request: SiteNewsIntelligenceRequest,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Get comprehensive AI-powered news and social intelligence about a site/company at a location
    
    Uses Perplexity AI to provide:
    - Recent news articles and updates (last 7 days)
    - Social media buzz and public sentiment
    - Local impact and community relations
    - Security and safety considerations
    - Business and operational updates
    
    This helps super admins stay informed about:
    - What's happening at client sites
    - Public perception and social buzz
    - Potential security concerns
    - Local news coverage and community sentiment
    """
    try:
        logger.info(f"Site intelligence requested by super admin: {current_super_admin.get('email')} for {request.site_name} in {request.location}")
        
        # Get site intelligence from Perplexity AI
        intelligence_data = await perplexity_service.get_site_news_intelligence(
            site_name=request.site_name,
            location=request.location
        )
        
        if intelligence_data.get("success"):
            logger.info(f"Site intelligence generated successfully for {request.site_name}")
        else:
            logger.warning(f"Site intelligence failed: {intelligence_data.get('error')}")
        
        return SiteNewsIntelligenceResponse(**intelligence_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Site intelligence error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get site intelligence: {str(e)}"
        )
