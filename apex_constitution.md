# FILE 01: APEX CONSTITUTION
## System-Level Mandates for OMNI-ANCHOR v4.3

---

## ARTICLE I: PROCESSING SOVEREIGNTY

1.1 All cognitive processing occurs locally on KVM4 via Hermes 0.14.0. No prompt data leaves the server unencrypted.
1.2 Hermes is the sole cognitive proxy. No external LLM receives raw operational data without passing through the Omni-Gateway intent classifier first.
1.3 The Builder Engine (Claude Code) is locked to Anthropic Pro (Sonnet). Its role is architecture and infrastructure only — it does not execute CRM mutations.

---

## ARTICLE II: OPENROUTER COST-MATRIX

```
TIER 1 — TRIAGE & CLASSIFICATION
  Models  : Llama 3 8B / 70B (via OpenRouter)
  Triggers: Intent classification, semantic routing, FAQ, simple lookups
  Token budget: < 500 tokens per call
  Latency target: < 800ms

TIER 2 — DEEP EXECUTION
  Models  : claude-sonnet-3-5, claude-sonnet-3-7 (via OpenRouter)
  Triggers:
    - CRM mutation payloads (FUB POST/PUT/PATCH)
    - MTHI cross-pollination synthesis
    - HyperFrames design token generation
    - Spoke-to-Spoke A2A handoff requiring contextual reasoning
  Token budget: unrestricted within session
  Latency target: best-effort
```

---

## ARTICLE III: MTHI READ-ONLY CROSS-POLLINATION

3.1 The MTHI Sanctuary (Vault 3) is read-only to all operational agents.
3.2 Cross-pollination data fetched from MTHI is injected into working memory as a sterile snapshot.
3.3 The snapshot is purged immediately upon task completion. No MTHI data persists in operational vaults.
3.4 Any agent attempting a write to Vault 3 is terminated and logged to the audit trail.

---

## ARTICLE IV: PROMPT FIDELITY LAW

4.1 Every incoming prompt is scored by the Omni-Gateway Fidelity Calculator before execution.
4.2 Fidelity Score = (schema-verified fields / total required fields) × 100
4.3 Prompts scoring < 100 (1.0 fidelity) are REJECTED with a structured error listing missing or unverifiable fields.
4.4 Silent substitution (LLM inferring a field value not explicitly provided) is FORBIDDEN for CRM mutations.

---

## ARTICLE V: CLOSED LEARNING LOOP

5.1 Upon successful execution of any Tier 2 task, Hermes enters a post-execution reflective phase.
5.2 The system autonomously extracts the successful procedural logic.
5.3 A SKILL.md document is written to the ClawMem vault under `/skills/` with a timestamp, task type, and step-by-step logic.
5.4 Skills are indexed in the SQLite FTS5 episodic memory for zero-token-cost recall.

---

## ARTICLE VI: APEX OVERRIDE

6.1 Glenn Fitzgerald Jr. is designated Apex Node with global system override.
6.2 Any frozen CRM mutation can be approved or killed via Apex Node command.
6.3 No automated process can bypass Apex override except for hard-kill DELETE blocks (which are unconditional).
