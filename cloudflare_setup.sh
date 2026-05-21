#!/bin/bash
# Cloudflare DNS + TLS setup for hvsold.com → KVM4 (92.112.184.45)
# Run: bash cloudflare_setup.sh <CF_API_TOKEN>
# Requires: curl, certbot

CF_TOKEN="${1:?Usage: cloudflare_setup.sh <CF_API_TOKEN>}"
CF_EMAIL="glennf35@gmail.com"
SERVER_IP="92.112.184.45"
ZONE_NAME="hvsold.com"

echo "=== Cloudflare DNS Setup for $ZONE_NAME ==="

# Get Zone ID
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'])")
echo "Zone ID: $ZONE_ID"

create_record() {
  local NAME=$1 TYPE=$2 CONTENT=$3 PROXIED=$4
  echo -n "Creating $TYPE $NAME → $CONTENT (proxied=$PROXIED)... "
  RESULT=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    -H "Authorization: Bearer $CF_TOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"$TYPE\",\"name\":\"$NAME\",\"content\":\"$CONTENT\",\"proxied\":$PROXIED,\"ttl\":1}")
  echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else d.get('errors'))"
}

# DNS Records
create_record "api.hvsold.com"    "A" "$SERVER_IP" "true"
create_record "widget.hvsold.com" "A" "$SERVER_IP" "true"

# Store zone ID for later use
echo "CF_TOKEN=$CF_TOKEN"    >> /root/omni-anchor/.env
echo "CF_ZONE_ID=$ZONE_ID"  >> /root/omni-anchor/.env
echo "CF_EMAIL=$CF_EMAIL"   >> /root/omni-anchor/.env

echo ""
echo "=== DNS records created. Waiting 10s for propagation... ==="
sleep 10

echo ""
echo "=== Installing certbot Cloudflare plugin ==="
apt-get install -y -qq certbot python3-certbot-dns-cloudflare

cat > /root/.cf-credentials.ini << CFCRED
dns_cloudflare_api_token = $CF_TOKEN
CFCRED
chmod 600 /root/.cf-credentials.ini

echo ""
echo "=== Requesting Let's Encrypt wildcard cert ==="
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cf-credentials.ini \
  -d "hvsold.com" \
  -d "*.hvsold.com" \
  --email "$CF_EMAIL" \
  --agree-tos \
  --non-interactive

# Update nginx to use Let's Encrypt cert
CERT_PATH="/etc/letsencrypt/live/hvsold.com"
sed -i "s|/etc/letsencrypt/live/[^/]*/fullchain.pem|$CERT_PATH/fullchain.pem|g" /root/omni-anchor/nginx/nginx.conf
sed -i "s|/etc/letsencrypt/live/[^/]*/privkey.pem|$CERT_PATH/privkey.pem|g" /root/omni-anchor/nginx/nginx.conf

# Reload nginx
docker compose -f /root/omni-anchor/docker-compose.yml restart nginx

echo ""
echo "=== DONE ==="
echo "api.hvsold.com    → https://api.hvsold.com"
echo "widget.hvsold.com → https://widget.hvsold.com"
echo ""
echo "Run next: bash /root/omni-anchor/fello_webhook_migrate.sh"
