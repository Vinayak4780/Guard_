# Admin-Controlled QR Code Management System

## Overview
Created 3 new QR management APIs that are controlled by admin instead of supervisor:

## 1. Admin Create QR Code
**Endpoint:** `POST /admin/qr/create`
**Access:** Admin only
**Purpose:** Admin can create QR codes for sites and posts

**Request Body:**
```json
{
  "site": "Google",
  "post_name": "Main Gate"
}
```

**Response:** Returns QR code image (PNG format)
**QR Content Format:** `ADMIN:site:post:qr_id`

---

## 2. Admin List QR Codes  
**Endpoint:** `GET /admin/qr/list`
**Access:** Admin only
**Purpose:** Admin can list all QR codes they created

**Query Parameters:**
- `site` (optional): Filter by site name
- `format` (optional): "json" or "html" (default: "json")

**JSON Response Example:**
```json
{
  "qr_codes": [
    {
      "qr_id": "68d394bc9de934d7834059a2",
      "site": "Google",
      "post": "Main Gate",
      "qr_content": "ADMIN:Google:Main Gate:68d394bc9de934d7834059a2",
      "qr_image": "data:image/png;base64,iVBORw0...",
      "created_by": "ADMIN",
      "admin_id": "68ca96697eeeafad1052780b",
      "created_at": "2025-10-06T12:00:00.000000",
      "updated_at": "2025-10-06T12:00:00.000000"
    }
  ],
  "total": 1,
  "site_filter": "Google",
  "message": "Found 1 admin-created QR codes for site 'Google'"
}
```

**HTML Response:** Use `?format=html` to see actual QR code images in browser

---

## 3. Supervisor Scan Admin QR Codes
**Endpoint:** `POST /supervisor/scan-admin-qr`
**Access:** Supervisor only  
**Purpose:** Supervisors can scan QR codes created by admin

**Request Body:**
```json
{
  "qr_data": "ADMIN:Google:Main Gate:68d394bc9de934d7834059a2"
}
```

**Response:**
```json
{
  "message": "Admin QR code scanned successfully",
  "scan_event_id": "68df5039ed4c484894f6c944",
  "qr_id": "68d394bc9de934d7834059a2",
  "site": "Google", 
  "post": "Main Gate",
  "qr_type": "ADMIN_CREATED",
  "scanned_at": "2025-10-06T12:30:00.000000",
  "supervisor_name": "John Smith"
}
```

---

## Key Differences from Supervisor QR Management

### Original Supervisor QRs:
- **Create:** `POST /qr/create` (Supervisor access)
- **List:** `GET /qr/list` (Supervisor access)  
- **QR Format:** `site:post:qr_id`
- **Database Field:** `supervisorId`

### New Admin QRs:
- **Create:** `POST /admin/qr/create` (Admin access)
- **List:** `GET /admin/qr/list` (Admin access)
- **Scan:** `POST /guard/scan-admin-qr` (Guard access)
- **QR Format:** `ADMIN:site:post:qr_id`
- **Database Fields:** `adminId`, `createdBy: "ADMIN"`

---

## Usage Examples

### 1. Admin creates QR code:
```bash
curl -X POST "http://localhost:8000/admin/qr/create" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"site": "Google", "post_name": "Security Gate"}'
```

### 2. Admin lists QR codes (JSON):
```bash
curl -X GET "http://localhost:8000/admin/qr/list?site=Google" \
  -H "Authorization: Bearer <admin_token>"
```

### 3. Admin views QR codes (HTML with images):
```bash
curl -X GET "http://localhost:8000/admin/qr/list?site=Google&format=html" \
  -H "Authorization: Bearer <admin_token>"
```

### 4. Guard scans admin QR:
```bash
curl -X POST "http://localhost:8000/guard/scan-admin-qr" \
  -H "Authorization: Bearer <guard_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "qr_data": "ADMIN:Google:Security Gate:68d394bc9de934d7834059a2",
    "device_lat": 28.7041,
    "device_lng": 77.1025
  }'
```

---

## Database Schema

### QR Locations (Admin-created):
```json
{
  "_id": "ObjectId",
  "site": "Google",
  "post": "Security Gate", 
  "adminId": "ObjectId",
  "createdBy": "ADMIN",
  "createdAt": "DateTime",
  "updatedAt": "DateTime"
}
```

### Scan Events (Supervisor scans):
```json
{
  "_id": "ObjectId",
  "qrId": "ObjectId",
  "guardId": "ObjectId", 
  "supervisorId": "ObjectId",
  "adminId": "ObjectId",
  "site": "Google",
  "post": "Security Gate",
  "scannedBy": "SUPERVISOR",
  "qrType": "ADMIN_CREATED",
  "scannedAt": "DateTime"
}
```

---

## Summary
✅ **Admin Create QR:** Admin creates QR codes for sites/posts  
✅ **Admin List QR:** Admin lists all their QR codes (JSON + HTML view)  
✅ **Guard Scan:** Guards scan admin-created QR codes with GPS location  
✅ **Proper Authentication:** Each endpoint restricted to correct role  
✅ **QR Differentiation:** Admin QRs prefixed with "ADMIN:" to distinguish from supervisor QRs  
✅ **Location Tracking:** Guard scans include GPS coordinates and address lookup