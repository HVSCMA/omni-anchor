# FILE 10: DEPLOYMENT BLUEPRINT
## Multi-Tenant Spoke Array — Isolated Container Definitions

---

## SPOKE INVENTORY

```yaml
spokes:
  heather:
    container_name: spoke-heather
    description: "Hudson Valley market operations — FUB/Sierra/Fello primary"
    market: hudson_valley
    idle_hibernate: true
    hibernate_after_minutes: 30
    resources:
      cpu_limit: "1.0"
      memory_limit: "512m"
      memory_reservation: "128m"

  alpha:
    container_name: spoke-alpha
    description: "Suncoast market operations — FUB/Sierra/Fello primary"
    market: suncoast
    idle_hibernate: true
    hibernate_after_minutes: 30
    resources:
      cpu_limit: "1.0"
      memory_limit: "512m"
      memory_reservation: "128m"

  beta:
    container_name: spoke-beta
    description: "Stillway / HyperFrames design operations"
    market: stillway
    idle_hibernate: true
    hibernate_after_minutes: 60
    resources:
      cpu_limit: "0.5"
      memory_limit: "256m"
      memory_reservation: "64m"

  gamma:
    container_name: spoke-gamma
    description: "General utility — scheduling, reporting, cross-market tasks"
    market: general
    idle_hibernate: true
    hibernate_after_minutes: 45
    resources:
      cpu_limit: "0.5"
      memory_limit: "256m"
      memory_reservation: "64m"
```

---

## DOCKER COMPOSE DEFINITION

```yaml
version: "3.9"

services:

  hermes-core:
    image: nousresearch/hermes:0.14.0
    container_name: hermes-core
    restart: unless-stopped
    networks:
      - hub-net
    volumes:
      - /root/omni-anchor:/app/omni-anchor:ro
      - /root/omni-anchor/.clawmem:/app/clawmem:rw
      - /root/omni-anchor/vaults/v1-real-estate:/app/vault1:rw
      - /root/omni-anchor/vaults/v2-stillway:/app/vault2:rw
      - /root/omni-anchor/vaults/v3-mthi:/app/vault3:ro
      - /root/omni-anchor/vaults/v4-fastsigns:/app/vault4:ro
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - REDIS_URL=redis://redis:6379
    ports:
      - "8000:8000"
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  spoke-heather:
    image: omni-anchor/spoke:latest
    container_name: spoke-heather
    restart: unless-stopped
    networks:
      - spoke-net
    volumes:
      - spoke-heather-data:/data/spoke-heather:rw
    environment:
      - SPOKE_ID=heather
      - HUB_RPC_URL=http://hermes-core:8001/rpc
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,noexec

  spoke-alpha:
    image: omni-anchor/spoke:latest
    container_name: spoke-alpha
    restart: unless-stopped
    networks:
      - spoke-net
    volumes:
      - spoke-alpha-data:/data/spoke-alpha:rw
    environment:
      - SPOKE_ID=alpha
      - HUB_RPC_URL=http://hermes-core:8001/rpc
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,noexec

  spoke-beta:
    image: omni-anchor/spoke:latest
    container_name: spoke-beta
    restart: unless-stopped
    networks:
      - spoke-net
    volumes:
      - spoke-beta-data:/data/spoke-beta:rw
    environment:
      - SPOKE_ID=beta
      - HUB_RPC_URL=http://hermes-core:8001/rpc
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,noexec

  spoke-gamma:
    image: omni-anchor/spoke:latest
    container_name: spoke-gamma
    restart: unless-stopped
    networks:
      - spoke-net
    volumes:
      - spoke-gamma-data:/data/spoke-gamma:rw
    environment:
      - SPOKE_ID=gamma
      - HUB_RPC_URL=http://hermes-core:8001/rpc
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,noexec

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    networks:
      - hub-net
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru

  nginx:
    image: nginx:alpine
    container_name: nginx
    restart: unless-stopped
    networks:
      - hub-net
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro

networks:
  hub-net:
    driver: bridge
  spoke-net:
    driver: bridge
    internal: true

volumes:
  spoke-heather-data:
  spoke-alpha-data:
  spoke-beta-data:
  spoke-gamma-data:
  redis-data:
```

---

## HIBERNATION LOGIC

```python
async def spoke_hibernation_monitor():
    """Monitors spoke activity and pauses containers when idle."""
    while True:
        for spoke_id, config in SPOKE_CONFIG.items():
            last_activity = await redis.get(f"spoke:{spoke_id}:last_activity")
            if last_activity:
                idle_minutes = (utcnow() - parse_ts(last_activity)).seconds / 60
                if idle_minutes > config["hibernate_after_minutes"]:
                    await docker_client.containers.get(f"spoke-{spoke_id}").pause()
                    await audit_log.write({"event": "spoke_hibernated", "spoke": spoke_id})
        await asyncio.sleep(60)
```
