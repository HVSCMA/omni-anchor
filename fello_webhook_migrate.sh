#!/bin/bash
# Fello Webhook Migration: Netlify → api.hvsold.com
# Run AFTER cloudflare_setup.sh and TLS cert is live

FELLO_KEY="uiQ4jADoUGeTqaBellkEcBxxrzQvgvnj"
NEW_BASE="https://api.hvsold.com/webhooks/fello"
FELLO_API="https://api.fello.ai/public/v1"

echo "=== FELLO WEBHOOK MIGRATION ==="
echo "Source: willow-fub-glenn.netlify.app"
echo "Target: api.hvsold.com"
echo ""

# Step 1: Delete all legacy Netlify webhooks
echo "--- Removing legacy Netlify webhooks ---"
for ID in \
  "3f993abd-ed58-431d-bc6f-bb15ac009886" \
  "0fc688a9-962a-429e-a9d9-6ae90ea0dce8" \
  "96227373-9c19-420c-b079-277403de27b2" \
  "86ebf18d-c41c-4f82-aaac-7559d4481f44" \
  "ab2447ae-3031-40e3-93ab-894b9dc1db9f" \
  "fa4622b4-46b7-4823-9686-cbba7b52f860" \
  "bc750877-8034-437b-ba1b-4605ff8384b0"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    "$FELLO_API/webhooks/$ID" \
    -H "x-api-key: $FELLO_KEY")
  echo "  Deleted $ID → HTTP $STATUS"
done

# Step 2: Register all 9 event types → new KVM4 endpoint
echo ""
echo "--- Registering new KVM4 webhooks ---"
for EVENT in \
  "FormSubmission" \
  "ContactEnriched" \
  "DashboardClick" \
  "EmailClick" \
  "PostcardScan" \
  "ContactUnsubscribed" \
  "ContactDetailsUpdated" \
  "TagsAdded" \
  "TagsRemoved"; do
  RESULT=$(curl -s -X POST "$FELLO_API/webhooks" \
    -H "x-api-key: $FELLO_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$NEW_BASE\",\"eventType\":\"$EVENT\"}")
  ID=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('subscriptionId','ERROR'))" 2>/dev/null)
  echo "  $EVENT → $ID"
done

echo ""
echo "=== MIGRATION COMPLETE ==="
echo "All 9 events now route to: $NEW_BASE"

# Verify
echo ""
echo "--- Verifying registered webhooks ---"
curl -s "$FELLO_API/webhooks" -H "x-api-key: $FELLO_KEY" | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
for w in d.get('webhooks', []):
    print(f'  [{w[\"status\"]}] {w[\"eventType\"]} → {w[\"url\"]}')
"
