#!/usr/bin/env python3
"""
ClawMem post_llm_call hook — OMNI-ANCHOR v4.3
Fires after each Willow turn. Extracts facts from (user, assistant) pair
and stores them into episodic.db. Silent on failure.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("GOOGLE_API_KEY", "AIzaSyDL19hk1vUNHuKqlPHvinzPCAXq390J1lI")
os.environ.setdefault("CLAWMEM_PATH", "/root/omni-anchor/.clawmem")

try:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    event = json.loads(raw)
except Exception:
    sys.exit(0)

user_msg   = event.get("extra", {}).get("user_message") or event.get("user_message") or ""
asst_reply = event.get("extra", {}).get("assistant_response") or event.get("assistant_response") or ""
session_id = event.get("session_id") or ""

if not user_msg or not asst_reply:
    sys.exit(0)
if len(user_msg.strip()) < 8 and len(asst_reply.strip()) < 8:
    sys.exit(0)

try:
    import memory_engine as mem
    count = mem.store_turn(user_msg, asst_reply, session_id=session_id or None)
    if count:
        sys.stderr.write(f"[clawmem] stored {count} new memories\n")
except Exception as e:
    sys.stderr.write(f"[clawmem] extract_hook error: {e}\n")

sys.exit(0)
