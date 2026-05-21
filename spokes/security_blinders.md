# FILE 11: SECURITY BLINDERS
## Hub-and-Spoke Blindness Enforcement + OpenTelemetry A2A Tracking

---

## SECTION 1: HUB-AND-SPOKE BLINDNESS

The fundamental security property: **spokes cannot see each other**. All inter-spoke communication MUST route through the hub. Direct spoke-to-spoke calls are blocked at the network level.

```
ALLOWED:  spoke-heather  →  hermes-core  →  spoke-alpha
BLOCKED:  spoke-heather  ×→  spoke-alpha
```

Enforcement mechanism:
1. Docker `spoke-net` is an `internal: true` network — no internet egress
2. No spoke container has the IP or hostname of any other spoke in its environment
3. Hub's RPC server validates caller identity on every inbound call
4. iptables rules (applied at container start) drop any cross-spoke traffic

```bash
# Applied at spoke container startup via entrypoint.sh
iptables -A OUTPUT -d spoke-heather -j DROP  # spokes can't reach each other by name
iptables -A OUTPUT -d spoke-alpha -j DROP
iptables -A OUTPUT -d spoke-beta -j DROP
iptables -A OUTPUT -d spoke-gamma -j DROP
```

---

## SECTION 2: A2A PROTOCOL — AGENT CARD REGISTRY

Each spoke publishes an `agent-card.json` to the hub registry. The hub uses these cards to route delegated tasks without human intervention.

```json
{
  "spoke_id": "heather",
  "version": "1.0",
  "capabilities": [
    "crm.fub.read",
    "crm.fub.mutate.frozen",
    "crm.sierra.read",
    "crm.fello.read",
    "crm.fello.mutate.frozen"
  ],
  "market_scope": ["hudson_valley"],
  "rpc_endpoint": "http://hermes-core:8001/rpc/spoke/heather",
  "health_endpoint": "http://hermes-core:8001/health/spoke/heather",
  "max_concurrent_tasks": 5,
  "idle_timeout_minutes": 30
}
```

---

## SECTION 3: OPENTELEMETRY A2A TRACKING

All A2A calls are instrumented with OpenTelemetry spans and routed to the local Policy Decision Point (PDP) for microsegmentation enforcement.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

tracer = trace.get_tracer("omni-anchor.a2a")

async def route_task_to_spoke(task: Task, target_spoke: str) -> TaskResult:
    with tracer.start_as_current_span("a2a.route") as span:
        span.set_attribute("a2a.source", "hermes-core")
        span.set_attribute("a2a.target", target_spoke)
        span.set_attribute("a2a.task_type", task.category)
        span.set_attribute("a2a.session_id", task.session_id)

        # PDP authorization check before routing
        authorized = await pdp.authorize({
            "source": "hermes-core",
            "target": target_spoke,
            "action": task.category,
            "context": task.context
        })

        if not authorized:
            span.set_attribute("a2a.blocked", True)
            raise AuthorizationError(f"PDP denied: hermes-core → {target_spoke} for {task.category}")

        result = await spoke_rpc.call(target_spoke, task)
        span.set_attribute("a2a.success", True)
        return result
```

---

## SECTION 4: MICROSEGMENTATION RULES (PDP)

```python
PDP_RULES = [
    # Hub can send any task to any spoke
    {"source": "hermes-core", "target": "*", "action": "*", "decision": "ALLOW"},

    # Spokes can only report results back to hub
    {"source": "spoke-*", "target": "hermes-core", "action": "task.result", "decision": "ALLOW"},

    # Spokes cannot initiate new tasks
    {"source": "spoke-*", "target": "*", "action": "task.initiate", "decision": "DENY"},

    # No vault access from spokes directly
    {"source": "spoke-*", "target": "vault-*", "action": "*", "decision": "DENY"},
]
```
