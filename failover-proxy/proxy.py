#!/usr/bin/env python3
"""
Claude Code failover proxy.

Claude Code is configured with ANTHROPIC_BASE_URL=http://127.0.0.1:8888.
Requests are forwarded to api.anthropic.com normally.  On 429 or 529
(rate-limited / Claude Pro resources depleted), the proxy transparently
reroutes to OpenRouter using claude-sonnet-4-6, translating between
Anthropic and OpenAI message formats.  A periodic probe checks if
Anthropic has recovered and reverts automatically.
"""

import asyncio
import json
import logging
import os
import time
from typing import AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("failover")

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
ANTHROPIC_BASE = "https://api.anthropic.com"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OR_MODEL = "anthropic/claude-sonnet-4-6"

RATE_LIMIT_CODES = {429, 529}
PROBE_INTERVAL = 60  # seconds between recovery probes

_state: dict = {
    "using_openrouter": False,
    "last_probe": 0.0,
}

app = FastAPI(title="Claude Code Failover Proxy")


# ── Header utilities ──────────────────────────────────────────────────────────

def _ant_headers(req_headers: dict) -> dict:
    """Build Anthropic-bound headers from the incoming Claude Code request."""
    out = {"content-type": "application/json"}
    for h in ("x-api-key", "authorization", "anthropic-version", "anthropic-beta"):
        if h in req_headers:
            out[h] = req_headers[h]
    return out


def _or_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hvsold.com",
        "X-Title": "OMNI-ANCHOR Claude Failover",
    }


# ── Format translation ────────────────────────────────────────────────────────

def _to_openai(body: dict) -> dict:
    """Translate Anthropic /v1/messages body → OpenAI chat completions body."""
    messages: list[dict] = []

    sys = body.get("system")
    if sys:
        if isinstance(sys, list):
            sys = " ".join(b.get("text", "") for b in sys if b.get("type") == "text")
        messages.append({"role": "system", "content": sys})

    for msg in body.get("messages", []):
        content = msg["content"]
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            )
        messages.append({"role": msg["role"], "content": content})

    out: dict = {
        "model": OR_MODEL,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 8192),
        "stream": body.get("stream", False),
    }
    for k in ("temperature", "top_p"):
        if k in body:
            out[k] = body[k]
    if "stop_sequences" in body:
        out["stop"] = body["stop_sequences"]
    return out


def _to_anthropic(oai: dict, original_model: str) -> dict:
    """Translate OpenAI chat completions response → Anthropic /v1/messages response."""
    choice = oai["choices"][0]
    content = choice["message"].get("content") or ""
    finish = choice.get("finish_reason", "stop")
    usage = oai.get("usage", {})
    return {
        "id": oai.get("id", "msg_or"),
        "type": "message",
        "role": "assistant",
        "model": original_model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn" if finish == "stop" else finish,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ── Streaming helpers ─────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _translate_or_stream(
    or_response: httpx.Response, original_model: str
) -> AsyncIterator[str]:
    """Yield Anthropic-format SSE events from an OpenRouter SSE stream."""
    msg_id = f"msg_or_{int(time.time())}"

    yield _sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": original_model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })
    yield _sse("content_block_start", {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield _sse("ping", {"type": "ping"})

    async for line in or_response.aiter_lines():
        if not line.startswith("data: "):
            continue
        raw = line[6:].strip()
        if raw == "[DONE]":
            break
        try:
            chunk = json.loads(raw)
            text = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
            if text:
                yield _sse("content_block_delta", {
                    "type": "content_block_delta", "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                })
        except (json.JSONDecodeError, IndexError, KeyError):
            continue

    yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield _sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 0},
    })
    yield _sse("message_stop", {"type": "message_stop"})


async def _or_stream_response(body: dict, original_model: str) -> AsyncIterator[str]:
    """Open an OpenRouter streaming request and yield translated SSE chunks."""
    oai_body = _to_openai(body)
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            f"{OPENROUTER_BASE}/chat/completions",
            headers=_or_headers(),
            json=oai_body,
        ) as r:
            async for chunk in _translate_or_stream(r, original_model):
                yield chunk


# ── Recovery probe ────────────────────────────────────────────────────────────

async def _probe_anthropic(ant_hdrs: dict, model: str) -> bool:
    """Return True if Anthropic responds with a non-rate-limit status."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{ANTHROPIC_BASE}/v1/messages",
                headers=ant_hdrs,
                json={"model": model, "max_tokens": 1,
                      "messages": [{"role": "user", "content": "hi"}]},
            )
        return r.status_code not in RATE_LIMIT_CODES
    except Exception:
        return False


# ── Main route ────────────────────────────────────────────────────────────────

@app.post("/v1/messages")
async def messages(request: Request) -> Response:
    body = await request.json()
    req_hdrs = {k.lower(): v for k, v in request.headers.items()}
    ant_hdrs = _ant_headers(req_hdrs)
    is_stream = bool(body.get("stream"))
    model = body.get("model", "claude-sonnet-4-6")

    # Recovery probe: once per PROBE_INTERVAL while in OR mode
    now = time.time()
    if _state["using_openrouter"] and (now - _state["last_probe"]) > PROBE_INTERVAL:
        _state["last_probe"] = now
        recovered = await _probe_anthropic(ant_hdrs, model)
        if recovered:
            log.info("✓ Anthropic recovered — reverting to Claude Pro")
            _state["using_openrouter"] = False
        else:
            log.info("↻ Anthropic still rate-limited — staying on OpenRouter")

    # ── Primary: Anthropic ────────────────────────────────────────────────────
    if not _state["using_openrouter"]:
        try:
            if is_stream:
                # Manually manage the httpx context so the connection stays open
                # after we return StreamingResponse (async with would close it).
                client = httpx.AsyncClient(timeout=300)
                stream_ctx = client.stream(
                    "POST", f"{ANTHROPIC_BASE}/v1/messages",
                    headers=ant_hdrs, json=body,
                )
                r = await stream_ctx.__aenter__()

                if r.status_code in RATE_LIMIT_CODES:
                    log.warning(f"⚡ Anthropic {r.status_code} — failing over to OpenRouter")
                    await stream_ctx.__aexit__(None, None, None)
                    await client.aclose()
                    _state["using_openrouter"] = True
                    _state["last_probe"] = time.time()
                    # fall through to OpenRouter block below
                else:
                    status = r.status_code

                    async def _forward() -> AsyncIterator[bytes]:
                        try:
                            async for chunk in r.aiter_bytes():
                                yield chunk
                        finally:
                            await stream_ctx.__aexit__(None, None, None)
                            await client.aclose()

                    return StreamingResponse(
                        _forward(),
                        status_code=status,
                        media_type="text/event-stream",
                        headers={"cache-control": "no-cache"},
                    )
            else:
                async with httpx.AsyncClient(timeout=300) as client:
                    r = await client.post(
                        f"{ANTHROPIC_BASE}/v1/messages",
                        headers=ant_hdrs, json=body,
                    )
                    if r.status_code in RATE_LIMIT_CODES:
                        log.warning(f"⚡ Anthropic {r.status_code} — failing over to OpenRouter")
                        _state["using_openrouter"] = True
                        _state["last_probe"] = time.time()
                        # fall through to OpenRouter block below
                    else:
                        return Response(
                            content=r.content,
                            status_code=r.status_code,
                            media_type="application/json",
                        )
        except Exception as e:
            log.error(f"Anthropic request exception: {e} — failing over to OpenRouter")
            _state["using_openrouter"] = True

    # ── Failover: OpenRouter ──────────────────────────────────────────────────
    log.info(f"→ OpenRouter ({OR_MODEL}) stream={is_stream}")

    if is_stream:
        return StreamingResponse(
            _or_stream_response(body, model),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-failover-backend": "openrouter"},
        )
    else:
        oai_body = _to_openai(body)
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers=_or_headers(),
                json=oai_body,
            )
            r.raise_for_status()
            return JSONResponse(
                _to_anthropic(r.json(), model),
                headers={"x-failover-backend": "openrouter"},
            )


# ── Health + passthrough ──────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": "openrouter" if _state["using_openrouter"] else "anthropic",
        "last_probe_ago": round(time.time() - _state["last_probe"], 1),
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def passthrough(request: Request, path: str) -> Response:
    req_hdrs = {k.lower(): v for k, v in request.headers.items()}
    ant_hdrs = _ant_headers(req_hdrs)
    body = await request.body()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request(
            method=request.method,
            url=f"{ANTHROPIC_BASE}/{path}",
            headers=ant_hdrs,
            content=body,
        )
    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type"),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="info")
