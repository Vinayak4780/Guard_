"""
Super Admin routes for managing state-wise admins
SUPER_ADMIN role only - manage state-wise admins and system configuration
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from bson import ObjectId

# Import services and dependencies
from services.auth_service import get_current_super_admin
from services.jwt_service import jwt_service
from database import get_users_collection, get_scan_events_collection, get_guards_collection
from config import settings

# Import models
from models import (
    SuperAdminAddAdminRequest, StateAdminResponse
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
    email: Optional[str] = None,
    phone: Optional[str] = None,
    current_super_admin: Dict[str, Any] = Depends(get_current_super_admin)
):
    """
    SUPER_ADMIN ONLY: Delete a state-wise admin from the system by name and contact info
    """
    try:
        users_collection = get_users_collection()

        if users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Validate that either email or phone is provided
        if not email and not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either email or phone number must be provided"
            )

        # Clean inputs
        name = name.strip()
        contact_value = email.strip() if email else phone.strip()
        contact_type = "email" if email else "phone"

        # Build search criteria
        search_criteria = {
            "role": "ADMIN",
            "name": name
        }

        if email:
            search_criteria["email"] = email.strip()
        elif phone:
            search_criteria["phone"] = phone.strip()

        # Find admin by name and contact info
        admin = await users_collection.find_one(search_criteria)

        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"State admin with name '{name}' and {contact_type} '{contact_value}' not found"
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

        logger.info(f"Super admin {current_super_admin.get('email')} deleted state admin {admin_id} ({admin_name}, {contact_type}: {contact_value}, {admin_state})")

        return {
            "message": "State admin deleted successfully",
            "admin_id": admin_id,
            "name": admin_name,
            "state": admin_state,
            "deleted_by": contact_type,
            "contact_used": contact_value
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
