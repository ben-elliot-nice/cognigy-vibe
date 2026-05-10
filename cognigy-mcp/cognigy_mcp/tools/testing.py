from __future__ import annotations
import json
import httpx
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="talk_to_agent",
        description="Send a message to a Cognigy flow via its REST endpoint and return the response. "
                    "Use for testing flows without opening the Cognigy UI. "
                    "Provide endpoint_token (from get_build_state) or flow_id (looks up token from state). "
                    "IMPORTANT: Use a new user_id to start a completely fresh session — Cognigy caches "
                    "session state by userId and reusing one will carry stale context silently. "
                    "IMPORTANT: This tool returns text output only. Tool calls made by the agent are "
                    "NOT visible in the response — only the agent's spoken text is returned. "
                    "Pass data={verbose: true} in the request body to surface errors that are otherwise swallowed.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "endpoint_token": {"type": "string", "description": "URL token from endpoint config"},
                "flow_id": {"type": "string", "description": "Looks up token from state if endpoint_token not provided"},
                "session_id": {"type": "string", "description": "Conversation session ID — reuse to continue, new to reset"},
                "user_id": {"type": "string", "description": "User ID — new value starts fresh session"},
            },
            "required": ["message", "session_id", "user_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _talk_to_agent(args: dict) -> list[TextContent]:
        message = args["message"]
        session_id = args["session_id"]
        user_id = args["user_id"]
        token = args.get("endpoint_token")

        if not token:
            flow_id = args.get("flow_id")
            if not flow_id:
                return _ok({"error": "Provide endpoint_token or flow_id"})
            # Find endpoint token from state by matching flow reference
            endpoints = state.get("endpoints") or {}
            for ep_name, ep in endpoints.items():
                if ep.get("flowReferenceId") == flow_id or ep.get("flowId") == flow_id:
                    token = ep.get("urlToken")
                    break
            if not token:
                return _ok({"error": f"No endpoint found for flow_id={flow_id}. Run sync_remote_state or provide endpoint_token."})

        endpoint_url = f"{client.endpoint_base_url}/{token}"
        payload = {
            "userId": user_id,
            "sessionId": session_id,
            "text": message,
            "data": {},
        }

        try:
            resp = httpx.post(endpoint_url, json=payload, timeout=30.0)
            resp.raise_for_status()
            return _ok(resp.json())
        except httpx.HTTPStatusError as e:
            return _ok({"error": f"HTTP {e.response.status_code}: {e.response.text}"})
        except Exception as e:
            return _ok({"error": str(e)})

    return {"talk_to_agent": _talk_to_agent}
