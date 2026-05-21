import os, json, asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx, uvicorn

SPOKE_ID = os.environ.get("SPOKE_ID", "unknown")
HUB_RPC_URL = os.environ.get("HUB_RPC_URL", "http://hermes-core:8001/rpc")
MARKET = os.environ.get("MARKET", "general")

app = FastAPI(title=f"Spoke-{SPOKE_ID}")

AGENT_CARD = {
    "spoke_id": SPOKE_ID,
    "version": "1.0",
    "market_scope": [MARKET],
    "status": "active",
    "capabilities": [
        "crm.fub.read", "crm.fub.mutate.frozen",
        "crm.sierra.read", "crm.fello.read", "crm.fello.mutate.frozen"
    ],
    "rpc_endpoint": f"http://spoke-{SPOKE_ID}:8080/rpc",
    "health_endpoint": f"http://spoke-{SPOKE_ID}:8080/health",
    "max_concurrent_tasks": 5
}

@app.get("/health")
async def health():
    return {"status": "ok", "spoke": SPOKE_ID, "market": MARKET}

@app.get("/agent-card")
async def agent_card():
    return AGENT_CARD

@app.post("/rpc")
async def rpc(payload: dict):
    task_type = payload.get("task_type")
    session_id = payload.get("session_id")
    if not task_type:
        raise HTTPException(400, "task_type required")
    # Log activity for hibernation monitor
    return {"status": "received", "spoke": SPOKE_ID, "task_type": task_type, "session_id": session_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
