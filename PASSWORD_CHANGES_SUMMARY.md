# Password Management API Changes Summary

## Overview
This document summarizes the changes made to the LHRM app's password management system based on the requirements:

1. Removed signup-related APIs
2. Modified password change functionality to support phone OR email
3. Removed self password change APIs for admin, supervisor, and guard
4. Only super admin can change their own password
5. Added search functionality for super admin

## APIs Removed

### Signup-Related APIs (Completely Removed)
- ❌ `POST /auth/signup` - Signup
- ❌ `POST /auth/verify-otp` - Verify OTP
- ❌ `POST /auth/reset-password` - Reset Password
- ❌ `POST /auth/reset-password-confirm` - Reset Password Confirm
- ❌ `POST /auth/resend-otp` - Resend OTP

### Self Password Change APIs (Removed)
- ❌ `PUT /supervisor/change-password` - Change Supervisor Password
- ❌ `PUT /admin/change-password` - Change Admin Password  
- ❌ `PUT /guard/change-password` - Change Guard Password

## APIs Modified/Added

### Password Change APIs (Support Phone OR Email)

#### Supervisor APIs
- ✅ `PUT /supervisor/change-guard-password` - Supervisor can change guard passwords
  - **Input**: `guardEmail` OR `guardPhone` + `newPassword`
  - **Validation**: Guard must be under supervisor's supervision

#### Admin APIs  
- ✅ `PUT /admin/change-supervisor-password` - Admin can change supervisor passwords
  - **Input**: `userEmail` OR `userPhone` + `newPassword`
  - **Validation**: Supervisor must exist in system

#### Super Admin APIs
- ✅ `PUT /super-admin/change-user-password` - Super admin can change ANY user password
  - **Input**: `userEmail` OR `userPhone` + `newPassword`
  - **Validation**: Searches across all collections (users, supervisors, guards)

- ✅ `PUT /super-admin/change-password` - Super admin can change own password
  - **Input**: `currentPassword` + `newPassword`
  - **Validation**: Verifies current password

- ✅ `GET /super-admin/search-users` - Search users across all collections
  - **Query Parameters**: 
    - `query` (search by name, email, phone)
    - `state` (filter by state)
    - `role` (filter by role: admin, supervisor, guard)
    - `page`, `limit` (pagination)

## Data Models Updated

### Password Change Request Models

```python
class AdminChangePasswordRequest(BaseModel):
    userEmail: Optional[str] = None
    userPhone: Optional[str] = None
    newPassword: str = Field(..., min_length=8)
    
    @model_validator(mode='after')
    def validate_contact_info(self):
        if not self.userEmail and not self.userPhone:
            raise ValueError('Either userEmail or userPhone must be provided')
        return self

class SupervisorChangePasswordRequest(BaseModel):
    guardEmail: Optional[str] = None  
    guardPhone: Optional[str] = None
    newPassword: str = Field(..., min_length=8)
    
    @model_validator(mode='after')
    def validate_contact_info(self):
        if not self.guardEmail and not self.guardPhone:
            raise ValueError('Either guardEmail or guardPhone must be provided')
        return self

class SuperAdminChangePasswordRequest(BaseModel):
    userEmail: Optional[str] = None
    userPhone: Optional[str] = None
    newPassword: str = Field(..., min_length=8)
    
    @model_validator(mode='after')
    def validate_contact_info(self):
        if not self.userEmail and not self.userPhone:
            raise ValueError('Either userEmail or userPhone must be provided')
        return self

class ChangePasswordRequest(BaseModel):
    """Only used by super admin for self password change"""
    currentPassword: str = Field(..., description="Current password")
    newPassword: str = Field(..., min_length=8, description="New password")
```

## Password Change Hierarchy

1. **Super Admin** → Can change password for:
   - ✅ Own password (with current password verification)
   - ✅ Any admin password
   - ✅ Any supervisor password
   - ✅ Any guard password

2. **Admin** → Can change password for:
   - ❌ Own password (REMOVED)
   - ✅ Supervisor passwords

3. **Supervisor** → Can change password for:
   - ❌ Own password (REMOVED)
   - ✅ Guard passwords (only guards under their supervision)

4. **Guard** → Can change password for:
   - ❌ Own password (REMOVED)

## Search Functionality

### Super Admin Search Users API
- **Endpoint**: `GET /super-admin/search-users`
- **Features**:
  - Search across all collections (users, supervisors, guards)
  - Search by name, email, or phone
  - Filter by state/area
  - Filter by role (admin, supervisor, guard)
  - Pagination support
  - Returns unified user data with role identification

## Security Enhancements

1. **Contact Method Flexibility**: All password change APIs now accept either email OR phone
2. **Proper Validation**: Database searches use appropriate criteria for both email and phone
3. **Collection Updates**: Password changes update both primary collection and users collection when applicable
4. **Audit Logging**: All password changes are logged with proper context
5. **Role-based Access**: Strict hierarchy enforcement for password changes

## Files Modified

### Route Files
- `routes/auth_routes.py` - Removed signup APIs and OTP functions
- `routes/supervisor_routes.py` - Removed self password change, updated guard password change
- `routes/admin_routes_working.py` - Removed self password change, updated supervisor password change  
- `routes/guard_routes_simple.py` - Removed self password change API
- `routes/super_admin_routes.py` - Updated user password change, added search API

### Model Files
- `models.py` - Updated password change request models with phone/email support

### Test Files
- `test_password_apis.py` - Comprehensive test suite for new password APIs

## Testing

A comprehensive test script has been created (`test_password_apis.py`) that validates:
- All password change APIs with different roles
- Phone and email support
- Search functionality
- Error handling
- Authentication requirements

## Next Steps

1. Update API documentation to reflect new endpoints
2. Update frontend applications to use new password change flow
3. Train administrators on new password management hierarchy
4. Consider adding password policy enforcement
5. Add password change notifications/emails

## Notes

- All password changes require proper authentication tokens
- Password hashing uses bcrypt for security
- Database updates are atomic and include proper error handling
- Logs are maintained for audit purposes
- Phone number searches may need normalization for consistency