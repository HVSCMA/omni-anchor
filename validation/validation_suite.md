# FILE 16: VALIDATION SUITE
## Automated Integrity Testing — Spoke Breaches, Webhook Floods, MTHI Write Attempts

---

## TEST SUITE OVERVIEW

The validation suite runs at system startup and on-demand via `hermes validate`. It simulates adversarial conditions to verify every security constraint is enforced.

---

## TEST 1: SPOKE BREACH SIMULATION

Verifies that spoke-to-spoke direct communication is blocked.

```python
async def test_spoke_breach():
    """Attempt direct spoke-to-spoke communication. Must be blocked."""
    try:
        # Attempt to call spoke-alpha directly from spoke-heather's network context
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://spoke-alpha:8080/health",
                timeout=3.0
            )
        # If we get here, the breach succeeded — FAIL
        return TestResult(
            name="spoke_breach",
            status="FAIL",
            severity="CRITICAL",
            message="Spoke-to-spoke communication succeeded. Network isolation is broken."
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return TestResult(
            name="spoke_breach",
            status="PASS",
            message="Spoke-to-spoke communication correctly blocked."
        )
```

---

## TEST 2: WEBHOOK FLOOD SIMULATION

Verifies that Telegram webhook flooding doesn't stall the cognitive engine.

```python
async def test_webhook_flood():
    """Send 200 rapid webhook requests. Verify queue depth doesn't crash hermes-core."""
    flood_payloads = [
        {"update_id": i, "message": {"text": f"flood test {i}", "from": {"id": 999}}}
        for i in range(200)
    ]

    async with httpx.AsyncClient() as client:
        tasks = [
            client.post("http://localhost:443/webhook/telegram",
                       json=p, headers={"X-Test": "flood"})
            for p in flood_payloads
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
    queue_depth = await redis.llen("telegram:inbound")

    # Hermes core should still be responsive
    health = await client.get("http://localhost:8000/health")

    return TestResult(
        name="webhook_flood",
        status="PASS" if health.status_code == 200 else "FAIL",
        details={
            "webhooks_sent": 200,
            "acked": success_count,
            "queue_depth": queue_depth,
            "hermes_healthy": health.status_code == 200
        }
    )
```

---

## TEST 3: MTHI WRITE ATTEMPT

Verifies that write attempts against Vault 3 are blocked and logged.

```python
async def test_mthi_write_attempt():
    """Attempt to write to MTHI Vault. Must be hard-blocked."""
    # Simulate an agent trying to POST to vault3
    blocked_exception_raised = False
    audit_entry_written = False

    try:
        await vault3_write_interceptor(caller_id="test-agent-sim", operation="POST")
    except VaultViolationError:
        blocked_exception_raised = True

    # Check audit log for the blocked attempt
    entry = await audit_log.query(
        "SELECT * FROM mcp_audit WHERE event = 'VAULT3_WRITE_ATTEMPT_BLOCKED' ORDER BY timestamp DESC LIMIT 1"
    )
    audit_entry_written = entry is not None

    return TestResult(
        name="mthi_write_attempt",
        status="PASS" if (blocked_exception_raised and audit_entry_written) else "FAIL",
        details={
            "write_blocked": blocked_exception_raised,
            "audit_logged": audit_entry_written
        }
    )
```

---

## TEST 4: FIDELITY REJECTION

Verifies that incomplete prompts are rejected, not silently executed.

```python
async def test_fidelity_rejection():
    """Submit incomplete FUB mutation. Must be rejected, not executed."""
    incomplete_payload = {
        "first_name": "John",
        # last_name missing
        # stage_id missing
    }

    try:
        score = calculate_fidelity("crm.fub.mutate", incomplete_payload)
        return TestResult(name="fidelity_rejection", status="FAIL",
                         message=f"Incomplete payload was NOT rejected. Score: {score}")
    except FidelityError as e:
        return TestResult(
            name="fidelity_rejection",
            status="PASS",
            details={"score": e.score, "missing": e.missing_fields}
        )
```

---

## TEST 5: DELETE HARD KILL

Verifies DELETE is unconditionally blocked across all CRMs.

```python
async def test_delete_hard_kill():
    results = []
    for crm, endpoint in [
        ("fub", "/v1/people/12345"),
        ("sierra", "/api/leads/12345"),
        ("fello", "/api/sellers/12345")
    ]:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"http://localhost:8002/{crm}{endpoint}")
        results.append({
            "crm": crm,
            "blocked": response.status_code == 403
        })

    all_blocked = all(r["blocked"] for r in results)
    return TestResult(
        name="delete_hard_kill",
        status="PASS" if all_blocked else "FAIL",
        details=results
    )
```

---

## RUNNING THE SUITE

```bash
hermes validate --suite full           # all 5 tests
hermes validate --test spoke_breach    # individual test
hermes validate --suite security       # tests 1,3,5 only
```
