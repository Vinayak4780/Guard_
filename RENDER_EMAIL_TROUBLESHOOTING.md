# 🚨 Email OTP Issues on Render - Troubleshooting Guide

## Problem: OTP emails work locally but not on Render

### Step 1: Check Environment Variables on Render

1. **Go to your Render dashboard**
2. **Select your service**
3. **Go to Environment tab**
4. **Verify these variables are set:**

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=vi.nayak4780@gmail.com
SMTP_PASSWORD=fotn dtly lmrw zzig
SMTP_FROM_EMAIL=vi.nayak4780@gmail.com
SMTP_FROM_NAME=Guard Management System
```

⚠️ **Common Mistake**: Environment variables with spaces or quotes can cause issues.

### Step 2: Use Debug Endpoints

After deploying with the debug routes, test these endpoints:

```bash
# 1. Check email configuration
GET https://your-render-app.onrender.com/debug/email-config
Authorization: Bearer <super_admin_token>

# 2. Test email sending
POST https://your-render-app.onrender.com/debug/test-email?test_email=your-email@gmail.com
Authorization: Bearer <super_admin_token>
```

### Step 3: Check Render Logs

1. **Go to Render dashboard**
2. **Select your service**
3. **Click "Logs"**
4. **Look for email-related errors:**

```
❌ Error patterns to look for:
- "Email service not properly configured"
- "SMTP connection failed"
- "Authentication failed"
- "Connection timed out"
- "TLS/SSL errors"
```

### Step 4: Common Render-Specific Issues

#### Issue 1: Gmail App Password Not Working
**Solution**: Regenerate Gmail App Password
1. Go to Google Account settings
2. Security → 2-Step Verification → App passwords
3. Generate new 16-character password
4. Update SMTP_PASSWORD in Render

#### Issue 2: Port/Protocol Issues
**Try alternative SMTP settings**:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465  # Try this instead of 587
SMTP_USE_TLS=True
```

#### Issue 3: Environment Variable Parsing
**Check for hidden characters**:
- Copy environment variables directly (no extra spaces)
- Don't wrap values in quotes unless necessary

### Step 5: Alternative Email Providers

If Gmail continues to fail, try these providers:

#### SendGrid (Recommended for production)
```
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=<your_sendgrid_api_key>
```

#### Mailgun
```
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=<your_mailgun_username>
SMTP_PASSWORD=<your_mailgun_password>
```

### Step 6: Network/Firewall Issues

**Render might block certain SMTP ports**:
- Try port 465 (SSL) instead of 587 (TLS)
- Some cloud providers block port 25

### Step 7: Code-Level Debugging

Add logging to your super admin password change endpoint:

```python
# In routes/super_admin_routes.py
logger.info(f"🔐 Attempting to send OTP to: {super_admin_email}")
email_sent = await email_service.send_otp_email(super_admin_email, otp, "password change")
logger.info(f"📧 Email send result: {email_sent}")
```

### Step 8: Quick Fix - Manual Testing

Test with curl on Render:

```bash
# Login as super admin
curl -X POST "https://your-app.onrender.com/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=md@lhriskmgt.com&password=Test@123"

# Request password change OTP
curl -X POST "https://your-app.onrender.com/super-admin/request-password-change-otp" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json"
```

### Step 9: Immediate Workaround

If emails still don't work, temporarily log the OTP:

```python
# In super_admin_routes.py, add this after OTP generation
logger.info(f"🚨 DEBUG OTP for {super_admin_email}: {otp}")
```

**Remove this logging before production!**

---

## Most Likely Causes (in order):

1. **Environment variables not set properly on Render** (90%)
2. **Gmail App Password expired/incorrect** (5%)
3. **Port blocking by Render** (3%)
4. **SMTP configuration differences** (2%)

## Quick Checklist:

- [ ] Environment variables copied exactly to Render
- [ ] Gmail 2FA enabled and App Password generated
- [ ] No quotes around environment variable values
- [ ] Debug endpoints added and tested
- [ ] Render logs checked for SMTP errors
- [ ] Alternative SMTP provider tested if needed