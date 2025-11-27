import json
from typing import Any, Dict, List

import httpx
import pytest

import symbol_store_server as server_module


class StubClient:
    def __init__(self, responses: Dict[str, Any]) -> None:
        self.responses = responses

    async def query_symbols(
        self,
        *,
        symbol_domain: str | None = None,
        symbol_tag: str | None = None,
        last_symbol_id: str | None = None,
        limit: int | None = None,
    ) -> Any:
        return self.responses["query_symbols"]

    async def get_symbol(self, symbol_id: str) -> Any:
        return self.responses[("get_symbol", symbol_id)]

    async def put_symbol(self, symbol_id: str, payload: Dict[str, Any]) -> Any:
        return self.responses[("put_symbol", symbol_id)]

    async def list_domains(self) -> Any:
        return self.responses["list_domains"]


@pytest.mark.asyncio
async def test_call_tool_query_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {"query_symbols": [{"id": "1", "domain": "test"}]}
    monkeypatch.setattr(server_module, "build_client", lambda: StubClient(responses))

    result = await server_module.call_tool(
        "query_symbols", {"symbol_domain": "test", "limit": 10}
    )

    assert len(result) == 1
    payload = json.loads(result[0].text.split("\n", 1)[1])
    assert payload == responses["query_symbols"]


@pytest.mark.asyncio
async def test_call_tool_list_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {"list_domains": ["alpha", "beta"]}
    monkeypatch.setattr(server_module, "build_client", lambda: StubClient(responses))

    result = await server_module.call_tool("list_domains", {})

    assert len(result) == 1
    assert "alpha" in result[0].text
    assert "beta" in result[0].text


@pytest.mark.asyncio
async def test_call_tool_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_client() -> StubClient:
        class FailingStub(StubClient):
            async def list_domains(self) -> Any:  # type: ignore[override]
                request = httpx.Request("GET", "http://example.com/domains")
                response = httpx.Response(404, request=request, text="not found")
                raise httpx.HTTPStatusError("error", request=request, response=response)

        return FailingStub({"list_domains": []})

    monkeypatch.setattr(server_module, "build_client", failing_client)

    result = await server_module.call_tool("list_domains", {})

    assert "failed with status 404" in result[0].text


def test_build_tools_from_spec_contains_expected_names() -> None:
    tools = server_module.build_tools_from_spec(server_module.load_spec())
    tool_names: List[str] = [tool.name for tool in tools]

    for expected in {"query_symbols", "get_symbol_by_id", "put_symbol_by_id", "list_domains"}:
        assert expected in tool_names
