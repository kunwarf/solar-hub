# Test User Credentials

**Created:** 2026-01-29

## Test User Account

```
Email:    test@solarhub.com
Password: Test123!@#
Role:     owner/admin
User ID:  4fc31ddb-dde2-4536-89cd-2dd0492e0fb8
```

## Usage

Use these credentials for:
- API testing
- Frontend testing
- Integration tests
- E2E tests

## Login Examples

### cURL
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@solarhub.com","password":"Test123!@#"}'
```

### Frontend Login
1. Navigate to http://localhost:5173
2. Email: test@solarhub.com
3. Password: Test123!@#

---

**Note:** Keep these credentials secure and do not commit them to version control in production environments.
