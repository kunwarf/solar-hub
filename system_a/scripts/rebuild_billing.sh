#!/bin/bash
# Simple billing rebuild script
# Deletes old billing records so they can be regenerated with correct timezone data

SITE_ID="${1}"
YEAR="${2}"
MONTH="${3}"

if [ -z "$SITE_ID" ] || [ -z "$YEAR" ] || [ -z "$MONTH" ]; then
    echo "Usage: $0 <site-id> <year> <month>"
    echo "Example: $0 271edc3f-f8e8-4aac-acae-78ffd8bf4643 2026 1"
    exit 1
fi

# Calculate period start and end
PERIOD_START="${YEAR}-$(printf "%02d" $MONTH)-01"
if [ "$MONTH" -eq 12 ]; then
    NEXT_YEAR=$((YEAR + 1))
    NEXT_MONTH=1
else
    NEXT_YEAR=$YEAR
    NEXT_MONTH=$((MONTH + 1))
fi
NEXT_MONTH_START="${NEXT_YEAR}-$(printf "%02d" $NEXT_MONTH)-01"
PERIOD_END=$(date -d "$NEXT_MONTH_START - 1 day" +%Y-%m-%d 2>/dev/null || date -v-1d -j -f "%Y-%m-%d" "$NEXT_MONTH_START" +%Y-%m-%d)

echo "============================================================"
echo "BILLING DATA REBUILD"
echo "============================================================"
echo "Site ID: $SITE_ID"
echo "Period: $PERIOD_START to $PERIOD_END"
echo "============================================================"
echo ""
echo "This will delete existing billing records for this period."
echo "The system will regenerate them automatically using new timezone-aware data."
echo ""
read -p "Proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Delete old billing simulations
echo ""
echo "Deleting old billing records..."

psql -U solarhub -d solar_hub << EOF
DELETE FROM billing_simulations
WHERE site_id = '$SITE_ID'
  AND period_start >= '$PERIOD_START'
  AND period_end <= '$PERIOD_END';

-- Show result
SELECT 'Deleted billing records' as status, COUNT(*) as count
FROM billing_simulations
WHERE site_id = '$SITE_ID'
  AND period_start >= '$PERIOD_START'
  AND period_end <= '$PERIOD_END';
EOF

echo ""
echo "============================================================"
echo "✓ Done!"
echo "============================================================"
echo "The billing scheduler will regenerate records automatically"
echo "using the new timezone-aware data from System B."
echo ""
echo "To trigger immediate regeneration, restart System A:"
echo "  sudo systemctl restart solarhub-platform.service"
echo "============================================================"
