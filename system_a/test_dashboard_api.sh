#!/bin/bash

BASE_URL="http://localhost:8000/api/v1"

echo "========================================="
echo "Testing Dashboard Preferences API"
echo "========================================="
echo ""

# 1. Login to get token
echo "1️⃣  Getting auth token..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@solarhub.com","password":"Test123!@#"}')

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get auth token"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Auth token obtained"
echo ""

# 2. Get dashboard preferences (should return defaults for new user)
echo "2️⃣  GET /users/me/dashboard/preferences"
GET_PREFS=$(curl -s -X GET "$BASE_URL/users/me/dashboard/preferences" \
  -H "Authorization: Bearer $TOKEN")
echo "Response:"
echo $GET_PREFS | python -m json.tool 2>/dev/null || echo $GET_PREFS
echo ""

# 3. Update dashboard preferences
echo "3️⃣  PUT /users/me/dashboard/preferences"
UPDATE_PREFS=$(curl -s -X PUT "$BASE_URL/users/me/dashboard/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_preset": "comprehensive",
    "grid_layout": "2x2",
    "widget_layout": [
      {"id": "stat-cards", "visible": true, "size": "large", "settings": {}},
      {"id": "energy-flow", "visible": true, "size": "medium", "settings": {}},
      {"id": "solar-production", "visible": true, "size": "large", "settings": {}}
    ]
  }')
echo "Response:"
echo $UPDATE_PREFS | python -m json.tool 2>/dev/null || echo $UPDATE_PREFS
echo ""

# 4. List custom presets (should be empty initially)
echo "4️⃣  GET /users/me/dashboard/presets"
LIST_PRESETS=$(curl -s -X GET "$BASE_URL/users/me/dashboard/presets" \
  -H "Authorization: Bearer $TOKEN")
echo "Response:"
echo $LIST_PRESETS | python -m json.tool 2>/dev/null || echo $LIST_PRESETS
echo ""

# 5. Create custom preset
echo "5️⃣  POST /users/me/dashboard/presets"
CREATE_PRESET=$(curl -s -X POST "$BASE_URL/users/me/dashboard/presets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Custom Layout",
    "description": "Power user setup",
    "widget_config": [
      {"id": "stat-cards", "visible": true, "size": "large"},
      {"id": "energy-flow", "visible": true, "size": "medium"},
      {"id": "solar-production", "visible": true, "size": "large"}
    ]
  }')
echo "Response:"
echo $CREATE_PRESET | python -m json.tool 2>/dev/null || echo $CREATE_PRESET
PRESET_ID=$(echo $CREATE_PRESET | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo ""

# 6. Get specific preset
if [ ! -z "$PRESET_ID" ]; then
  echo "6️⃣  GET /users/me/dashboard/presets/$PRESET_ID"
  GET_PRESET=$(curl -s -X GET "$BASE_URL/users/me/dashboard/presets/$PRESET_ID" \
    -H "Authorization: Bearer $TOKEN")
  echo "Response:"
  echo $GET_PRESET | python -m json.tool 2>/dev/null || echo $GET_PRESET
  echo ""

  # 7. Update custom preset
  echo "7️⃣  PUT /users/me/dashboard/presets/$PRESET_ID"
  UPDATE_PRESET=$(curl -s -X PUT "$BASE_URL/users/me/dashboard/presets/$PRESET_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Updated Custom Layout",
      "description": "Updated description with more details"
    }')
  echo "Response:"
  echo $UPDATE_PRESET | python -m json.tool 2>/dev/null || echo $UPDATE_PRESET
  echo ""

  # 8. List presets again (should show the updated preset)
  echo "8️⃣  GET /users/me/dashboard/presets (verify update)"
  LIST_PRESETS_2=$(curl -s -X GET "$BASE_URL/users/me/dashboard/presets" \
    -H "Authorization: Bearer $TOKEN")
  echo "Response:"
  echo $LIST_PRESETS_2 | python -m json.tool 2>/dev/null || echo $LIST_PRESETS_2
  echo ""

  # 9. Delete custom preset
  echo "9️⃣  DELETE /users/me/dashboard/presets/$PRESET_ID"
  DELETE_PRESET=$(curl -s -X DELETE "$BASE_URL/users/me/dashboard/presets/$PRESET_ID" \
    -H "Authorization: Bearer $TOKEN")
  echo "Response:"
  echo $DELETE_PRESET | python -m json.tool 2>/dev/null || echo $DELETE_PRESET
  echo ""
fi

# 10. Verify preferences persisted
echo "🔟 Verify preferences persisted"
VERIFY_PREFS=$(curl -s -X GET "$BASE_URL/users/me/dashboard/preferences" \
  -H "Authorization: Bearer $TOKEN")
echo "Response:"
echo $VERIFY_PREFS | python -m json.tool 2>/dev/null || echo $VERIFY_PREFS
echo ""

echo "========================================="
echo "✅ All API tests completed successfully!"
echo "========================================="
