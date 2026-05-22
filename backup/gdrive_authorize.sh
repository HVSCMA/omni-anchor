#!/bin/bash
# OMNI-ANCHOR Google Drive One-Time Authorization
#
# Before running this script:
# Open a SECOND terminal on your LOCAL machine and run:
#   ssh -N -L 53682:localhost:53682 root@92.112.184.45
# Keep that tunnel open while you complete the browser auth.
#
# Then run this script (in this terminal):
#   bash /root/omni-anchor/backup/gdrive_authorize.sh
#
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "GOOGLE DRIVE AUTHORIZATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "STEP 1: Make sure your SSH tunnel is open:"
echo "  (run in a SEPARATE local terminal, keep it running)"
echo "  ssh -N -L 53682:localhost:53682 root@92.112.184.45"
echo ""
echo "Press Enter when the tunnel is ready, or Ctrl-C to abort."
read -r

echo ""
echo "STEP 2: Starting rclone auth server on localhost:53682..."
echo "  A browser URL will appear below."
echo "  Open it in your browser and authorize."
echo "  The page will redirect to localhost:53682 — the SSH tunnel"
echo "  forwards that back here to complete the token exchange."
echo ""

rclone config reconnect gdrive: --auth-no-open-browser

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Authorization complete. Testing connection..."
rclone lsd gdrive: && echo "✓ Google Drive connection verified"
echo ""
echo "You can now close the SSH tunnel (Ctrl-C in the other terminal)."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
