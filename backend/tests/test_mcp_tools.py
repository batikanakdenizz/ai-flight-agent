"""
The MCP tool contract.

These schemas are the only thing the model sees when it decides which tool to
call and what to pass. If a tool disappears from the listing, or an argument
stops being required, the model starts inventing values instead of asking the
user -- which is exactly the failure the system prompt tries to prevent.
"""
import pytest

import mcp_server as server

REQUIRED_ARGUMENTS = {
    "query_flights": {
        "airport_from",
        "airport_to",
        "departure_date_from",
        "departure_date_to",
    },
    "buy_ticket": {"flight_number", "departure_date", "passenger_names"},
    "check_in": {"flight_number", "departure_date", "passenger_name"},
}


async def _tools_by_name():
    return {tool.name: tool for tool in await server.mcp.list_tools()}


async def test_server_exposes_exactly_the_three_documented_tools():
    assert set(await _tools_by_name()) == set(REQUIRED_ARGUMENTS)


@pytest.mark.parametrize("tool_name", sorted(REQUIRED_ARGUMENTS))
async def test_required_arguments_match_the_contract(tool_name):
    tool = (await _tools_by_name())[tool_name]
    required = set(tool.inputSchema.get("required", []))
    assert required == REQUIRED_ARGUMENTS[tool_name]


@pytest.mark.parametrize("tool_name", sorted(REQUIRED_ARGUMENTS))
async def test_every_tool_carries_a_description(tool_name):
    """The description is the model's only cue for picking one tool over another."""
    tool = (await _tools_by_name())[tool_name]
    assert tool.description and tool.description.strip()


async def test_optional_search_arguments_stay_optional():
    """
    Paging and passenger count have defaults. Marking them required would force
    the model to guess them on every search.
    """
    tool = (await _tools_by_name())["query_flights"]
    required = set(tool.inputSchema.get("required", []))
    for optional in ("number_of_people", "is_round_trip", "page", "size"):
        assert optional in tool.inputSchema["properties"]
        assert optional not in required


async def test_buy_ticket_accepts_multiple_passengers():
    """One booking covers a party, so the passenger argument has to be a list."""
    tool = (await _tools_by_name())["buy_ticket"]
    assert tool.inputSchema["properties"]["passenger_names"]["type"] == "array"


async def test_check_in_takes_a_single_passenger():
    """Check-in is per person, unlike booking."""
    tool = (await _tools_by_name())["check_in"]
    assert tool.inputSchema["properties"]["passenger_name"]["type"] == "string"
