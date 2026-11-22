"""Basic Calculator MCP Server (stdio transport).

Works with Claude Desktop and any MCP client.
Important: never print() to stdout in a stdio server - it corrupts the
protocol. Use logging (stderr) or the Context object instead.
"""
import math
import logging

try:
    # MCP Python SDK v2.x (FastMCP was renamed to MCPServer)
    from mcp.server.mcpserver import MCPServer
except ImportError:
    # MCP Python SDK v1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

logging.basicConfig(level=logging.INFO)  # logs go to stderr

mcp = MCPServer("calculator")


@mcp.tool()
def add(a: int, b: int) -> str:
    """Add two numbers."""
    return f"""{a} + {b} = {a + b} 
    this is a calculator server add response for test"""


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Raise base to the given exponent."""
    return math.pow(base, exponent)


@mcp.tool()
def sqrt(x: float) -> float:
    """Square root of a non-negative number."""
    if x < 0:
        raise ValueError("Cannot take square root of a negative number")
    return math.sqrt(x)


@mcp.tool()
def modulo(a: float, b: float) -> float:
    """Remainder of a divided by b."""
    if b == 0:
        raise ValueError("Cannot take modulo by zero")
    return a % b


if __name__ == "__main__":
    mcp.run(transport="stdio")
