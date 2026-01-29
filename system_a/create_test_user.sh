#!/bin/bash

BASE_URL="http://localhost:8000/api/v1"

echo "Creating test user..."

# Create new user
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@solarhub.com",
    "password": "Test123!@#",
    "full_name": "Test User",
    "role": "admin"
  }')

echo "Registration response: $REGISTER_RESPONSE"

# Save credentials to file
cat > test_credentials.txt << 'CREDS'
===========================================
TEST USER CREDENTIALS (for future use)
===========================================
Email: test@solarhub.com
Password: Test123!@#
Role: admin
Created: $(date)
===========================================
CREDS

echo ""
echo "✅ Test user credentials saved to: system_a/test_credentials.txt"
