#!/bin/sh
# Initialize the Home Assistant MQTT broker (Dynamic Security Plugin).
# Runs once as an init container; skips if data file already exists.
#
# Environment variables expected:
#   HA_MQTT_ADMIN_PASSWORD     — password for solarhub_admin account
#   HA_MQTT_PUBLISHER_PASSWORD — password for solarhub_publisher account

set -e

DYNSEC_FILE="/mosquitto/data/dynamic-security.json"
ADMIN_USER="solarhub_admin"
PUBLISHER_USER="solarhub_publisher"

ADMIN_PASSWORD="${HA_MQTT_ADMIN_PASSWORD:-admin_change_me_in_production}"
PUBLISHER_PASSWORD="${HA_MQTT_PUBLISHER_PASSWORD:-publisher_change_me_in_production}"

if [ -f "$DYNSEC_FILE" ]; then
    echo "[init_mosquitto_ha] dynsec file already exists — skipping init"
    exit 0
fi

echo "[init_mosquitto_ha] Initializing Dynamic Security Plugin..."

# Create the base dynsec file with the admin account
mosquitto_ctrl dynsec init "$DYNSEC_FILE" "$ADMIN_USER" "$ADMIN_PASSWORD"

# Connect to the temp broker via localhost to add roles and publisher.
# We use the offline dynsec management approach: pipe commands via
# mosquitto_ctrl using the file directly (Mosquitto 2.x supports this).

# Add publisher client
mosquitto_ctrl -u "$ADMIN_USER" -P "$ADMIN_PASSWORD" \
    dynsec createClient "$PUBLISHER_USER" -p "$PUBLISHER_PASSWORD" 2>/dev/null || \
    mosquitto_ctrl dynsec createClient \
        --username "$ADMIN_USER" --pw "$ADMIN_PASSWORD" \
        "$PUBLISHER_USER" "$PUBLISHER_PASSWORD" || true

# Create roles via the JSON file directly (works when broker is offline)
python3 - "$DYNSEC_FILE" "$PUBLISHER_USER" "$ADMIN_USER" <<'PYEOF'
import json, sys

path = sys.argv[1]
publisher_user = sys.argv[2]
admin_user = sys.argv[3]

with open(path) as f:
    data = json.load(f)

# Ensure clients list exists
clients = {c["username"]: c for c in data.get("clients", [])}

# HA subscriber role: can subscribe to solarhub/ha/<own-prefix>/#
# Individual user ACLs are added dynamically by System A.
# For now only the publisher and admin roles are bootstrapped here.

# Publisher role: publish to solarhub/ha/# and homeassistant/#
publisher_role = {
    "rolename": "ha_publisher",
    "textname": "HA Telemetry Publisher",
    "acls": [
        {"acltype": "publishClientSend",    "topic": "solarhub/ha/#",    "allow": True},
        {"acltype": "publishClientSend",    "topic": "homeassistant/#",  "allow": True},
        {"acltype": "publishClientReceive", "topic": "$CONTROL/#",       "allow": True},
        {"acltype": "subscribePattern",     "topic": "$CONTROL/#",       "allow": True},
    ]
}

# Admin role: full dynsec management
admin_role = {
    "rolename": "ha_admin",
    "textname": "HA Broker Admin",
    "acls": [
        {"acltype": "publishClientSend",    "topic": "$CONTROL/#", "allow": True},
        {"acltype": "publishClientReceive", "topic": "$CONTROL/#", "allow": True},
        {"acltype": "subscribePattern",     "topic": "$CONTROL/#", "allow": True},
        {"acltype": "publishClientSend",    "topic": "#",          "allow": True},
        {"acltype": "publishClientReceive", "topic": "#",          "allow": True},
        {"acltype": "subscribePattern",     "topic": "#",          "allow": True},
    ]
}

roles_map = {r["rolename"]: r for r in data.get("roles", [])}
roles_map["ha_publisher"] = publisher_role
roles_map["ha_admin"] = admin_role
data["roles"] = list(roles_map.values())

# Assign ha_publisher role to the publisher client
if publisher_user in clients:
    existing_roles = {r["rolename"] for r in clients[publisher_user].get("roles", [])}
    if "ha_publisher" not in existing_roles:
        clients[publisher_user].setdefault("roles", []).append({"rolename": "ha_publisher"})

# Assign ha_admin role to the admin client
if admin_user in clients:
    existing_roles = {r["rolename"] for r in clients[admin_user].get("roles", [])}
    if "ha_admin" not in existing_roles:
        clients[admin_user].setdefault("roles", []).append({"rolename": "ha_admin"})

data["clients"] = list(clients.values())

# Set default deny (all clients start with no access unless a role grants it)
data["defaultACLAction"] = {
    "publishClientSend":    "deny",
    "publishClientReceive": "deny",
    "subscribe":            "deny",
    "unsubscribe":          "allow"
}

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(f"[init_mosquitto_ha] Roles and ACLs applied to {path}")
PYEOF

echo "[init_mosquitto_ha] Initialization complete"
