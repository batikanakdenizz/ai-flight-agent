"""
The HTTP surface: session handling and error translation.

The MCP subprocess and the local model are both stubbed out here -- these tests
are about what FastAPI does with the result, not about the agent loop.
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client(monkeypatch):
    """A client whose lifespan does not spawn the MCP server subprocess."""

    async def _noop():
        return None

    monkeypatch.setattr(main, "init_mcp", _noop)
    monkeypatch.setattr(main, "shutdown_mcp", _noop)
    main.sessions.clear()

    with TestClient(main.app) as test_client:
        yield test_client

    main.sessions.clear()


@pytest.fixture
def stub_agent(monkeypatch):
    """Replaces the agent loop with something that records what it was given."""
    seen = []

    async def _process(history, message):
        seen.append((list(history), message))
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "done"})
        return "done", [{"tool": "query_flights", "input": {"airport_from": "IST"}}]

    monkeypatch.setattr(main, "process_message", _process)
    return seen


def test_root_reports_the_discovered_tools(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "get_tool_definitions",
        lambda: [{"type": "function", "function": {"name": "query_flights"}}],
    )

    body = client.get("/").json()

    assert body["status"] == "AI Flight Agent is running"
    assert body["mcp_tools"] == ["query_flights"]


def test_chat_issues_a_session_id_when_none_is_supplied(client, stub_agent):
    body = client.post("/chat", json={"message": "flights to Izmir"}).json()

    assert body["session_id"]
    assert body["response"] == "done"
    assert body["tool_calls"][0]["tool"] == "query_flights"


def test_chat_keeps_history_within_one_session(client, stub_agent):
    first = client.post("/chat", json={"message": "flights to Izmir"}).json()
    session_id = first["session_id"]

    client.post("/chat", json={"message": "book the first one", "session_id": session_id})

    # The agent saw an empty history on turn one and the previous exchange on turn two.
    assert stub_agent[0][0] == []
    assert len(stub_agent[1][0]) == 2
    assert len(main.sessions[session_id]) == 4


def test_separate_sessions_do_not_share_history(client, stub_agent):
    one = client.post("/chat", json={"message": "hello"}).json()["session_id"]
    two = client.post("/chat", json={"message": "hello"}).json()["session_id"]

    assert one != two
    assert len(main.sessions) == 2


def test_agent_failure_becomes_a_500(client, monkeypatch):
    async def _boom(history, message):
        raise RuntimeError("ollama is not running")

    monkeypatch.setattr(main, "process_message", _boom)

    response = client.post("/chat", json={"message": "flights to Izmir"})

    assert response.status_code == 500
    assert "ollama is not running" in response.json()["detail"]


def test_chat_requires_a_message(client):
    assert client.post("/chat", json={}).status_code == 422


def test_clearing_a_session_drops_its_history(client, stub_agent):
    session_id = client.post("/chat", json={"message": "hello"}).json()["session_id"]
    assert session_id in main.sessions

    response = client.delete(f"/session/{session_id}")

    assert response.status_code == 200
    assert session_id not in main.sessions


def test_clearing_an_unknown_session_is_not_an_error(client):
    """The frontend clears on unload without knowing whether the session existed."""
    assert client.delete("/session/never-existed").status_code == 200
