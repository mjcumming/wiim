# Token Troubleshooting Guide

## Problem: "401: Unauthorized" Error

When running the test suite, you might see:

```
❌ Connection failed: HTTP 401
```

## Why This Happens

Your token is technically valid (correct format, not expired) but Home Assistant doesn't recognize it.

### Common Causes:

1. **Token from Different Instance**

   - Token was created on a different HA installation
   - You have multiple HA instances (dev/prod)

2. **Token Was Revoked**

   - Token was manually deleted from HA settings
   - User account was changed

3. **HA Was Reset/Restored**

   - HA was restored from backup
   - Database was reset
   - User credentials were changed

4. **Wrong User Account**
   - Token belongs to a different user
   - User doesn't have admin permissions

---

## ✅ Solution: Create a Fresh Token

### Step 1: Access Home Assistant

Open your browser and go to:

```
http://homeassistant.local:8123
```

Or use the IP address directly:

```
http://192.168.1.145:8123
```

### Step 2: Navigate to Profile

1. Click your **profile icon** (bottom left)
2. Scroll down to **"Long-Lived Access Tokens"**

### Step 3: Create New Token

1. Click **"Create Token"**
2. Enter a name: `WiiM Device Testing`
3. Click **"OK"**
4. **IMMEDIATELY COPY THE TOKEN** (you can't see it again!)

The token will look like this:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ...
```

### Step 4: Test the Token

```bash
# Set the token
export HA_TOKEN="paste_your_new_token_here"

# Test it works
curl -H "Authorization: Bearer $HA_TOKEN" \
  http://homeassistant.local:8123/api/

# Should return: {"message":"API running."}
```

### Step 5: Run Tests

```bash
python /workspaces/wiim/scripts/test-real-devices.py http://homeassistant.local:8123
```

---

## Verifying Token in HA

### Check Active Tokens

1. Go to Profile → Long-Lived Access Tokens
2. You should see your tokens listed:
   - Name
   - Created date
   - Last used date

### Revoke Old Tokens

If you see old/unused tokens:

1. Click the **trash icon** next to them
2. Confirm deletion
3. Create fresh token for testing

---

## Token Best Practices

### ✅ DO:

- Create tokens with descriptive names
- Store tokens securely (environment variables)
- Revoke tokens when done testing
- Use different tokens for different purposes

### ❌ DON'T:

- Share tokens publicly
- Commit tokens to git
- Use production tokens for testing
- Leave unused tokens active

---

## Advanced: Token Information

### Your Current Token Analysis:

**Format:** Valid JWT (JSON Web Token)
**Structure:**

- Header: Algorithm (HS256) and type (JWT)
- Payload: Issuer ID, issued-at time, expiration time
- Signature: HMAC signature for verification

**Expiration:**

- Most tokens expire after some time
- Your token was set to expire in 2035 (10 years)
- This is normal for long-lived tokens

**Issuer ID:**

- Format: 32-character hex string
- Example: `57b22358fe734b5fb8014b5a94a2ab22`
- Unique to the user/instance that created it

---

## Still Having Issues?

### Check HA Logs

```bash
# View recent HA logs
docker logs homeassistant | tail -50

# Or in HA UI:
# Settings → System → Logs
```

### Verify Network

```bash
# Test HA is accessible
ping homeassistant.local

# Test HA is responding
curl -I http://homeassistant.local:8123
```

### Try IP Address Instead

```bash
# Use IP directly
python scripts/test-real-devices.py http://192.168.1.145:8123
```

---

## Contact Support

If you're still having issues:

1. **Check Token Format**

   - Should be ~140+ characters
   - Three parts separated by dots
   - Only letters, numbers, dashes, underscores

2. **Verify HA Version**

   - Requires Home Assistant 2021.1 or newer
   - Check: Settings → About

3. **Check User Permissions**
   - User must have admin access
   - Check: Settings → People → Your User

---

## Quick Reference

### Create Token

Profile → Long-Lived Access Tokens → Create Token

### Test Token

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://homeassistant.local:8123/api/
```

### Run Tests

```bash
export HA_TOKEN="your_token"
python scripts/test-real-devices.py http://homeassistant.local:8123
```

### Expected Output

```
✅ Connected to Home Assistant
✅ Found X WiiM device(s)
✅ All tests passed
```

---

**Once you have a valid token, the tests will run perfectly!** 🎉
