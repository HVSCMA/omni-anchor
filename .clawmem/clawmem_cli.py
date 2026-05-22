#!/usr/bin/env python3
"""
ClawMem CLI — OMNI-ANCHOR v4.3
Called by Hermes hooks and directly by Willow via terminal tool.

Usage:
  python3 clawmem_cli.py recall  "<query>"          → print recalled memories
  python3 clawmem_cli.py store   "<fact>" [type]    → store a memory
  python3 clawmem_cli.py extract "<user>" "<reply>" → extract + store from turn
  python3 clawmem_cli.py stats                      → print memory stats
  python3 clawmem_cli.py hook                       → pre_llm_call hook mode (reads JSON from stdin)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("GOOGLE_API_KEY", "AIzaSyDL19hk1vUNHuKqlPHvinzPCAXq390J1lI")
os.environ.setdefault("CLAWMEM_PATH", "/root/omni-anchor/.clawmem")

import memory_engine as mem

def cmd_recall(args):
    if not args:
        print("Usage: clawmem_cli.py recall <query>", file=sys.stderr)
        sys.exit(1)
    query = " ".join(args)
    memories = mem.recall(query)
    if not memories:
        print("No relevant memories found.")
        return
    for m in memories:
        print(f"[{m['score']:.2f}] ({m['memory_type']}) {m['content']}")

def cmd_store(args):
    if not args:
        print("Usage: clawmem_cli.py store <fact> [type]", file=sys.stderr)
        sys.exit(1)
    fact = args[0]
    mtype = args[1] if len(args) > 1 else "fact"
    mem_id = mem.store(fact, memory_type=mtype)
    if mem_id > 0:
        print(f"Stored memory #{mem_id}: {fact[:80]}")
    else:
        print(f"Duplicate — already stored: {fact[:80]}")

def cmd_extract(args):
    if len(args) < 2:
        print("Usage: clawmem_cli.py extract <user_msg> <assistant_reply>", file=sys.stderr)
        sys.exit(1)
    count = mem.store_turn(args[0], args[1])
    print(f"Extracted and stored {count} new memories.")

def cmd_stats(_args):
    s = mem.stats()
    print(f"Total memories: {s['total']}")
    for t, c in s.get("by_type", {}).items():
        print(f"  {t}: {c}")

def cmd_hook(_args):
    """
    pre_llm_call hook mode.
    Reads Hermes hook JSON from stdin, recalls relevant memories,
    returns {"context": "..."} for Hermes to inject into the system prompt.
    """
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(0)
        event = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Extract query from the hook event
    event_name = event.get("hook_event_name", "")
    message = (
        event.get("message") or
        (event.get("extra") or {}).get("message") or
        (event.get("tool_input") or {}).get("command") or
        ""
    )

    if not message or len(message.strip()) < 5:
        sys.exit(0)

    try:
        memories = mem.recall(message.strip(), top_k=5, min_score=0.68)
        if not memories:
            sys.exit(0)
        context = mem.format_recall(memories)
        print(json.dumps({"context": context}))
    except Exception:
        sys.exit(0)

COMMANDS = {
    "recall":  cmd_recall,
    "store":   cmd_store,
    "extract": cmd_extract,
    "stats":   cmd_stats,
    "hook":    cmd_hook,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}. Available: {list(COMMANDS)}", file=sys.stderr)
        sys.exit(1)
    COMMANDS[cmd](sys.argv[2:])
