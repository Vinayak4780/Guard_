"""
Supervisor routes for QR location management and guard oversight
SUPERVISOR role only - manage QR locations, view assigned guards, and access scan data
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import io
import os
from bson import ObjectId

# Import services and dependencies
from services.auth_service import get_current_supervisor
from services.tomtom_service import tomtom_service
from services.email_service import email_service
from services.jwt_service import jwt_service
#from services.excel_service import excel_service
from database import (
    get_supervisors_collection, get_guards_collection, get_qr_locations_collection,
    get_scan_events_collection, get_users_collection
)
from models import SupervisorAddGuardRequest, UserRole, SupervisorChangePasswordRequest
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
supervisor_router = APIRouter()



# ============================================================================
# NEW: Supervisor Add Building API
# ============================================================================
from fastapi import Body

@supervisor_router.post("/site/add")
async def add_site(
    site: str = Body(..., embed=True, description="Site name to be added by the supervisor"),
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    Supervisor-only: Add a new site to the system.
    Sites and QR codes are handled separately.
    """
    qr_locations_collection = get_qr_locations_collection()

    if qr_locations_collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Normalize site name and convert supervisorId to ObjectId
    normalized_site = site.strip()
    supervisor_id = ObjectId(current_supervisor["_id"]) if not isinstance(current_supervisor["_id"], ObjectId) else current_supervisor["_id"]

    # Debug logs
    print(f"Normalized site: {normalized_site}")
    print(f"Supervisor ID: {supervisor_id}")

    # Check if site already exists
    existing_site = await qr_locations_collection.find_one({
        "site": {"$regex": f"^{normalized_site}$", "$options": "i"},  # Match site
        "supervisorId": supervisor_id
    })

    print(f"Existing site query result: {existing_site}")

    if existing_site:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Site already exists."
        )

    # Add new site
    site_data = {
        "site": normalized_site,  # Save site
        "createdBy": str(current_supervisor["_id"]),
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
        "supervisorId": supervisor_id  # Use the ObjectId version for consistency
    }

    result = await qr_locations_collection.insert_one(site_data)

    return {
        "message": "Site added successfully",
        "siteId": str(result.inserted_id)
    }


# ============================================================================
# NEW: Supervisor List Buildings API
# ============================================================================
@supervisor_router.get("/sites")
async def list_sites(
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: List all sites created by the current supervisor
    Automatically shows all sites with total count
    """
    try:
        qr_locations_collection = get_qr_locations_collection()
        if qr_locations_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        supervisor_id = current_supervisor["_id"]

        # Get all distinct sites for this supervisor
        pipeline = [
            {"$match": {"supervisorId": supervisor_id}},
            {"$group": {
                "_id": "$organization",
                "site_name": {"$first": "$organization"},
                "created_at": {"$min": "$createdAt"},
                "qr_count": {"$sum": 1},
                "sites": {"$addToSet": "$site"}
            }},
            {"$sort": {"created_at": -1}}
        ]
        
        sites_cursor = qr_locations_collection.aggregate(pipeline)
        sites = await sites_cursor.to_list(length=None)

        # Total count is simply the length of sites list
        total = len(sites)

        # Format response
        formatted_sites = []
        for site in sites:
            # Include only the required fields
            formatted_sites.append({
                "qr_locations_count": site.get("qr_count", 0),
                "sites_count": len(site.get("sites", [])),
                "sites": site.get("sites", [])
            })

        return {
            "sites": formatted_sites
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sites: {str(e)}"
        )


# ============================================================================
# NEW: Supervisor List Guards API
# ============================================================================
@supervisor_router.get("/guards")
async def list_guards(
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: List all guards under the current supervisor
    Automatically shows all guards (active and inactive) with total count
    """
    try:
        guards_collection = get_guards_collection()
        
        if guards_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        supervisor_id = current_supervisor["_id"]
        
        # Build match filter for guards under this supervisor
        # Try both string and ObjectId formats for supervisorId
        guards_filter = {
            "$or": [
                {"supervisorId": str(supervisor_id)},
                {"supervisorId": supervisor_id}
            ]
        }
        
        # Find all guards for this supervisor
        guards_cursor = guards_collection.find(guards_filter).sort("createdAt", -1)
        guards_data = await guards_cursor.to_list(length=None)
        
        # Format the response
        guards = []
        for guard in guards_data:
            guard_info = {
                "guard_id": str(guard["_id"]),
                "guard_internal_id": guard.get("guardId", ""),
                "name": guard.get("name", ""),
                "email": guard.get("email", ""),
                "phone": guard.get("phone", ""),
                "area_city": guard.get("areaCity", ""),
                "is_active": guard.get("isActive", True),
                "created_at": guard.get("createdAt"),
                "created_by": guard.get("createdBy", ""),
                "supervisor_id": guard.get("supervisorId", "")
            }
            guards.append(guard_info)
        
        # Count totals
        total_guards = len(guards)
        
        # Format dates for response
        for guard in guards:
            if guard.get("created_at"):
                if hasattr(guard["created_at"], 'isoformat'):
                    guard["created_at"] = guard["created_at"].isoformat()
        
        return {
            "guards": guards,
            "total_guards": total_guards
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing guards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list guards: {str(e)}"
        )


    # --- The following code should be inside get_supervisor_dashboard, not add_building ---

@supervisor_router.get("/dashboard")
async def get_supervisor_dashboard(current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)):
    supervisors_collection = get_supervisors_collection()
    guards_collection = get_guards_collection()
    qr_locations_collection = get_qr_locations_collection()
    scan_events_collection = get_scan_events_collection()

    if (supervisors_collection is None or guards_collection is None or 
        qr_locations_collection is None or scan_events_collection is None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    supervisor_user_id = str(current_supervisor["_id"])
    supervisor_state = current_supervisor["areaCity"]

    # Get assigned guards count (guards assigned to this supervisor)
    assigned_guards = await guards_collection.count_documents({
        "supervisorId": ObjectId(supervisor_user_id)
    })

    # Get QR locations count  
    qr_locations = await qr_locations_collection.count_documents({
        "supervisorId": ObjectId(supervisor_user_id)
    })

    # Improved scan filtering logic - try multiple approaches
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Primary filter: scans linked to this supervisor
    supervisor_scan_filter = {
        "$and": [
            {"scannedAt": {"$gte": today_start}},
            {"$or": [
                {"supervisorId": str(supervisor_user_id)},
                {"supervisorId": ObjectId(supervisor_user_id)}
            ]}
        ]
    }
    
    today_scans = await scan_events_collection.count_documents(supervisor_scan_filter)
    
    # If no scans found by supervisorId, try area-based filtering
    if today_scans == 0:
        area_scan_filter = {
            "$and": [
                {"scannedAt": {"$gte": today_start}},
                {"$or": [
                    {"organization": {"$regex": supervisor_state, "$options": "i"}},
                    {"site": {"$regex": supervisor_state, "$options": "i"}},
                    {"address": {"$regex": supervisor_state, "$options": "i"}},
                    {"formatted_address": {"$regex": supervisor_state, "$options": "i"}}
                ]}
            ]
        }
        today_scans = await scan_events_collection.count_documents(area_scan_filter)

    # Get this week's scan statistics using the same logic
    week_start = today_start - timedelta(days=today_start.weekday())
    week_supervisor_filter = {
        "$and": [
            {"scannedAt": {"$gte": week_start}},
            {"$or": [
                {"supervisorId": str(supervisor_user_id)},
                {"supervisorId": ObjectId(supervisor_user_id)}
            ]}
        ]
    }
    
    this_week_scans = await scan_events_collection.count_documents(week_supervisor_filter)
    
    # If no scans found by supervisorId, try area-based filtering for the week
    if this_week_scans == 0:
        week_area_filter = {
            "$and": [
                {"scannedAt": {"$gte": week_start}},
                {"$or": [
                    {"organization": {"$regex": supervisor_state, "$options": "i"}},
                    {"site": {"$regex": supervisor_state, "$options": "i"}},
                    {"address": {"$regex": supervisor_state, "$options": "i"}},
                    {"formatted_address": {"$regex": supervisor_state, "$options": "i"}}
                ]}
            ]
        }
        this_week_scans = await scan_events_collection.count_documents(week_area_filter)

    # Get recent scan events with improved filtering
    recent_scans_filter = {
        "$or": [
            {"supervisorId": str(supervisor_user_id)},
            {"supervisorId": ObjectId(supervisor_user_id)},
            {"organization": {"$regex": supervisor_state, "$options": "i"}},
            {"site": {"$regex": supervisor_state, "$options": "i"}},
            {"address": {"$regex": supervisor_state, "$options": "i"}},
            {"formatted_address": {"$regex": supervisor_state, "$options": "i"}}
        ]
    }
    
    recent_scans_cursor = scan_events_collection.find(recent_scans_filter).sort("scannedAt", -1).limit(10)
    recent_scans = await recent_scans_cursor.to_list(length=None)

    # Get guards with most activity - use the same improved filtering
    guard_activity_pipeline = [
        {"$match": {
            "$and": [
                {"scannedAt": {"$gte": week_start}},
                {"$or": [
                    {"supervisorId": str(supervisor_user_id)},
                    {"supervisorId": ObjectId(supervisor_user_id)},
                    {"organization": {"$regex": supervisor_state, "$options": "i"}},
                    {"site": {"$regex": supervisor_state, "$options": "i"}},
                    {"address": {"$regex": supervisor_state, "$options": "i"}},
                    {"formatted_address": {"$regex": supervisor_state, "$options": "i"}}
                ]}
            ]
        }},
        {"$group": {
            "_id": "$guardEmail",
            "guard_name": {"$first": "$guardName"},
            "scan_count": {"$sum": 1}
        }},
        {"$sort": {"scan_count": -1}},
        {"$limit": 5},
        {"$project": {
            "guard_email": "$_id",
            "guard_name": 1,
            "scan_count": 1,
            "_id": 0
        }}
    ]
    guard_activity = await scan_events_collection.aggregate(guard_activity_pipeline).to_list(length=None)

    # Guard activity already has proper structure, no ObjectId conversion needed

    return {
        "statistics": {
            "assigned_guards": assigned_guards,
            "qr_locations": qr_locations,
            "today_scans": today_scans,
            "this_week_scans": this_week_scans
        },
        "recent_scans": [
            {
                "id": str(scan["_id"]),
                "guard_email": scan.get("guardEmail", ""),
                "guard_id": str(scan.get("guardId", "")),
                "qr_id": scan.get("qrId", ""),
                "original_scan_content": scan.get("originalScanContent", ""),
                "location_name": scan.get("locationName", "Unknown Location"),
                "scanned_at": scan.get("scannedAt"),
                "timestamp": scan.get("timestampIST", ""),
                "device_lat": scan.get("deviceLat", 0),
                "device_lng": scan.get("deviceLng", 0),
                "address": scan.get("address", ""),
                "formatted_address": scan.get("formatted_address", ""),
                "address_lookup_success": scan.get("address_lookup_success", False)
            }
            for scan in recent_scans
        ],
        "guard_activity": guard_activity,
        "area_info": {
            "state": supervisor_state,
            "assigned_area": current_supervisor["areaCity"],
            "state_full": current_supervisor.get("areaState"),
            "country": current_supervisor.get("areaCountry")
        }
    }


@supervisor_router.post("/generate-excel-report")
async def generate_excel_report(
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor),
    days_back: int = Query(7, ge=1, le=30, description="Number of days to include in report"),
    building_name: Optional[str] = Query(None, description="Name of the building to filter (optional)")
):
    """
    Generate Excel report of scan data for supervisor's area and send to admin
    """
    try:
        logger.info("Starting Excel report generation...")
        scan_events_collection = get_scan_events_collection()
        if scan_events_collection is None:
            logger.error("Scan events collection is None")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Calculate date range using IST
        from utils.timezone_utils import parse_ist_date_range, format_excel_datetime
        start_date, end_date = parse_ist_date_range(days_back)
        
        # Build query filter
        supervisor_id = current_supervisor["_id"]
        supervisor_area = current_supervisor.get("areaCity", "")
        
        logger.info(f"Excel report request - Days back: {days_back}, Building name: {building_name}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Supervisor ID: {supervisor_id}, Supervisor area: {supervisor_area}")
        
        # Primary query: Try both string and ObjectId for supervisorId filter
        query_filter = {
            "scannedAt": {"$gte": start_date, "$lte": end_date},
            "$or": [
                {"supervisorId": str(supervisor_id)},
                {"supervisorId": supervisor_id}
            ]
        }

        if building_name:
            # Case-insensitive search for site name
            query_filter["site"] = {"$regex": building_name, "$options": "i"}

        # Filter scans by supervisor's area and date range
        scans = await scan_events_collection.find(query_filter).to_list(length=None)
        
        # If no scans found with supervisorId, try to find scans in the supervisor's area or by building name
        if not scans:
            logger.info(f"No scans found by supervisorId, trying alternative queries")
            
            alternative_query_filter = {
                "scannedAt": {"$gte": start_date, "$lte": end_date}
            }
            
            if building_name:
                # Case-insensitive search for building name in organization field
                alternative_query_filter["organization"] = {"$regex": building_name, "$options": "i"}
            
            # Get all scans in date range matching building name (regardless of supervisorId)
            scans = await scan_events_collection.find(alternative_query_filter).to_list(length=None)
            logger.info(f"Found {len(scans)} scans using alternative query (building name: {building_name})")
            
            # If still no scans and we have supervisor area, try area-based search
            if not scans and supervisor_area:
                area_query_filter = {
                    "scannedAt": {"$gte": start_date, "$lte": end_date}
                }
                
                # Get all scans in date range and filter by organization name matching area
                all_scans = await scan_events_collection.find(area_query_filter).to_list(length=None)
                scans = [scan for scan in all_scans 
                        if supervisor_area.lower() in scan.get("organization", "").lower() 
                        or supervisor_area.lower() in scan.get("site", "").lower()]
                logger.info(f"Found {len(scans)} scans in supervisor's area: {supervisor_area}")

        if not scans:
            logger.warning("No scan data found in the specified date range")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No scan data found in the specified date range"
            )

        # Debug: Log all scan events found by query
        logger.info(f"Total scan events found: {len(scans)}")
        
        # Fetch guard details from the guards collection
        guards_collection = get_guards_collection()
        if guards_collection is None:
            logger.error("Guards collection is None")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Prepare Excel data with IST timezone conversion
        excel_data = []
        for scan in scans:
            try:
                # Convert guardId to ObjectId for querying the guards collection
                from bson import ObjectId
                guard_id = scan.get("guardId")
                if guard_id:
                    try:
                        guard_id = ObjectId(guard_id)
                    except Exception as e:
                        logger.error(f"Invalid guardId format: {guard_id}, Error: {e}")
                        guard_id = None

                # Fetch guard details using guardId
                guard = await guards_collection.find_one({"_id": guard_id}) if guard_id else None

                # Convert UTC to IST for display
                date_time = format_excel_datetime(scan.get("scannedAt"))
                site = scan.get("site", "Unknown Site")

                # Handle different guard name fields from different endpoints
                guard_name = scan.get("guardName") or scan.get("guard_name") or "Unknown Guard"

                row_data = {
                    "Date + Time (IST)": date_time,
                    "Action": "QR Code Scan",
                    "Site Name": site,
                    "Guard Name": guard_name,
                    "Latitude": scan.get("deviceLat"),
                    "Longitude": scan.get("deviceLng"),
                    "Address": scan.get("address", "Unknown Address"),
                    "Formatted Address": scan.get("formatted_address", "Unknown Formatted Address"),
                    "Scan Source": scan.get("scanSource", "Unknown Source"),
                }

                excel_data.append(row_data)

            except Exception as e:
                logger.error(f"Error processing scan: {e}")
                continue

        if not excel_data:
            logger.warning("No valid scan data found for Excel report")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No valid scan data found for Excel report"
            )


        # Create Excel file in memory and return as response
        import io
        import pandas as pd
        from fastapi.responses import StreamingResponse

        output = io.BytesIO()
        df = pd.DataFrame(excel_data)
        df.to_excel(output, index=False, sheet_name="Scan Report")
        output.seek(0)

        filename = f"scan_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}"
        }
        logger.info(f"Excel report generated successfully in memory: {filename}")
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error generating Excel report: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the report: {str(e)}"
        )


# ============================================================================
# SUPERVISOR: Add Guard API
# ============================================================================

@supervisor_router.post("/add-guard")
async def add_guard(
    guard_data: SupervisorAddGuardRequest,
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: Add a new guard to the system
    Creates guard account and saves data only in the guards collection.
    """
    try:
        guards_collection = get_guards_collection()

        if guards_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        supervisor_id = str(current_supervisor["_id"])
        supervisor_name = current_supervisor.get("name", current_supervisor.get("email", "Supervisor"))
        supervisor_area = current_supervisor.get("areaCity", "Unknown")

        # Generate a simple guard ID
        guard_count = await guards_collection.count_documents({})
        guard_id = f"guard_{guard_count + 1}"

        # Hash the password
        hashed_password = jwt_service.hash_password(guard_data.password)

        # Generate a unique employee code
        employee_code = f"EMP-{guard_count + 1:05d}"  # Example: EMP-00001

        # Generate a unique user ID
        user_id = f"user_{guard_count + 1}"  # Example: user_1

        # Check if a guard with the same email or phone already exists
        # Only check non-empty values to avoid matching empty strings
        duplicate_conditions = []
        if guard_data.email:
            duplicate_conditions.append({"email": guard_data.email})
        if guard_data.phone:
            duplicate_conditions.append({"phone": guard_data.phone})
        
        if duplicate_conditions:
            existing_guard = await guards_collection.find_one({
                "$or": duplicate_conditions
            })
            
            if existing_guard:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A guard with the same email or phone already exists."
                )

        # Process email only if provided
        if guard_data.email and not guard_data.email.endswith("@gmail.com"):
            guard_data.email = guard_data.email.split("@")[0] + "@gmail.com"

        # Create guard record
        guard_data_record = {
            "guardId": guard_id,
            "supervisorId": supervisor_id,
            "name": guard_data.name,
            "email": guard_data.email,
            "phone": guard_data.phone,
            "passwordHash": hashed_password,  # Store hashed password
            "areaCity": supervisor_area,
            "isActive": True,
            "createdBy": supervisor_id,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            "employeeCode": employee_code,  # Add unique employee code
            "userId": user_id  # Add unique user ID
        }

        # Insert guard into the guards collection
        await guards_collection.insert_one(guard_data_record)

        logger.info(f"Supervisor {supervisor_name} created guard account for {guard_data.name}")

        return {
            "message": "Guard added successfully",
            "guard": {
                "id": guard_id,
                "name": guard_data.name,
                "email": guard_data.email,
                "phone": guard_data.phone,
                "areaCity": supervisor_area,
                "supervisorId": supervisor_id,
                "supervisorName": supervisor_name,
                "createdAt": datetime.utcnow().isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding guard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add guard: {str(e)}"
        )


# ============================================================================
# SUPERVISOR: Delete Guard API
# ============================================================================

@supervisor_router.delete("/delete-guard")
async def delete_guard(
    name: str,
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: Delete a guard from the system by name only
    Removes guard from both guards and users collections
    """
    try:
        users_collection = get_users_collection()
        guards_collection = get_guards_collection()

        if users_collection is None or guards_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Verify the guard belongs to this supervisor
        supervisor_id = current_supervisor["_id"]

        # Normalize inputs
        name_normalized = name.strip()
        
        # Build search criteria
        search_criteria = {
            "name": name_normalized,  # Exact match for name
            "$or": [
                {"supervisorId": str(supervisor_id)},
                {"supervisorId": supervisor_id}
            ]
        }

        # Log the search criteria for debugging
        logger.debug(f"Search criteria for deleting guard: {search_criteria}")
        logger.debug(f"Supervisor ID type: {type(supervisor_id)}, value: {supervisor_id}")

        # Find guard
        guard = await guards_collection.find_one(search_criteria)
        
        # If not found with exact match, try with case-insensitive name
        if not guard:
            logger.debug("Exact match failed, trying case-insensitive name match")
            search_criteria["name"] = {"$regex": f"^{name_normalized}$", "$options": "i"}
            guard = await guards_collection.find_one(search_criteria)
        
        if not guard:
            # Log what we're actually looking for vs what's in the database
            logger.debug(f"Guard not found. Looking for: name='{name_normalized}', supervisorId='{supervisor_id}'")
            
            # Try to find any guards with this supervisor to debug
            all_supervisor_guards = await guards_collection.find({"$or": [
                {"supervisorId": str(supervisor_id)},
                {"supervisorId": supervisor_id}
            ]}).to_list(length=10)
            logger.debug(f"Found {len(all_supervisor_guards)} guards for this supervisor")
            for g in all_supervisor_guards:
                logger.debug(f"Existing guard: name='{g.get('name')}', email='{g.get('email')}', phone='{g.get('phone')}'")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No guard found with name '{name}' in the system"
            )

        guard_id = str(guard["_id"])
        user_id = guard.get("userId")

        # Delete from guards collection
        await guards_collection.delete_one({"_id": guard["_id"]})

        # Delete from users collection if userId exists
        if user_id:
            await users_collection.delete_one({"_id": user_id})

        logger.info(f"Supervisor {current_supervisor.get('name', 'Unknown')} deleted guard '{guard.get('name')}' with ID '{guard_id}'")

        return {"message": f"Guard '{guard.get('name')}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting guard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete guard: {str(e)}"
        )


# ============================================================================
# SUPERVISOR: Change Guard Password API
# ============================================================================

@supervisor_router.put("/change-guard-password")
async def change_guard_password(
    request: SupervisorChangePasswordRequest,
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: Change password for a guard under their supervision
    """
    try:
        guards_collection = get_guards_collection()
        users_collection = get_users_collection()

        if guards_collection is None or users_collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        supervisor_id = current_supervisor["_id"]

        # Ensure at least one contact method is provided
        if not request.guardEmail and not request.guardPhone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either guardEmail or guardPhone must be provided"
            )

        # Build search criteria for guard
        guard_search = {
            "$and": [
                {
                    "$or": [
                        {"supervisorId": str(supervisor_id)},
                        {"supervisorId": supervisor_id}
                    ]
                }
            ]
        }

        # Add email or phone condition
        contact_conditions = []
        if request.guardEmail:
            contact_conditions.append({"email": request.guardEmail})
        if request.guardPhone:
            contact_conditions.append({"phone": request.guardPhone})
        
        # Add contact filter (we know at least one exists due to validation above)
        guard_search["$and"].append({"$or": contact_conditions})

        # Find the guard and verify they're under this supervisor
        guard = await guards_collection.find_one(guard_search)

        if not guard:
            contact_info = request.guardEmail or request.guardPhone
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guard with contact {contact_info} not found or not under your supervision"
            )

        # Hash the new password
        new_password_hash = jwt_service.hash_password(request.newPassword)

        # Update password in guards collection
        await guards_collection.update_one(
            {"_id": guard["_id"]},
            {
                "$set": {
                    "passwordHash": new_password_hash,
                    "updatedAt": datetime.utcnow()
                }
            }
        )

        # Also update in users collection if guard has a user record
        user_update_criteria = {}
        if request.guardEmail:
            user_update_criteria["email"] = request.guardEmail
        elif request.guardPhone:
            user_update_criteria["phone"] = request.guardPhone

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

        contact_info = request.guardEmail or request.guardPhone
        logger.info(f"Supervisor {current_supervisor.get('name', 'Unknown')} changed password for guard {contact_info}")

        return {
            "message": f"Password changed successfully for guard {contact_info}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing guard password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change guard password: {str(e)}"
        )


# ============================================================================
# SUPERVISOR: Scan Admin QR Codes
# ============================================================================

from fastapi import Body

@supervisor_router.post("/scan-admin-qr")
async def supervisor_scan_admin_qr(
    qr_data: str = Body(..., description="QR code data scanned by supervisor"),
    device_lat: float = Body(..., description="Device latitude"),
    device_lng: float = Body(..., description="Device longitude"),
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    SUPERVISOR ONLY: Scan QR codes created by admin.
    Records scan events for admin-created QR codes with location tracking.
    """
    try:
        from database import get_qr_locations_collection
        
        qr_locations_collection = get_qr_locations_collection()
        scan_events_collection = get_scan_events_collection()

        if qr_locations_collection is None or scan_events_collection is None:
            raise HTTPException(status_code=503, detail="Database not available")

        # Parse QR data - expected format: "ADMIN:site:post:qr_id"
        qr_parts = qr_data.strip().split(":")
        if len(qr_parts) != 4 or qr_parts[0] != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR code format. Expected admin QR code."
            )

        _, site, post, qr_id = qr_parts

        # Verify QR location exists and was created by admin
        try:
            qr_object_id = ObjectId(qr_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR ID format"
            )

        qr_location = await qr_locations_collection.find_one({
            "_id": qr_object_id,
            "createdBy": "ADMIN",
            "site": site,
            "post": post
        })

        if not qr_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR location not found or not created by admin"
            )

        # Get address from coordinates using TomTom service
        address_info = await tomtom_service.get_address_from_coordinates(device_lat, device_lng)
        
        # Create scan event record
        scan_event = {
            "qrId": qr_object_id,
            "supervisorId": current_supervisor["_id"],
            "adminId": qr_location.get("adminId"),
            "supervisorEmail": current_supervisor.get("email", ""),
            "supervisorName": current_supervisor.get("name", ""),
            "site": site,
            "post": post,
            "organization": qr_location.get("organization", ""),
            "scannedAt": datetime.utcnow(),
            "scannedBy": "SUPERVISOR",
            "qrType": "ADMIN_CREATED",
            "address": address_info.get("formatted_address", ""),
            "deviceLat": device_lat,
            "deviceLng": device_lng,
            "timestampIST": datetime.utcnow().isoformat()
        }

        # Insert scan event
        scan_result = await scan_events_collection.insert_one(scan_event)
        scan_event_id = str(scan_result.inserted_id)

        logger.info(f"Supervisor {current_supervisor.get('name')} scanned admin QR code {qr_id} at {site}-{post}")

        return {
            "message": "Admin QR code scanned successfully",
            "scan_event_id": scan_event_id,
            "qr_id": qr_id,
            "site": site,
            "post": post,
            "qr_type": "ADMIN_CREATED",
            "scanned_at": scan_event["scannedAt"].isoformat(),
            "supervisor_name": current_supervisor.get("name", ""),
            "location": {
                "latitude": device_lat,
                "longitude": device_lng,
                "address": address_info.get("formatted_address", ""),
                "address_lookup_success": address_info.get("success", False)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning admin QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan admin QR code: {str(e)}"
        )




