"""
What the tools actually send to the gateway, and how they behave when it says no.

Every tool returns a string rather than raising, because the return value goes
straight back to the model as tool output. An exception here would surface as a
500 from /chat instead of something the assistant can explain to the user.
"""
import httpx
import pytest
import respx

import mcp_server as server

GATEWAY = server.GATEWAY_BASE_URL


@respx.mock
async def test_query_flights_widens_a_single_date_into_a_full_day():
    route = respx.get(f"{GATEWAY}/gateway/flights/query").mock(
        return_value=httpx.Response(200, text='{"flights":[]}')
    )

    await server.query_flights("Istanbul", "Izmir", "2026-09-01", "2026-09-01")

    params = dict(route.calls[0].request.url.params)
    assert params["departureDateFrom"] == "2026-09-01T00:00:00Z"
    assert params["departureDateTo"] == "2026-09-01T23:59:59Z"


@respx.mock
async def test_query_flights_trims_airport_values():
    route = respx.get(f"{GATEWAY}/gateway/flights/query").mock(
        return_value=httpx.Response(200, text="{}")
    )

    await server.query_flights("  IST  ", "  ADB  ", "2026-09-01", "2026-09-01")

    params = dict(route.calls[0].request.url.params)
    assert params["airportFrom"] == "IST"
    assert params["airportTo"] == "ADB"


@respx.mock
async def test_query_flights_identifies_itself_to_the_gateway():
    """The gateway rate-limits per client, so the header has to be present."""
    route = respx.get(f"{GATEWAY}/gateway/flights/query").mock(
        return_value=httpx.Response(200, text="{}")
    )

    await server.query_flights("IST", "ADB", "2026-09-01", "2026-09-01")

    assert route.calls[0].request.headers["Client"] == "ai-agent"


@respx.mock
async def test_query_flights_returns_the_body_unchanged_on_success():
    body = '{"flights":[{"flightNumber":"TK123"}]}'
    respx.get(f"{GATEWAY}/gateway/flights/query").mock(
        return_value=httpx.Response(200, text=body)
    )

    assert await server.query_flights("IST", "ADB", "2026-09-01", "2026-09-01") == body


@respx.mock
@pytest.mark.parametrize("status", [400, 429, 500])
async def test_query_flights_reports_failures_as_text(status):
    respx.get(f"{GATEWAY}/gateway/flights/query").mock(
        return_value=httpx.Response(status, text="upstream said no")
    )

    result = await server.query_flights("IST", "ADB", "2026-09-01", "2026-09-01")

    assert str(status) in result
    assert "upstream said no" in result


@respx.mock
async def test_buy_ticket_authenticates_before_booking():
    respx.post(f"{GATEWAY}/gateway/auth/login").mock(
        return_value=httpx.Response(200, json={"token": "jwt-abc"})
    )
    tickets = respx.post(f"{GATEWAY}/gateway/tickets").mock(
        return_value=httpx.Response(200, text='{"pnr":"XYZ789"}')
    )

    result = await server.buy_ticket("TK123", "2026-09-01T14:30:00", ["Ada Lovelace"])

    assert result == '{"pnr":"XYZ789"}'
    assert tickets.calls[0].request.headers["Authorization"] == "Bearer jwt-abc"


@respx.mock
async def test_buy_ticket_normalizes_the_departure_datetime():
    respx.post(f"{GATEWAY}/gateway/auth/login").mock(
        return_value=httpx.Response(200, json={"token": "jwt-abc"})
    )
    tickets = respx.post(f"{GATEWAY}/gateway/tickets").mock(
        return_value=httpx.Response(200, text="{}")
    )

    await server.buy_ticket("TK123", "2026-09-01T14:30:00", ["Ada Lovelace"])

    import json

    body = json.loads(tickets.calls[0].request.content)
    assert body["departureDate"] == "2026-09-01T14:30:00Z"
    assert body["passengerNames"] == ["Ada Lovelace"]


@respx.mock
async def test_buy_ticket_does_not_book_when_login_fails():
    """
    Without a token the booking call would be rejected anyway. Skipping it keeps
    a failed login from looking like a failed booking in the logs.
    """
    respx.post(f"{GATEWAY}/gateway/auth/login").mock(
        return_value=httpx.Response(401, text="bad credentials")
    )
    tickets = respx.post(f"{GATEWAY}/gateway/tickets").mock(
        return_value=httpx.Response(200, text="{}")
    )

    result = await server.buy_ticket("TK123", "2026-09-01T14:30:00", ["Ada Lovelace"])

    assert "Authentication failed" in result
    assert not tickets.called


@respx.mock
async def test_buy_ticket_survives_an_unreachable_auth_endpoint():
    """A network error during login must not escape as an exception."""
    respx.post(f"{GATEWAY}/gateway/auth/login").mock(
        side_effect=httpx.ConnectError("gateway is down")
    )

    result = await server.buy_ticket("TK123", "2026-09-01T14:30:00", ["Ada Lovelace"])

    assert "Authentication failed" in result


@respx.mock
async def test_check_in_normalizes_a_date_only_departure():
    checkin = respx.post(f"{GATEWAY}/gateway/checkin").mock(
        return_value=httpx.Response(200, text='{"seat":"12A"}')
    )

    result = await server.check_in("TK123", "2026-09-01", "Ada Lovelace")

    import json

    body = json.loads(checkin.calls[0].request.content)
    assert body["departureDate"] == "2026-09-01T00:00:00Z"
    assert body["passengerName"] == "Ada Lovelace"
    assert result == '{"seat":"12A"}'


@respx.mock
async def test_check_in_reports_failures_as_text():
    respx.post(f"{GATEWAY}/gateway/checkin").mock(
        return_value=httpx.Response(404, text="no such booking")
    )

    result = await server.check_in("TK123", "2026-09-01", "Ada Lovelace")

    assert "404" in result
    assert "no such booking" in result
