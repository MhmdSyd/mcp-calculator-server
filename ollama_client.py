"""MCP client that lets a local Ollama model (default: gemma4:12b) use the
calculator MCP server in this project.

How it works
------------
1. Launches calculator_server.py as a subprocess and connects over stdio (MCP).
2. Lists the server's tools and converts them to Ollama's tool format.
3. Sends your question to the Ollama model together with those tools.
4. When the model asks to call a tool, the call is forwarded to the MCP server
   and the result is given back to the model, repeating until it answers.

Works with MCP Python SDK v1.x and v2.x.

Usage
-----
    python ollama_client.py                     # interactive chat
    python ollama_client.py -p "What is 127 * 43?"   # single question
    python ollama_client.py --model gemma4:12b --server calculator_server.py
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlparse

from ollama import AsyncClient, ResponseError

from mcp import StdioServerParameters

try:  # MCP Python SDK v2.x
    from mcp import Client as MCPClient
except ImportError:  # MCP Python SDK v1.x
    MCPClient = None
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

DEFAULT_MODEL = "gemma4:12b"
DEFAULT_SERVER = Path(__file__).with_name("calculator_server.py")
MAX_TOOL_STEPS = 8

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to calculator tools. "
    "For ANY arithmetic, always call the matching tool instead of calculating "
    "yourself. For multi-step problems, call one tool at a time and use the "
    "previous result. After the tools return, give a short, clear final answer."
)


# --------------------------------------------------------------------------- #
# MCP connection (works on SDK v1 and v2)
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def connect(params: StdioServerParameters) -> AsyncIterator[Any]:
    """Yield an object that has list_tools() and call_tool(name, arguments)."""
    if MCPClient is not None:  # v2
        async with MCPClient(params) as client:
            yield client
    else:  # v1
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


def attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Read the first existing attribute (v2 uses snake_case, v1 camelCase)."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


# --------------------------------------------------------------------------- #
# MCP <-> Ollama conversion
# --------------------------------------------------------------------------- #
def to_ollama_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to Ollama's function-tool format."""
    tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        schema = attr(tool, "input_schema", "inputSchema", default=None) or {}
        properties: dict[str, Any] = {}
        for name, prop in (schema.get("properties") or {}).items():
            clean = {k: prop[k] for k in ("type", "description", "enum") if k in prop}
            clean.setdefault("type", "string")
            properties[name] = clean
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": list(schema.get("required") or []),
                    },
                },
            }
        )
    return tools


def result_to_text(result: Any) -> str:
    """Flatten an MCP CallToolResult into plain text for the model."""
    parts = [b.text for b in (attr(result, "content", default=[]) or []) if hasattr(b, "text")]
    text = "\n".join(parts).strip() or "(no output)"
    if attr(result, "is_error", "isError", default=False):
        text = f"Tool error: {text}"
    return text


# --------------------------------------------------------------------------- #
# Chat loop
# --------------------------------------------------------------------------- #
async def answer(
    llm: AsyncClient,
    model: str,
    session: Any,
    tools: list[dict[str, Any]],
    messages: list[Any],
) -> str:
    """Run the model, executing any tool calls it makes, until it answers."""
    for _ in range(MAX_TOOL_STEPS):
        response = await llm.chat(model=model, messages=messages, tools=tools)
        message = response.message
        messages.append(message)

        if not message.tool_calls:
            return (message.content or "").strip()

        for call in message.tool_calls:
            name = call.function.name
            arguments = dict(call.function.arguments or {})
            print(f"  [tool] {name}({', '.join(f'{k}={v}' for k, v in arguments.items())})")
            try:
                result = await session.call_tool(name, arguments)
                text = result_to_text(result)
            except Exception as exc:  # report the failure back to the model
                text = f"Tool call failed: {exc}"
            print(f"  [result] {text}")
            messages.append({"role": "tool", "tool_name": name, "content": text})

    return "(Stopped: the model made too many tool calls in a row.)"


def resolve_host(host: str | None) -> str:
    """Return a connectable Ollama URL.

    OLLAMA_HOST is often set to 0.0.0.0 so the server listens on all
    interfaces. That is a bind address: clients (especially on Windows) cannot
    connect to it, so it is rewritten to 127.0.0.1.
    """
    raw = (host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").strip()
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    hostname = parsed.hostname or "127.0.0.1"
    if hostname in {"0.0.0.0", "::", ""}:
        hostname = "127.0.0.1"
    scheme = parsed.scheme or "http"
    port = parsed.port or (443 if scheme == "https" else 11434)
    return f"{scheme}://{hostname}:{port}"


async def check_model(llm: AsyncClient, model: str) -> None:
    try:
        await llm.show(model)
    except ConnectionError as exc:
        sys.exit(
            f"Cannot reach Ollama at {getattr(getattr(llm, '_client', None), 'base_url', 'the configured host')}.\n"
            f"Details: {exc}\n"
            "Make sure Ollama is running, or pass --host http://127.0.0.1:11434"
        )
    except ResponseError as exc:
        if exc.status_code == 404:
            sys.exit(f"Model '{model}' is not installed. Run:  ollama pull {model}")
        sys.exit(f"Ollama error: {exc}")


async def main_async(args: argparse.Namespace) -> None:
    server_path = Path(args.server).resolve()
    if not server_path.exists():
        sys.exit(f"Server script not found: {server_path}")

    llm = AsyncClient(host=resolve_host(args.host))
    await check_model(llm, args.model)

    # Launch the MCP server with the same Python interpreter running this client.
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])

    async with connect(params) as session:
        listed = await session.list_tools()
        tools = to_ollama_tools(listed.tools)
        print(f"Connected to MCP server. Tools: {', '.join(t['function']['name'] for t in tools)}")
        print(f"Model: {args.model}\n")

        system = {"role": "system", "content": SYSTEM_PROMPT}
        messages: list[Any] = [system]

        if args.prompt:  # single question
            messages.append({"role": "user", "content": args.prompt})
            print(await answer(llm, args.model, session, tools, messages))
            return

        print("Type a question. Commands: /tools, /reset, exit")
        while True:
            try:
                user = (await asyncio.to_thread(input, "\nYou> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user.lower() in {"exit", "quit", "/exit", "/quit"}:
                break
            if user == "/reset":
                messages = [system]
                print("Conversation cleared.")
                continue
            if user == "/tools":
                for t in tools:
                    print(f"- {t['function']['name']}: {t['function']['description']}")
                continue

            messages.append({"role": "user", "content": user})
            try:
                reply = await answer(llm, args.model, session, tools, messages)
            except ResponseError as exc:
                reply = f"Ollama error: {exc}"
            print(f"\nAssistant> {reply}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama + MCP calculator client")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("-s", "--server", default=str(DEFAULT_SERVER), help="Path to the MCP server script")
    parser.add_argument("-p", "--prompt", help="Ask one question and exit")
    parser.add_argument("--host", default=None, help="Ollama URL (default: OLLAMA_HOST or http://127.0.0.1:11434)")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
