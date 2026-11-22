# MCP Calculator Server

A simple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server written in Python that exposes basic calculator operations as tools. It works with **Claude Desktop** and any other MCP-compatible client (Claude Code, Cursor, VS Code, MCP Inspector, etc.).

It is intentionally small, which makes it a good starting point for learning how MCP servers are built.

## Features

The server exposes the following tools:

| Tool       | Arguments                    | Description                         |
|------------|------------------------------|-------------------------------------|
| `add`      | `a: float, b: float`         | Returns `a + b`                     |
| `subtract` | `a: float, b: float`         | Returns `a - b`                     |
| `multiply` | `a: float, b: float`         | Returns `a * b`                     |
| `divide`   | `a: float, b: float`         | Returns `a / b` (errors if `b = 0`) |
| `power`    | `base: float, exponent: float` | Returns `base ** exponent`        |
| `sqrt`     | `x: float`                   | Square root (errors if `x < 0`)     |
| `modulo`   | `a: float, b: float`         | Returns `a % b` (errors if `b = 0`) |

## Requirements

- Python 3.10 or newer
- The official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (both v1.x and v2.x are supported)

## Installation

### Option A: using [uv](https://docs.astral.sh/uv/) (recommended)

```bash
git clone https://github.com/<your-username>/mcp-calculator-server.git
cd mcp-calculator-server

uv sync        # creates .venv and installs dependencies from pyproject.toml
```

If you are starting from scratch instead of cloning, the equivalent is:

```bash
uv init mcp-calculator-server
cd mcp-calculator-server
uv add "mcp[cli]"
```

### Option B: using pip

```bash
git clone https://github.com/<your-username>/mcp-calculator-server.git
cd mcp-calculator-server

# (recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Running and testing

The server uses the **stdio** transport, so normally an MCP client launches it for you. To test it interactively with the MCP Inspector:

```bash
uv run mcp dev calculator_server.py      # with uv
mcp dev calculator_server.py             # with pip / activated venv
```

This opens a web UI where you can list the tools and call them with different inputs.

You can also run the server directly (it will wait for MCP messages on stdin):

```bash
uv run calculator_server.py              # with uv
python calculator_server.py              # with pip / activated venv
```

## Connecting to Claude Desktop

1. Open Claude Desktop and go to **Settings → Developer → Edit Config**. This opens `claude_desktop_config.json`:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Add the server (see [`claude_desktop_config.example.json`](claude_desktop_config.example.json)).

   **With uv (recommended):**

   ```json
   {
     "mcpServers": {
       "calculator": {
         "command": "uv",
         "args": [
           "--directory",
           "/absolute/path/to/mcp-calculator-server",
           "run",
           "calculator_server.py"
         ]
       }
     }
   }
   ```

   - `--directory` must point to the project folder (the one containing `pyproject.toml`). On Windows, use forward slashes or double the backslashes (`D:\\projects\\mcp-calculator-server`).
   - If Claude Desktop cannot find `uv`, use its full path as `command`. Find it with `where uv` (Windows) or `which uv` (macOS/Linux), e.g. `C:\\Users\\<you>\\.local\\bin\\uv.exe`.

   **With plain Python instead:**

   ```json
   {
     "mcpServers": {
       "calculator": {
         "command": "/path/to/venv/bin/python",
         "args": ["/absolute/path/to/mcp-calculator-server/calculator_server.py"]
       }
     }
   }
   ```

3. **Fully quit and restart** Claude Desktop.
4. Click the tools icon in the chat box. You should see `calculator` listed.
5. Try a prompt such as: *"Use the calculator to multiply 127 by 43, then take the square root of the result."*

## Using with VS Code (GitHub Copilot)

This repo includes `.vscode/mcp.json`, so VS Code picks the server up automatically when you open the project folder:

```json
{
  "servers": {
    "calculator": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${workspaceFolder}", "run", "calculator_server.py"]
    }
  }
}
```

1. Open the project folder in VS Code (`uv sync` first so dependencies are installed).
2. Open `.vscode/mcp.json` and click **Start** above the `calculator` entry (or run **MCP: List Servers** from the Command Palette).
3. Open Copilot Chat and switch the mode to **Agent**.
4. Click the tools icon and make sure the `calculator` tools are ticked.
5. Ask: *"Use the calculator tools to multiply 127 by 43, then take the square root."* and click **Allow** when asked.

Note that VS Code uses a top-level `servers` key, while Claude Desktop uses `mcpServers`.

## Using with other MCP clients

Because this is a standard stdio server, any client that can launch a local command can use it.

**Claude Code:**

```bash
claude mcp add calculator -- uv --directory /absolute/path/to/mcp-calculator-server run calculator_server.py
```

**Other clients (Cursor, VS Code, etc.):** add a server entry with `python` as the command and the path to `calculator_server.py` as the argument. Check your client's docs for the exact config file.

### Optional: HTTP transport

To serve over HTTP instead of stdio, change the last line of `calculator_server.py` to:

```python
mcp.run(transport="streamable-http")
```

## Ollama client (local LLM + MCP)

`ollama_client.py` is an MCP **client** that connects to this calculator server and lets a local [Ollama](https://ollama.com) model use its tools. The default model is `gemma4:12b`.

```
You ──▶ ollama_client.py ──▶ Ollama (gemma4:12b)
              │                     │  "call multiply(127, 43)"
              ▼                     │
        MCP stdio  ◀────────────────┘
              ▼
     calculator_server.py  ──▶ result ──▶ back to the model ──▶ final answer
```

### Prerequisites

1. Install [Ollama](https://ollama.com/download) and make sure it is running.
2. Pull the model (tool calling needs a recent Ollama version, so update Ollama if tool calls fail):
   ```bash
   ollama pull gemma4:12b
   ```
3. Install the project dependencies (includes the `ollama` Python package):
   ```bash
   uv sync          # or: pip install -r requirements.txt
   ```

### Run it

```bash
uv run ollama_client.py                        # interactive chat
uv run ollama_client.py -p "What is 127 * 43, then its square root?"
uv run ollama_client.py --model gemma4:12b     # choose another Ollama model
```

(With pip, use `python ollama_client.py ...` instead of `uv run ollama_client.py ...`.)

Example session:

```
You> What is 127 times 43?
  [tool] multiply(a=127, b=43)
  [result] 5461.0
Assistant> 127 times 43 is 5,461.
```

Chat commands: `/tools` lists the MCP tools, `/reset` clears the conversation, `exit` quits.

### Options

| Option | Description |
|--------|-------------|
| `-m`, `--model` | Ollama model name (default `gemma4:12b`) |
| `-s`, `--server` | Path to the MCP server script (default `calculator_server.py`) |
| `-p`, `--prompt` | Ask one question and exit |
| `--host` | Ollama URL if not `http://localhost:11434` |

### How it works

1. Starts `calculator_server.py` as a subprocess and connects over stdio.
2. Reads the server's tools and converts their JSON schemas to Ollama's tool format.
3. Sends your message plus the tools to the model.
4. Runs any tool calls the model requests through the MCP server and returns the results to the model, until it gives a final answer.

Small local models are less reliable at tool calling than large hosted ones. If the model answers without calling a tool, rephrase with "use the calculator tool".

## Troubleshooting

- **Server doesn't show up in Claude Desktop:** check `claude_desktop_config.json` for JSON syntax errors, then fully restart the app. Logs are in `%APPDATA%\Claude\logs\` (Windows) or `~/Library/Logs/Claude/` (macOS); look for `mcp-server-calculator.log`.
- **`No module named 'mcp'`:** the Python used by Claude Desktop is not the one where you installed the package. Use the uv config above, or point `command` at the exact interpreter you used with `pip install`.
- **`spawn uv ENOENT` or `uv` not found:** Claude Desktop can't see `uv` on its PATH. Use the full path to `uv` as `command`.
- **Connection errors or garbled output:** never use `print()` in a stdio server, since stdout carries the protocol. Use `logging` (stderr) instead.

## Notes on MCP SDK versions

In MCP Python SDK **v2**, `FastMCP` was renamed to `MCPServer` (`mcp.server.mcpserver`). This project imports `MCPServer` and automatically falls back to `mcp.server.fastmcp.FastMCP` on v1, so it runs on either version. The error `No module named 'mcp.server.fastmcp'` means you are on v2 and are running an older copy of this code; update `calculator_server.py` or pin `mcp<2`. See the [v1 to v2 migration guide](https://py.sdk.modelcontextprotocol.io/v2/migration/).

## Project structure

```
mcp-calculator-server/
├── calculator_server.py                # The MCP server
├── pyproject.toml                      # Project metadata and dependencies (uv)
├── requirements.txt                    # Dependencies for pip users
├── ollama_client.py                    # MCP client using a local Ollama model
├── claude_desktop_config.example.json  # Example Claude Desktop config
├── .vscode/mcp.json                    # VS Code / GitHub Copilot MCP config
├── .gitignore
├── LICENSE
└── README.md
```

## Extending the server

Adding a new tool takes a few lines. Decorate a typed function with a docstring:

```python
@mcp.tool()
def absolute(x: float) -> float:
    """Return the absolute value of x."""
    return abs(x)
```

The type hints and docstring are used to generate the tool's schema and description, which is what the AI model sees when deciding how to call it.

## Contributing

Issues and pull requests are welcome. Feel free to open an issue for bugs or feature ideas.

## License

Released under the [MIT License](LICENSE).
