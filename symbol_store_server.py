"""MCP server for SignalZero symbol store.

This server exposes tools backed by the OpenAPI specification in
``aws/global_symbols_openapi.yaml``. It forwards tool invocations to the
remote AWS API Gateway instance and returns JSON responses as text
content for clients to consume.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

ROOT_DIR = Path(__file__).parent
DEFAULT_SPEC_PATH = ROOT_DIR / "aws" / "global_symbols_openapi.yaml"
DEFAULT_BASE_URL = "https://qnw96whs57.execute-api.us-west-2.amazonaws.com/prod"


class SymbolStoreClient:
    """Lightweight HTTP client for the symbol store API."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers: Dict[str, str] = {"Accept": "application/json"}
        if api_key:
            self.headers["x-api-key"] = api_key
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        ) as client:
            response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    async def query_symbols(
        self,
        *,
        symbol_domain: Optional[str] = None,
        symbol_tag: Optional[str] = None,
        last_symbol_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        params = {
            key: value
            for key, value in {
                "symbol_domain": symbol_domain,
                "symbol_tag": symbol_tag,
                "last_symbol_id": last_symbol_id,
                "limit": limit,
            }.items()
            if value is not None
        }
        response = await self._request("GET", "/symbol", params=params)
        return response.json()

    async def get_symbol(self, symbol_id: str) -> Any:
        response = await self._request("GET", f"/symbol/{symbol_id}")
        return response.json()

    async def put_symbol(self, symbol_id: str, payload: Dict[str, Any]) -> Any:
        response = await self._request("PUT", f"/save_symbol/{symbol_id}", json=payload)
        return response.json()

    async def list_domains(self) -> Any:
        response = await self._request("GET", "/domains")
        return response.json()


def load_spec(path: Path = DEFAULT_SPEC_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_tools_from_spec(spec: Dict[str, Any]) -> list[Tool]:
    return [
        Tool(
            name="query_symbols",
            description=spec["paths"]["/symbol"]["get"].get("summary", "Query symbols"),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol_domain": {"type": "string", "description": "Filter by domain"},
                    "symbol_tag": {"type": "string", "description": "Filter by tag"},
                    "last_symbol_id": {"type": "string", "description": "Start after ID"},
                    "limit": {"type": "integer", "description": "Maximum results"},
                },
            },
        ),
        Tool(
            name="get_symbol_by_id",
            description=spec["paths"]["/symbol/{id}"]["get"].get("summary", "Get symbol by ID"),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Symbol identifier"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="put_symbol_by_id",
            description=spec["paths"]["/save_symbol/{symbol_id}"]["put"].get("summary", "Save symbol"),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol_id": {"type": "string", "description": "Symbol identifier"},
                    "symbol": spec["components"]["schemas"]["Symbol"],
                },
                "required": ["symbol_id", "symbol"],
            },
        ),
        Tool(
            name="list_domains",
            description=spec["paths"]["/domains"]["get"].get("summary", "List symbol domains"),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def format_json_payload(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


server = Server("signalzero-symbol-store")
spec_cache = load_spec()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return build_tools_from_spec(spec_cache)


def build_client() -> SymbolStoreClient:
    base_url = os.getenv("SYMBOL_STORE_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.getenv("SYMBOL_STORE_API_KEY")
    return SymbolStoreClient(base_url=base_url, api_key=api_key)


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    client = build_client()

    try:
        if name == "query_symbols":
            data = await client.query_symbols(
                symbol_domain=arguments.get("symbol_domain"),
                symbol_tag=arguments.get("symbol_tag"),
                last_symbol_id=arguments.get("last_symbol_id"),
                limit=arguments.get("limit"),
            )
            message = "Query results" if data else "No symbols returned"
            text = f"{message}:\n{format_json_payload(data)}"

        elif name == "get_symbol_by_id":
            data = await client.get_symbol(arguments["id"])
            text = format_json_payload(data)

        elif name == "put_symbol_by_id":
            symbol_id = arguments["symbol_id"]
            symbol_body = arguments["symbol"]
            data = await client.put_symbol(symbol_id, symbol_body)
            text = f"Stored symbol {symbol_id}:\n{format_json_payload(data)}"

        elif name == "list_domains":
            data = await client.list_domains()
            text = f"Available domains:\n{format_json_payload(data)}"

        else:
            text = f"Unknown tool: {name}"

    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        text = (
            f"Request to {exc.request.method} {exc.request.url} failed with status "
            f"{exc.response.status_code}: {body}"
        )

    return [TextContent(type="text", text=text)]


async def main() -> None:
    async with stdio_server(server):
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
