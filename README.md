# SignalZeroMCP
SignalZero shared symbolic store, MCP server

## MCP Server

A Python MCP server is provided in `symbol_store_server.py` that wraps the AWS SignalZero symbol store API defined in `aws/global_symbols_openapi.yaml`.

### Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Optionally set environment variables:
   - `SYMBOL_STORE_BASE_URL` (defaults to the production API Gateway URL)
   - `SYMBOL_STORE_API_KEY` (if your deployment requires an API key)
3. Start the server over stdio:
   ```bash
   python symbol_store_server.py
   ```

### Available tools

The server exposes tools that correspond to the OpenAPI operations:
- `query_symbols`: Filter symbols by domain or tag.
- `get_symbol_by_id`: Retrieve a symbol document by ID.
- `put_symbol_by_id`: Store or update a symbol document.
- `list_domains`: Enumerate available symbol domains.
