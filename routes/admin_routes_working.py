"""
Admin routes for user management and system administration
ADMIN role only - manage supervisors, guards, and system configuration
Updated with specific email patterns: admin@lh.io.in, {area}supervisor@lh.io.in
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import os
import io
import json
from bson import ObjectId

# Import services and dependencies
from services.auth_service import get_current_admin
from services.google_drive_excel_service import google_drive_excel_service
from services.email_service import email_service
from services.jwt_service import jwt_service
from database import (
    get_users_collection, get_supervisors_collection, get_guards_collection,
    get_scan_events_collection, get_qr_locations_collection, get_database_health
)
from config import settings

# Import models
from models import (
    UserCreate, UserResponse, UserRole, SupervisorCreate, SupervisorResponse,
    GuardCreate, GuardResponse, ScanEventResponse, AreaReportRequest,
    ScanReportResponse, SuccessResponse, SystemConfig, SystemConfigUpdate,
    AdminAddSupervisorRequest, generate_supervisor_email, generate_guard_email,
    AdminChangePasswordRequest
)

logger = logging.getLogger(__name__)

# Create router
admin_router = APIRouter()


@admin_router.get("/dashboard")
async def get_admin_dashboard(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """
    Admin dashboard with system statistics and detailed user data export
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
        
        # Get basic counts (exclude user count from admin dashboard)
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
        
        # Get basic lists with simple information
        supervisors_list = []
        guards_list = []
        
        # Get all supervisors with basic details (no area field)
        supervisors_cursor = supervisors_collection.find({})
        async for supervisor in supervisors_cursor:
            supervisor_data = {
                "name": supervisor.get("name", ""),
                "contact": supervisor.get("email", "") or supervisor.get("phone", "")
            }
            supervisors_list.append(supervisor_data)
        
        # Get all guards with basic details (no area field)
        guards_cursor = guards_collection.find({})
        async for guard in guards_cursor:
            guard_data = {
                "name": guard.get("name", ""),
                "contact": guard.get("email", "") or guard.get("phone", "")
            }
            guards_list.append(guard_data)
        
        # Get recent activity with improved data display
        recent_scans_cursor = scan_events_collection.find({}) \
            .sort("scannedAt", -1) \
            .limit(10)
        
        recent_scans = []
        async for scan in recent_scans_cursor:
            # Get site information (removed organization field)
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
        
        # Convert admin ObjectIds to strings
        admin_info = {
            "_id": str(current_admin["_id"]),
            "email": current_admin["email"],
            "name": current_admin.get("name", "Admin"),
            "role": current_admin.get("role", "ADMIN")
        }
        
        # Include simplified user data directly in response
        response_data = {
            "stats": {
                "totalSupervisors": total_supervisors,
                "totalGuards": total_guards,
                "scansToday": total_scans_today,
                "supervisorScansToday": supervisor_scans_today,
                "guardScansToday": guard_scans_today
            },
            "recentActivity": recent_scans,
            "adminInfo": admin_info,
            "supervisors": supervisors_list,
            "guards": guards_list
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard"
        )


@admin_router.get("/excel/area-wise-reports")
async def get_area_wise_excel_reports(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    days_back: int = Query(7, ge=1, le=30, description="Number of days to include in report"),
    area: Optional[str] = Query(None, description="Specific area/state to filter (optional)"),
    site: Optional[str] = Query(None, description="Name of the site to filter (optional)")
):
    """
    Generate area-wise Excel reports for all areas or a specific area
    """
    try:
        scan_events_collection = get_scan_events_collection()
        guards_collection = get_guards_collection()  # Get guards collection
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

            if guard_id:
                try:
                    guard_id = ObjectId(guard_id)
                    guard = await guards_collection.find_one({"_id": guard_id})
                except Exception as e:
                    logger.error(f"Error fetching guard details for guardId {guard_id}: {e}")

            area_name = scan.get("formatted_address") or scan.get("address", "Unknown Area")
            site_name = scan.get("site", "Unknown Site")
            guard_name = scan.get("guardName", "Unknown Guard")

            if area_name not in area_data:
                area_data[area_name] = []

            area_data[area_name].append({
                "timestamp": scan.get("scannedAt"),
                "site": site_name,
                "guard_name": guard_name,
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
        for area_name, scans in area_data.items():
            for scan_data in scans:
                excel_data.append({
                    "Area": area_name,
                    "Site": scan_data["site"],
                    "Guard Name": scan_data["guard_name"],
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
        
        logger.info(f"Area-wise Excel report generated: {filename}, Records: {len(excel_data)}")
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating area-wise Excel report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel report: {str(e)}"
        )


# ============================================================================
# ADMIN: Add Supervisor API
# ============================================================================

# Updated validation to allow either email or phone
@admin_router.post("/add-supervisor")
async def add_supervisor(
    supervisor_data: AdminAddSupervisorRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin)
):
    """
    ADMIN ONLY: Add a new supervisor to the system
    Creates supervisor account and sends credentials via email only
    """
    try:
        supervisors_collection = get_supervisors_collection()

        if supervisors_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        admin_id = str(current_admin["_id"])
        admin_name = current_admin.get("name", current_admin.get("email", "Admin"))

        # Ensure at least one contact method is provided (check for empty strings too)
        has_email = supervisor_data.email and supervisor_data.email.strip()
        has_phone = supervisor_data.phone and supervisor_data.phone.strip()
        
        if not has_email and not has_phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either email or phone must be provided"
            )

        # Determine if using email or phone
        contact_method = "email" if has_email else "phone"
        contact_value = supervisor_data.email.strip() if has_email else supervisor_data.phone.strip()

        # Check if supervisor already exists (only check non-empty values)
        or_conditions = []
        
        # Only check email if it's provided and not empty
        if supervisor_data.email and supervisor_data.email.strip():
            or_conditions.append({"email": supervisor_data.email.strip()})
        
        # Only check phone if it's provided and not empty
        if supervisor_data.phone and supervisor_data.phone.strip():
            or_conditions.append({"phone": supervisor_data.phone.strip()})
        
        # Only run the query if we have conditions to check
        if or_conditions:
            existing_supervisor = await supervisors_collection.find_one({
                "$or": or_conditions
            })

            if existing_supervisor:
                # Determine which field matched
                if (supervisor_data.email and supervisor_data.email.strip() and 
                    existing_supervisor.get("email") == supervisor_data.email.strip()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Supervisor with email {supervisor_data.email} already exists"
                    )
                elif (supervisor_data.phone and supervisor_data.phone.strip() and 
                      existing_supervisor.get("phone") == supervisor_data.phone.strip()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Supervisor with phone {supervisor_data.phone} already exists"
                    )

        # Hash the password
        hashed_password = jwt_service.hash_password(supervisor_data.password)

        # Create supervisor record
        supervisor_data_record = {
            "name": supervisor_data.name,
            "areaCity": supervisor_data.areaCity,
            "isActive": True,
            "createdBy": admin_id,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        # Add email or phone to supervisor record (only if not empty)
        if supervisor_data.email and supervisor_data.email.strip():
            supervisor_data_record["email"] = supervisor_data.email.strip()
        if supervisor_data.phone and supervisor_data.phone.strip():
            supervisor_data_record["phone"] = supervisor_data.phone.strip()

        # Generate an incrementing id like sp1, sp2, etc.
        # Count total supervisors to get the next sequential number
        supervisor_count = await supervisors_collection.count_documents({})
        new_id_number = supervisor_count + 1
        
        # Generate unique code by checking if it exists
        while True:
            new_id = f"sp{new_id_number}"
            # Check if this code already exists
            existing_code = await supervisors_collection.find_one({"code": new_id})
            if not existing_code:
                break
            new_id_number += 1

        # Add the new id and required fields to the supervisor record
        supervisor_data_record["id"] = new_id
        supervisor_data_record["code"] = new_id  # Use the same value for code field
        supervisor_data_record["userId"] = new_id  # Use the same value for userId field to avoid duplicate key errors

        # Add the hashed password to the supervisor record
        supervisor_data_record["passwordHash"] = hashed_password

        # Insert supervisor
        supervisor_result = await supervisors_collection.insert_one(supervisor_data_record)

        # Construct response with the new id (only include non-empty contact info)
        response_supervisor = {
            "id": new_id,
            "name": supervisor_data.name,
            "areaCity": supervisor_data.areaCity,
            "adminName": admin_name
        }
        
        # Add email and phone only if they were provided
        if has_email:
            response_supervisor["email"] = supervisor_data.email.strip()
        if has_phone:
            response_supervisor["phone"] = supervisor_data.phone.strip()
        
        return {
            "message": "Supervisor added successfully",
            "supervisor": response_supervisor
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding supervisor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add supervisor: {str(e)}"
        )


# ============================================================================
# ADMIN: List Supervisors API
# ============================================================================

@admin_router.get("/supervisors")
async def list_supervisors(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    area_city: Optional[str] = Query(None, description="Filter by area/city")
):
    """
    ADMIN ONLY: List all supervisors in the system
    Supports filtering by area/city
    """
    try:
        supervisors_collection = get_supervisors_collection()
        
        if supervisors_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Build query filter
        query_filter = {}
        
        if area_city:
            query_filter["areaCity"] = {"$regex": area_city, "$options": "i"}  # Case-insensitive search
        
        # Get supervisors
        supervisors_cursor = supervisors_collection.find(query_filter).sort("createdAt", -1)
        
        supervisors = []
        async for supervisor in supervisors_cursor:
            supervisor_data = {
                "id": supervisor.get("id", str(supervisor["_id"])),
                "name": supervisor["name"],
                "email": supervisor.get("email"),
                "phone": supervisor.get("phone"),
                "areaCity": supervisor["areaCity"],
                "isActive": supervisor.get("isActive", True),
                "createdAt": supervisor.get("createdAt"),
                "updatedAt": supervisor.get("updatedAt"),
                "lastLogin": supervisor.get("lastLogin"),
                "code": supervisor.get("code"),
                "userId": supervisor.get("userId")
            }
            supervisors.append(supervisor_data)
        
        return {
            "supervisors": supervisors,
            "filters": {
                "area_city": area_city
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing supervisors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list supervisors: {str(e)}"
        )


# ============================================================================
# ADMIN: Delete Supervisor API
# ============================================================================

# Fixed the search criteria to match the database field names
@admin_router.delete("/delete-supervisor")
async def delete_supervisor(
    name: str,
    area: str,
    current_admin: Dict[str, Any] = Depends(get_current_admin)
):
    """
    ADMIN ONLY: Delete a supervisor from the system by name and area
    Removes supervisor from the supervisors collection only
    """
    try:
        supervisors_collection = get_supervisors_collection()

        if supervisors_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Clean inputs
        name = name.strip()
        area = area.strip()
        # Build search criteria
        search_criteria = {
            "name": name,
            "state": area  # Using the correct database field name
        }

        # Find supervisor by name and area
        supervisor = await supervisors_collection.find_one(search_criteria)

        if not supervisor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with name '{name}' in area '{area}' not found"
            )

        supervisor_id = str(supervisor["_id"])

        # Delete from supervisors collection
        supervisor_result = await supervisors_collection.delete_one({"_id": supervisor["_id"]})

        logger.info(f"Admin {current_admin.get('email')} deleted supervisor {supervisor_id} ({name}, area: {area})")

        return {
            "message": "Supervisor deleted successfully",
            "supervisor_id": supervisor_id,
            "name": name,
            "area": area
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting supervisor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete supervisor: {str(e)}"
        )


# ============================================================================
# ADMIN: Change Supervisor Password API
# ============================================================================

@admin_router.put("/change-supervisor-password")
async def change_supervisor_password(
    request: AdminChangePasswordRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin)
):
    """
    ADMIN ONLY: Change password for a supervisor
    """
    try:
        supervisors_collection = get_supervisors_collection()
        users_collection = get_users_collection()

        if supervisors_collection is None or users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Ensure at least one contact method is provided
        if not request.userEmail and not request.userPhone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either userEmail or userPhone must be provided"
            )

        # Build search criteria for supervisor (email OR phone)
        contact_conditions = []
        if request.userEmail:
            contact_conditions.append({"email": request.userEmail})
        if request.userPhone:
            contact_conditions.append({"phone": request.userPhone})

        supervisor_search = {"$or": contact_conditions}

        # Find the supervisor by email or phone
        supervisor = await supervisors_collection.find_one(supervisor_search)

        if not supervisor:
            contact_info = request.userEmail or request.userPhone
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with contact {contact_info} not found"
            )

        # Hash the new password
        new_password_hash = jwt_service.hash_password(request.newPassword)

        # Update password in supervisors collection
        await supervisors_collection.update_one(
            {"_id": supervisor["_id"]},
            {
                "$set": {
                    "passwordHash": new_password_hash,
                    "updatedAt": datetime.utcnow()
                }
            }
        )

        # Also update in users collection if supervisor has a user record
        user_update_criteria = {}
        if request.userEmail:
            user_update_criteria["email"] = request.userEmail
        elif request.userPhone:
            user_update_criteria["phone"] = request.userPhone

        if user_update_criteria:
            await users_collection.update_one(
                user_update_criteria,
                {
                    "$set": {
                        "passwordHash": new_password_hash,
                        "updatedAt": datetime.utcnow()
                    }
                }
            )

        contact_info = request.userEmail or request.userPhone
        logger.info(f"Admin {current_admin.get('name', 'Unknown')} changed password for supervisor {contact_info}")

        return {
            "message": f"Password changed successfully for supervisor {contact_info}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing supervisor password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change supervisor password: {str(e)}"
        )


# ============================================================================
# ADMIN: QR Code Management APIs
# ============================================================================

from fastapi import Body
from fastapi.responses import StreamingResponse, HTMLResponse

@admin_router.post("/qr/create")
async def admin_create_qr_code(
    site: str = Body(..., embed=True, description="Site name created by the admin"),
    post_name: str = Body(..., embed=True, description="Post name (e.g., canteen, gate, etc.)"),
    current_admin: Dict[str, Any] = Depends(get_current_admin)
):
    """
    ADMIN ONLY: Create a QR code for a specific site and post.
    QR codes created by admin can be scanned by supervisors.
    """
    qr_locations_collection = get_qr_locations_collection()

    if qr_locations_collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Normalize inputs
    normalized_site = site.strip()
    post_name = post_name.strip()

    # Validation
    if not normalized_site or not post_name:
        raise HTTPException(status_code=400, detail="Site and post_name are required and cannot be empty")

    try:
        # Check for existing QR location
        existing_qr = await qr_locations_collection.find_one({
            "site": normalized_site,
            "post": post_name,
            "createdBy": "ADMIN"
        })

        if existing_qr:
            qr_id = str(existing_qr["_id"])
            logger.info(f"Found existing admin QR location with ID: {qr_id}")
        else:
            # Create new QR location document with admin info
            qr_location_doc = {
                "site": normalized_site,
                "post": post_name,
                "adminId": current_admin["_id"],
                "createdBy": "ADMIN",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }

            qr_result = await qr_locations_collection.insert_one(qr_location_doc)
            qr_id = str(qr_result.inserted_id)
            logger.info(f"Successfully created admin QR location with ID: {qr_id}")

    except Exception as e:
        logger.error(f"Database error during admin QR creation: {e}")
        raise HTTPException(status_code=500, detail="Unable to create or find QR location")

    # Generate QR code with site, post, QR id
    qr_content = f"ADMIN:{normalized_site}:{post_name}:{qr_id}"

    import qrcode, io
    
    # Create QR code with better settings
    qr_code = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr_code.add_data(qr_content)
    qr_code.make(fit=True)
    
    # Create image with white background
    qr_img = qr_code.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")


@admin_router.get("/qr/list")
async def admin_list_qr_codes(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    site: Optional[str] = Query(None, description="Filter by site name"),
    format: Optional[str] = Query("json", description="Response format: 'json' or 'html'")
):
    """
    ADMIN ONLY: List all QR codes created by admins.
    """
    try:
        qr_locations_collection = get_qr_locations_collection()
        if qr_locations_collection is None:
            raise HTTPException(status_code=503, detail="Database not available")

        # Build filter query for admin-created QR codes
        filter_query = {"createdBy": "ADMIN"}

        # Add site filter if provided
        if site:
            filter_query["site"] = {"$regex": site.strip(), "$options": "i"}

        # Ensure 'post' field is not empty or null
        filter_query["post"] = {"$exists": True, "$ne": ""}

        # Get filtered QR locations created by admin
        qr_locations = await qr_locations_collection.find(filter_query).sort("createdAt", -1).to_list(length=None)

        formatted_qrs = []
        for qr in qr_locations:
            # Generate QR code image with better quality
            qr_content = f"ADMIN:{qr.get('site', '')}:{qr.get('post', '')}:{str(qr['_id'])}"
            
            import qrcode, io, base64
            from PIL import Image
            
            # Create QR code with better settings
            qr_code = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr_code.add_data(qr_content)
            qr_code.make(fit=True)
            
            # Create image with white background
            qr_img = qr_code.make_image(fill_color="black", back_color="white")
            
            # Convert to bytes
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            buf.seek(0)
            
            # Convert to base64 for JSON response
            qr_image_base64 = base64.b64encode(buf.getvalue()).decode()
            
            qr_data = {
                "qr_id": str(qr["_id"]),
                "site": qr.get("site", ""),
                "post": qr.get("post", ""),
                "qr_content": qr_content,
                "qr_image": f"data:image/png;base64,{qr_image_base64}",
                "created_by": "ADMIN",
                "admin_id": str(qr.get("adminId", "")),
                "created_at": qr.get("createdAt").isoformat() if qr.get("createdAt") else None,
                "updated_at": qr.get("updatedAt").isoformat() if qr.get("updatedAt") else None
            }
            formatted_qrs.append(qr_data)

        # Prepare response message
        total_count = len(formatted_qrs)
        filter_message = f" for site '{site}'" if site else ""

        # Return HTML format if requested
        if format.lower() == "html":
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Admin QR Codes List</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .qr-item {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 8px; }}
                    .qr-info {{ display: inline-block; vertical-align: top; margin-left: 20px; }}
                    img {{ border: 2px solid #333; }}
                    h1 {{ color: #333; }}
                    .total {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                    .admin-tag {{ background: #007bff; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; }}
                </style>
            </head>
            <body>
                <h1>Admin QR Codes List</h1>
                <div class="total">
                    <strong>Found {total_count} admin-created QR codes{filter_message}</strong>
                </div>
            """
            
            for qr in formatted_qrs:
                html_content += f"""
                <div class="qr-item">
                    <img src="{qr['qr_image']}" alt="QR Code" width="200" height="200">
                    <div class="qr-info">
                        <h3>{qr['site']} - {qr['post']} <span class="admin-tag">ADMIN CREATED</span></h3>
                        <p><strong>QR ID:</strong> {qr['qr_id']}</p>
                        <p><strong>Content:</strong> {qr['qr_content']}</p>
                        <p><strong>Admin ID:</strong> {qr['admin_id']}</p>
                        <p><strong>Created:</strong> {qr['created_at']}</p>
                        <p><strong>Updated:</strong> {qr['updated_at']}</p>
                    </div>
                </div>
                """
            
            html_content += """
            </body>
            </html>
            """
            
            return HTMLResponse(content=html_content)

        # Return JSON format (default)
        return {
            "qr_codes": formatted_qrs,
            "total": total_count,
            "site_filter": site,
            "message": f"Found {total_count} admin-created QR codes{filter_message}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing admin QR codes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ADMIN: Supervisor Scans Excel Export
# ============================================================================

@admin_router.get("/excel/supervisor-scans")
async def get_supervisor_scans_excel(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    supervisor_area: Optional[str] = Query(None, description="Filter by supervisor area/city"),
    days_back: int = Query(7, ge=1, le=30, description="Number of previous days to include in report")
):
    """
    ADMIN ONLY: Generate Excel report of supervisor scans filtered by area and days
    """
    try:
        scan_events_collection = get_scan_events_collection()
        supervisors_collection = get_supervisors_collection()

        if not all([scan_events_collection, supervisors_collection]):
            raise HTTPException(status_code=503, detail="Database not available")

        # Build query filter for supervisor scans
        query_filter = {"scannedBy": "SUPERVISOR"}

        # Calculate date range using days_back
        from utils.timezone_utils import parse_ist_date_range, format_excel_datetime
        start_date, end_date = parse_ist_date_range(days_back)
        query_filter["scannedAt"] = {"$gte": start_date, "$lte": end_date}

        logger.info(f"[ADMIN] Supervisor scans Excel report request - Days back: {days_back}, Area: {supervisor_area or 'All areas'}")
        logger.info(f"Date range: {start_date} to {end_date}")

        # Filter by supervisor area if provided
        if supervisor_area:
            # Find supervisors in the specified area
            supervisors_in_area = await supervisors_collection.find({
                "areaCity": {"$regex": supervisor_area, "$options": "i"}
            }).to_list(length=None)
            
            if supervisors_in_area:
                supervisor_ids = [supervisor["_id"] for supervisor in supervisors_in_area]
                query_filter["supervisorId"] = {"$in": supervisor_ids}
            else:
                # If no supervisors found in the area, return empty result
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No supervisors found in area: {supervisor_area}"
                )

        # Get supervisor scans
        scans_cursor = scan_events_collection.find(query_filter).sort("scannedAt", -1)
        scans = await scans_cursor.to_list(length=None)

        if not scans:
            area_msg = f" in area '{supervisor_area}'" if supervisor_area else ""
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No supervisor scan data found for the last {days_back} days{area_msg}"
            )

        # Prepare Excel data
        excel_data = []
        for scan in scans:
            excel_data.append({
                "Supervisor Name": scan.get("supervisorName", ""),
                "Site": scan.get("site", ""),
                "Post": scan.get("post", ""),
                "QR Type": scan.get("qrType", ""),
                "Scanned At": scan.get("scannedAt").strftime("%Y-%m-%d %H:%M:%S") if scan.get("scannedAt") else "",
                "Address": scan.get("address", ""),
                "Latitude": scan.get("deviceLat", ""),
                "Longitude": scan.get("deviceLng", "")
            })

        # Create Excel file
        import io
        import pandas as pd
        from fastapi.responses import StreamingResponse

        output = io.BytesIO()
        df = pd.DataFrame(excel_data)
        df.to_excel(output, index=False, sheet_name="Supervisor Scans")
        output.seek(0)

        # Generate filename
        area_suffix = f"_{supervisor_area.replace(' ', '_')}" if supervisor_area else ""
        days_suffix = f"_{days_back}days"
        filename = f"supervisor_scans_report{area_suffix}{days_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        logger.info(f"[ADMIN] Supervisor scans Excel report generated: {filename}, Records: {len(excel_data)}")

        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating supervisor scans Excel report (ADMIN): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel report: {str(e)}"
        )
