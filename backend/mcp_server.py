"""
Standalone MCP server for the SE4458 Airline Ticketing APIs.

Exposes three tools over MCP (stdio transport):
  - query_flights
  - buy_ticket
  - check_in

Every tool routes its HTTP call through the Ocelot gateway. The agent backend
spawns this file as a subprocess and talks to it via the Model Context Protocol.

Run standalone (for debugging):
    python mcp_server.py
"""
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

GATEWAY_BASE_URL = os.getenv(
    "GATEWAY_BASE_URL",
    "https://gateway-midterm-begsgfcubdhxaph0.francecentral-01.azurewebsites.net",
)

mcp = FastMCP("airline-tickets")


# ---------- Date normalization helpers ----------
def _to_utc_start(date_str: str) -> str:
    """Start of day in UTC — for departureDateFrom."""
    date_part = date_str.strip().split("T")[0]
    return f"{date_part}T00:00:00Z"


def _to_utc_end(date_str: str) -> str:
    """End of day in UTC — for departureDateTo."""
    date_part = date_str.strip().split("T")[0]
    return f"{date_part}T23:59:59Z"


def _to_utc_datetime(date_str: str) -> str:
    """Ensure date string has UTC time component (for ticket/checkin departure dates)."""
    date_str = date_str.strip()
    if "T" not in date_str:
        return f"{date_str}T00:00:00Z"
    # A trailing offset already carries the timezone; appending Z would produce
    # something like '...-05:00Z', which the gateway cannot parse. Both signs
    # have to be checked -- only the last six characters can hold an offset, so
    # the hyphens inside the date part are never seen here.
    offset = date_str[-6:]
    if not date_str.endswith("Z") and "+" not in offset and "-" not in offset:
        return f"{date_str}Z"
    return date_str


# ---------- Auth ----------
async def _get_auth_token() -> Optional[str]:
    username = os.getenv("AIRLINE_USERNAME", "admin")
    password = os.getenv("AIRLINE_PASSWORD", "admin123")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GATEWAY_BASE_URL}/gateway/auth/login",
                json={"username": username, "password": password},
            )
            if resp.status_code == 200:
                return resp.json().get("token")
    except Exception:
        return None
    return None


# ---------- MCP tools ----------
@mcp.tool()
async def query_flights(
    airport_from: str,
    airport_to: str,
    departure_date_from: str,
    departure_date_to: str,
    number_of_people: int = 1,
    is_round_trip: bool = False,
    page: int = 1,
    size: int = 10,
) -> str:
    """
    Search for available flights between two airports.

    The user may provide city names (e.g. Istanbul, Frankfurt) or airport
    codes (e.g. IST, FRA). Dates must be in ISO format (YYYY-MM-DD); use the
    same value for departure_date_from and departure_date_to for a single-day
    search.

    Returns the raw JSON response from the gateway as a string.
    """
    params = {
        "airportFrom": airport_from.strip(),
        "airportTo": airport_to.strip(),
        "departureDateFrom": _to_utc_start(departure_date_from),
        "departureDateTo": _to_utc_end(departure_date_to),
        "numberOfPeople": number_of_people,
        "isRoundTrip": is_round_trip,
        "page": page,
        "size": size,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{GATEWAY_BASE_URL}/gateway/flights/query",
            params=params,
            headers={"Client": "ai-agent"},
        )
        if resp.status_code == 200:
            return resp.text
        return f"Flight query failed with status {resp.status_code}: {resp.text}"


@mcp.tool()
async def buy_ticket(
    flight_number: str,
    departure_date: str,
    passenger_names: list[str],
) -> str:
    """
    Book/purchase a flight ticket for one or more passengers.

    Requires flight number, departure datetime (YYYY-MM-DDTHH:MM:SS), and the
    full names of every passenger. Authenticates automatically with constant
    credentials before hitting the gateway.
    """
    token = await _get_auth_token()
    if not token:
        return "Authentication failed. Could not obtain access token."

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GATEWAY_BASE_URL}/gateway/tickets",
            json={
                "flightNumber": flight_number,
                "departureDate": _to_utc_datetime(departure_date),
                "passengerNames": passenger_names,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return resp.text
        return f"Ticket booking failed with status {resp.status_code}: {resp.text}"


@mcp.tool()
async def check_in(
    flight_number: str,
    departure_date: str,
    passenger_name: str,
) -> str:
    """
    Check in a passenger for an existing booking.

    Requires the flight number, the scheduled departure datetime
    (YYYY-MM-DDTHH:MM:SS), and the passenger's full name.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GATEWAY_BASE_URL}/gateway/checkin",
            json={
                "flightNumber": flight_number,
                "departureDate": _to_utc_datetime(departure_date),
                "passengerName": passenger_name,
            },
        )
        if resp.status_code == 200:
            return resp.text
        return f"Check-in failed with status {resp.status_code}: {resp.text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
