import os
import json
import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

NEXUS_SECRET = os.getenv("NEXUS_SECRET")
if not NEXUS_SECRET:
    raise RuntimeError("NEXUS_SECRET environment variable must be set.")

app = FastAPI(title="Phoenix Nexus Broker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # You can restrict later if desired
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected clients:
#   client_id -> {"ws": WebSocket, "node_id": str}
clients: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

async def broadcast(message: Dict[str, Any], exclude_client_id: str | None = None):
    """Broadcast a JSON message to all connected clients (optionally excluding one)."""
    dead_clients: List[str] = []

    for cid, info in clients.items():
        if exclude_client_id is not None and cid == exclude_client_id:
            continue
        ws: WebSocket = info["ws"]
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead_clients.append(cid)

    # Clean up dead connections
    for cid in dead_clients:
        try:
            clients.pop(cid, None)
        except Exception:
            pass


# ─────────────────────────────────────────────
# HTTP STATUS CHECK
# ─────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return JSONResponse({"status": "ok", "clients": len(clients)})


# ─────────────────────────────────────────────
# WEBSOCKET ENDPOINT
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Expected initial query params:
        ?node_id=<NODE_ID>&secret=<NEXUS_SECRET>
    Messages must be JSON:
        {
          "type": "SOVEREIGN_INTENT" | "NODE_SYNTHESIS" | "PING" | ...,
          "from": "<NODE_ID>",
          "payload": {...}
        }
    """
    query_params = websocket.query_params

    node_id = query_params.get("node_id")
    secret = query_params.get("secret")

    if secret != NEXUS_SECRET:
        # Reject connection if secret invalid
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not node_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    client_id = str(uuid.uuid4())
    clients[client_id] = {"ws": websocket, "node_id": node_id}

    # Notify others that a node joined (optional)
    join_msg = {
        "type": "NODE_JOIN",
        "from": node_id,
        "payload": {"node_id": node_id}
    }
    await broadcast(join_msg, exclude_client_id=client_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                # Ignore malformed messages
                continue

            msg_type = msg.get("type")
            msg_from = msg.get("from", node_id)

            # Basic normalization
            msg["from"] = msg_from

            # BROKER BEHAVIOR:
            # - SOVEREIGN_INTENT: broadcast to all nodes (including orchestrator)
            # - NODE_SYNTHESIS: broadcast to all or just orchestrator, depending on your client logic
            # - any other type: fire-and-forget broadcast
            if msg_type in ("SOVEREIGN_INTENT", "NODE_SYNTHESIS", "PING", "INFO"):
                await broadcast(msg, exclude_client_id=None)
            else:
                # Default: passthrough broadcast
                await broadcast(msg, exclude_client_id=None)

    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup on disconnect
        left = clients.pop(client_id, None)
        if left:
            node_id_left = left["node_id"]
            leave_msg = {
                "type": "NODE_LEAVE",
                "from": node_id_left,
                "payload": {"node_id": node_id_left}
            }
            await broadcast(leave_msg, exclude_client_id=None)