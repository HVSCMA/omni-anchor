# FILE 07: MTHI SANCTUARY
## Vault 3 — Encrypted Spatial Logic Graph
## ACCESS: READ-ONLY. Zero inbound operational data permitted.

---

## VAULT PURPOSE

The MTHI Sanctuary stores Glenn's proprietary spatial logic framework — the mathematical and topological models underlying the MTHI methodology. This vault exists in cognitive quarantine. No operational data from CRM systems, spoke agents, or external APIs may be written here under any circumstance.

---

## VAULT CONTENTS SCHEMA

```python
@dataclass(frozen=True)
class MTHINode:
    node_id: str
    node_type: str              # spatial | temporal | relational | archetypal
    label: str
    coordinates: tuple[float, float, float]   # 3D spatial position
    resonance_frequency: float
    linked_nodes: tuple[str, ...]             # immutable edge list
    metadata: dict

@dataclass(frozen=True)
class MTHIGraph:
    version: str
    created_at: str             # ISO 8601
    nodes: tuple[MTHINode, ...]
    topology_hash: str          # SHA-256 of full graph state — detects tampering
    encrypted: bool             # always True in production
```

---

## ENCRYPTION SPEC

- Tier 3: AES-256 at rest + envelope encryption (key stored in `/root/omni-anchor/.keys/mthi.key`)
- Key rotation: manual, by Apex Node only
- No automated key rotation — prevents silent re-encryption attacks

---

## ACCESS LOG REQUIREMENT

Every read from this vault generates an immutable audit entry:

```json
{
  "event": "mthi_vault_read",
  "caller": "<hermes-core session_id>",
  "timestamp": "<ISO 8601 UTC>",
  "nodes_accessed": ["<node_id>", ...],
  "purpose": "<Tier 2 task description>",
  "purge_confirmed": false
}
```

`purge_confirmed` is set to `true` only after the purge handler (File 05) confirms deletion.

---

## WRITE BLOCK ENFORCEMENT

Any `POST`, `PUT`, `PATCH`, or `DELETE` against this vault:
1. Is intercepted by `vault3_write_interceptor` (File 05)
2. Terminates the calling agent process
3. Writes a `CRITICAL` severity alert to audit log
4. Sends immediate Telegram notification to Apex Node
