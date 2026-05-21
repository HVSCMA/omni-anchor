# FILE 02: JAILING MATRIX
## Container Isolation & Execution Security Constraints

---

## SECTION 1: DOCKER USER-SPACE NAMESPACES

All spoke containers MUST be launched with the following Docker security profile:

```yaml
security_opt:
  - no-new-privileges:true
  - seccomp:unconfined   # override per-spoke with hardened profile
userns_mode: "host"      # KVM4 kernel handles UID remapping
read_only: true
tmpfs:
  - /tmp:size=256m,noexec
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE      # only if spoke needs port binding
```

---

## SECTION 2: HYPERVISOR BAN

2.1 Nested hypervisors (KVM-in-Docker, QEMU, VirtualBox) are BANNED on KVM4.
2.2 Rationale: KVM4 is itself a KVM instance. Nested virtualization creates unmeasurable blast radius.
2.3 Any container image containing `kvm`, `qemu-kvm`, or `libvirt` is rejected at build time.

Enforcement via pre-build hook:
```bash
grep -rE "(kvm|qemu-kvm|libvirt)" Dockerfile && echo "BLOCKED: hypervisor keyword detected" && exit 1
```

---

## SECTION 3: TELEGRAM WEBHOOK ARCHITECTURE

3.1 Telegram webhooks are ASYNCHRONOUS. Hermes never blocks on Telegram API responses.
3.2 Inbound webhook payloads are dropped onto a Redis queue (`telegram:inbound`).
3.3 A separate worker process consumes the queue, preventing webhook floods from stalling the cognitive engine.

```
[Telegram API] --POST--> [nginx reverse proxy :443]
                               |
                          [Redis queue: telegram:inbound]
                               |
                    [Hermes webhook worker (async)]
                               |
                    [Omni-Gateway Intent Classifier]
```

3.4 Webhook flood protection: nginx rate-limits to 30 req/min per IP. Beyond that, returns 429.

---

## SECTION 4: NETWORK ISOLATION MATRIX

```
ALLOWED inter-container communication:
  hub (hermes-core) <-> spoke-heather
  hub (hermes-core) <-> spoke-alpha
  hub (hermes-core) <-> spoke-beta
  hub (hermes-core) <-> spoke-gamma
  hub (hermes-core) <-> clawmem-db
  hub (hermes-core) <-> redis

BLOCKED:
  spoke-* <-> spoke-*          (hub-and-spoke blindness enforced)
  spoke-* <-> clawmem-db       (vaults accessed only via hub API)
  any-container <-> internet   (except hub via controlled egress)
```

Docker network config:
```yaml
networks:
  hub-net:
    driver: bridge
    internal: false   # hub has egress
  spoke-net:
    driver: bridge
    internal: true    # spokes are air-gapped from internet
```

---

## SECTION 5: FILE SYSTEM JAILING

5.1 Each spoke container mounts only its own `/data/spoke-{name}` volume — read-write.
5.2 ClawMem vault paths are bind-mounted read-only into spokes that require cross-pollination.
5.3 The MTHI Vault path is NEVER mounted into any spoke container. Hub only.
5.4 Spoke containers cannot write to `/root`, `/etc`, or any path outside `/data/spoke-{name}` and `/tmp`.
