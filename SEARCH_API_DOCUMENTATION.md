# Super Admin Search Users API - Updated Documentation

## Endpoint
`GET /super-admin/search-users`

## Description
SUPER_ADMIN ONLY: Search for users across all collections by name, email, phone, or state with special role mapping functionality.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | No | Search by name, email, or phone. Special keywords: 'fieldofficer' searches supervisors, 'supervisor' searches guards |
| `state` | string | No | Filter by state/area |

## Special Role Mapping

This API implements a unique role mapping system:

- **`fieldofficer`** or **`field-officer`** or **`field officer`** → Searches for SUPERVISORS
- **`supervisor`** → Searches for GUARDS  
- **Any other query** → Normal search across all collections by name, email, or phone

## Response Format

```json
{
  "users": [
    {
      "id": "string",
      "name": "string", 
      "email": "string",
      "phone": "string",
      "role": "ADMIN|SUPERVISOR|GUARD",
      "areaCity": "string",
      "isActive": boolean,
      "createdAt": "ISO string",
      "lastLogin": "ISO string|null",
      "collection": "users|supervisors|guards",
      "code": "string",           // Only for supervisors
      "employeeCode": "string",   // Only for guards
      "supervisorId": "string"    // Only for guards
    }
  ],
  "total": number,
  "filters": {
    "query": "string|null",
    "state": "string|null"
  }
}
```

## Examples

### Normal Search by Name
```
GET /super-admin/search-users?query=john
```
Returns all users (admins, supervisors, guards) with "john" in their name, email, or phone.

### Search by Email
```
GET /super-admin/search-users?query=john@example.com
```
Returns users matching the email across all collections.

### Search for Supervisors (using role mapping)
```
GET /super-admin/search-users?query=fieldofficer
```
Returns only SUPERVISORS from the supervisors collection.

### Search for Guards (using role mapping)
```
GET /super-admin/search-users?query=supervisor
```
Returns only GUARDS from the guards collection.

### Search by State
```
GET /super-admin/search-users?state=california
```
Returns all users from California across all collections.

### Combined Search
```
GET /super-admin/search-users?query=john&state=california
```
Returns users with "john" in their details who are located in California.

## Key Changes from Previous Version

1. **Removed pagination** - No more `page` and `limit` parameters
2. **Removed role filter** - No more `role` parameter
3. **Added role mapping** - Special keywords for searching specific collections
4. **Returns all results** - No pagination, returns complete result set
5. **Simplified response** - Removed `page` and `totalPages` from response

## Authentication
Requires Bearer token with SUPER_ADMIN role.

## Error Responses

- `401 Unauthorized` - Invalid or missing authentication token
- `403 Forbidden` - User does not have SUPER_ADMIN role
- `503 Service Unavailable` - Database connection issues
- `500 Internal Server Error` - Server error during search

## Notes

- The role mapping is case-insensitive
- Results are sorted by creation date (newest first)  
- The `collection` field in response indicates which database collection the user was found in
- Search is performed using regex with case-insensitive matching
- All date fields are formatted as ISO strings in the response