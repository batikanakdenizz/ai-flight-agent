"""
The MCP client: schema translation and the guards around an unopened session.

MCP describes tools in its own shape; Ollama's function-calling API expects
another. The conversion happens once at startup, so a mistake there is invisible
until the model refuses to call anything.
"""
import mcp_client


class FakeTool:
    """Stands in for an mcp.types.Tool without pulling in the SDK's models."""

    def __init__(self, name, description=None, inputSchema=None):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema


def test_conversion_produces_the_ollama_function_shape():
    schema = {"type": "object", "properties": {"city": {"type": "string"}}}
    tool = FakeTool("check_in", "Check a passenger in.", schema)

    converted = mcp_client._convert_mcp_tool_to_ollama(tool)

    assert converted["type"] == "function"
    assert converted["function"]["name"] == "check_in"
    assert converted["function"]["description"] == "Check a passenger in."
    assert converted["function"]["parameters"] == schema


def test_conversion_strips_docstring_padding():
    """MCP descriptions come from docstrings, which carry leading newlines."""
    tool = FakeTool("buy_ticket", "\n  Book a seat.\n  ", {"type": "object"})

    converted = mcp_client._convert_mcp_tool_to_ollama(tool)

    assert converted["function"]["description"] == "Book a seat."


def test_conversion_tolerates_a_missing_description():
    tool = FakeTool("query_flights", None, {"type": "object"})

    converted = mcp_client._convert_mcp_tool_to_ollama(tool)

    assert converted["function"]["description"] == ""


def test_conversion_supplies_an_empty_schema_when_none_is_given():
    """
    Ollama rejects a tool with no parameters block, so a missing schema has to
    become an empty object rather than None.
    """
    tool = FakeTool("query_flights", "Search.", None)

    converted = mcp_client._convert_mcp_tool_to_ollama(tool)

    assert converted["function"]["parameters"] == {"type": "object", "properties": {}}


async def test_calling_a_tool_before_startup_returns_a_message(monkeypatch):
    """
    The agent feeds this string back to the model. Raising instead would turn a
    startup ordering problem into a 500 from /chat.
    """
    monkeypatch.setattr(mcp_client, "_session", None)

    result = await mcp_client.call_mcp_tool("query_flights", {})

    assert result == "MCP client is not initialized."


def test_tool_definitions_start_empty(monkeypatch):
    monkeypatch.setattr(mcp_client, "_tool_definitions", [])

    assert mcp_client.get_tool_definitions() == []


async def test_shutdown_is_safe_to_call_twice(monkeypatch):
    """FastAPI's lifespan runs shutdown once, but tests and reloads can double it."""
    monkeypatch.setattr(mcp_client, "_exit_stack", None)
    monkeypatch.setattr(mcp_client, "_session", None)

    await mcp_client.shutdown_mcp()
    await mcp_client.shutdown_mcp()

    assert mcp_client.get_tool_definitions() == []
