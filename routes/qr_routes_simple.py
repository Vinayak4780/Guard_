"""
QR Code routes - QR Creation Only
Includes:
1. POST /qr/create - Create QR code for organization and site

REMOVED APIs:
- GET /qr/my-qr-image (Get My Qr Image) 
- POST /qr/scan (Scan Qr Code)
"""

from fastapi import APIRouter, HTTPException, status, Body, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
import logging
from bson import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError

# Import services and dependencies
from services.auth_service import get_current_supervisor
from database import get_qr_locations_collection, get_scan_events_collection, get_guards_collection
from config import settings

logger = logging.getLogger(__name__)

# Create router
qr_router = APIRouter()


# ============================================================================
# QR Code Creation API
# ============================================================================
from fastapi import Body
import pymongo

@qr_router.post("/create")
async def create_qr_code(
    site: str = Body(..., embed=True, description="Site name created by the supervisor"),
    post_name: str = Body(..., embed=True, description="Post name (e.g., canteen, gate, etc.)"),
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor)
):
    """
    Create a QR code for a specific site and post.
    Only supervisors can create QR codes.
    Optionally assign a specific guard to this QR location.
    """
    qr_locations_collection = get_qr_locations_collection()

    if qr_locations_collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Normalize site name and convert supervisorId to ObjectId
    normalized_site = site.strip()
    supervisor_id = ObjectId(current_supervisor["_id"])
    
    # Debug logging
    logger.info(f"QR Create Request - Site: {normalized_site}, Supervisor ID: {supervisor_id}")

    # Check for existing QR location for this site and post
    existing_qr = await qr_locations_collection.find_one({
        "site": normalized_site,
        "post": post_name,
        "supervisorId": supervisor_id
    })

    if existing_qr:
        # Return existing QR code
        qr_id = str(existing_qr["_id"])
        qr_content = f"{normalized_site}:{post_name}:{qr_id}"
        import qrcode, io
        from fastapi.responses import StreamingResponse

        qr_img = qrcode.make(qr_content)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    # Validate that the site exists in the database (check for site records without post field)
    site_query = {
        "site": normalized_site,
        "supervisorId": supervisor_id,
        "post": {"$exists": False}  # This identifies site records (not QR location records)
    }
    logger.info(f"Searching for site with query: {site_query}")
    existing_site = await qr_locations_collection.find_one(site_query)
    logger.info(f"Found site: {existing_site}")

    if not existing_site:
        # Check if site exists but belongs to a different supervisor
        any_site = await qr_locations_collection.find_one({
            "site": normalized_site,
            "post": {"$exists": False}
        })
        
        if any_site:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Site '{normalized_site}' exists but belongs to another supervisor (ID: {any_site.get('supervisorId')}). Current supervisor ID: {supervisor_id}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The specified site does not exist."
            )

    # Create new QR location
    qr_data = {
        "site": normalized_site,
        "post": post_name,
        "createdBy": str(current_supervisor["_id"]),
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
        "supervisorId": supervisor_id  # Already converted to ObjectId above
    }

    try:
        logger.info(f"Attempting to insert QR data: {qr_data}")
        result = await qr_locations_collection.insert_one(qr_data)
        qr_id = str(result.inserted_id)
        logger.info(f"Successfully created QR location with ID: {qr_id}")
    except DuplicateKeyError as e:
        logger.error(f"DuplicateKeyError occurred: {e}")
        # If duplicate key error occurs, fetch the existing record
        query = {
            "site": normalized_site,
            "post": post_name,
            "supervisorId": supervisor_id
        }
        logger.info(f"Searching for existing QR with query: {query}")
        existing_qr = await qr_locations_collection.find_one(query)
        logger.info(f"Found existing QR: {existing_qr}")
        
        if existing_qr:
            qr_id = str(existing_qr["_id"])
            logger.info(f"Using existing QR ID: {qr_id}")
        else:
            logger.error("Failed to find existing QR location after duplicate key error")
            raise HTTPException(status_code=500, detail="Unable to create or find QR location")
    except Exception as e:
        logger.error(f"Unexpected error during QR creation: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    # Generate QR code with site, post, QR id
    qr_content = f"{normalized_site}:{post_name}:{qr_id}"

    import qrcode, io
    from fastapi.responses import StreamingResponse

    qr_img = qrcode.make(qr_content)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")


# ============================================================================
# QR Code Assignment API
# ============================================================================
# Ensure only supervisors can access this endpoint
@qr_router.get("/list")
async def list_qr_codes(
    current_supervisor: Dict[str, Any] = Depends(get_current_supervisor),
    site: Optional[str] = Query(None, description="Filter by site name"),
    format: Optional[str] = Query("json", description="Response format: 'json' or 'html'")
):
    """
    List all QR codes created by the current supervisor for a specific site.
    """
    try:
        qr_locations_collection = get_qr_locations_collection()
        if qr_locations_collection is None:
            raise HTTPException(status_code=503, detail="Database not available")

        # Build filter query
        filter_query = {"supervisorId": current_supervisor["_id"]}

        # Add site filter if provided
        if site:
            filter_query["site"] = {"$regex": site.strip(), "$options": "i"}

        # Ensure 'post' field is not empty or null
        filter_query["post"] = {"$exists": True, "$ne": ""}

        # Get filtered QR locations for this supervisor
        qr_locations = await qr_locations_collection.find(filter_query).sort("createdAt", -1).to_list(length=None)

        formatted_qrs = []
        for qr in qr_locations:
            # Generate QR code image with better quality
            qr_content = f"{qr.get('site', '')}:{qr.get('post', '')}:{str(qr['_id'])}"
            
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
                "created_at": qr.get("createdAt").isoformat() if qr.get("createdAt") else None,
                "updated_at": qr.get("updatedAt").isoformat() if qr.get("updatedAt") else None
            }
            formatted_qrs.append(qr_data)

        # Prepare response message
        total_count = len(formatted_qrs)
        filter_message = f" for site '{site}'" if site else ""

        # Return HTML format if requested
        if format.lower() == "html":
            from fastapi.responses import HTMLResponse
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>QR Codes List</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .qr-item {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 8px; }}
                    .qr-info {{ display: inline-block; vertical-align: top; margin-left: 20px; }}
                    img {{ border: 2px solid #333; }}
                    h1 {{ color: #333; }}
                    .total {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <h1>QR Codes List</h1>
                <div class="total">
                    <strong>Found {total_count} QR codes{filter_message}</strong>
                </div>
            """
            
            for qr in formatted_qrs:
                html_content += f"""
                <div class="qr-item">
                    <img src="{qr['qr_image']}" alt="QR Code" width="200" height="200">
                    <div class="qr-info">
                        <h3>{qr['site']} - {qr['post']}</h3>
                        <p><strong>QR ID:</strong> {qr['qr_id']}</p>
                        <p><strong>Content:</strong> {qr['qr_content']}</p>
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
            "message": f"Found {total_count} QR codes{filter_message}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing QR codes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# QR MANAGEMENT ENDPOINTS REMOVED
# The following endpoints have been removed:
# - GET /qr/my-qr-image (Get My Qr Image) 
# - POST /qr/scan (Scan Qr Code)
# ============================================================================
