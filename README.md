# AI Flight Agent

> A conversational AI agent that lets users search flights, book tickets, and check in — all through natural language chat, powered by a local LLM (Ollama) and the SE4458 Airline Ticketing API.

---

## Video

Youtube Video: https://youtu.be/eq-2jGJ4ftE

---

## Live Demo

| Layer | URL |
|-------|-----|
| Frontend | http://localhost:3000 |
| Agent Backend | http://localhost:8000 |
| API Docs (Backend) | http://localhost:8000/docs |
| Midterm Gateway | https://gateway-midterm-begsgfcubdhxaph0.francecentral-01.azurewebsites.net |
| Midterm API | https://api-midterm-bgareudhf2aaakar.francecentral-01.azurewebsites.net |

---

## Architecture

```
┌─────────────────┐   HTTP/JSON    ┌──────────────────────────┐
│                 │ ─────────────► │   Agent Backend          │
│  React Frontend │                │   (Python FastAPI)        │
│  (Vite + Chat)  │ ◄───────────── │                          │
│                 │  response text │  ┌────────────────────┐  │
└─────────────────┘                │  │  Ollama LLM        │  │
                                   │  │  (qwen2.5:7b /     │  │
                                   │  │   llama3.1 / etc.) │  │
                                   │  └────────┬───────────┘  │
                                   │           │ tool_calls    │
                                   │  ┌────────▼───────────┐  │
                                   │  │   MCP Client       │  │
                                   │  │  (mcp_client.py)   │  │
                                   │  └────────┬───────────┘  │
                                   └───────────┼──────────────┘
                                               │ MCP over stdio
                                               │ (spawned subprocess)
                                   ┌───────────▼──────────────┐
                                   │   MCP Server             │
                                   │  (mcp_server.py)         │
                                   │                          │
                                   │  • query_flights         │
                                   │  • buy_ticket            │
                                   │  • check_in              │
                                   └───────────┬──────────────┘
                                               │ HTTPS
                                   ┌───────────▼──────────────┐
                                   │   Ocelot API Gateway     │
                                   │   (Azure – francecentral) │
                                   │                          │
                                   │  Rate limiting (3/min)   │
                                   │  JWT forwarding          │
                                   └───────────┬──────────────┘
                                               │
                                   ┌───────────▼──────────────┐
                                   │   Midterm REST API       │
                                   │   (.NET 8 / PostgreSQL)  │
                                   │                          │
                                   │  /api/v1/Auth/login      │
                                   │  /api/v1/Flight/query    │
                                   │  /api/v1/Ticket          │
                                   │  /api/v1/CheckIn         │
                                   └──────────────────────────┘
```

### Component Stack

| Component | Technology | Role |
|-----------|-----------|------|
| **Frontend** | React 18 + Vite | Chat UI with markdown rendering |
| **Agent Backend** | Python FastAPI | Orchestrates LLM ↔ MCP client ↔ frontend |
| **LLM** | Ollama (`qwen2.5:7b`) | Intent parsing & tool selection |
| **MCP Client** | `mcp` Python SDK | Spawns & talks to the MCP server over stdio |
| **MCP Server** | `FastMCP` (Python, standalone process) | Exposes flight tools, calls the gateway |
| **Gateway** | Ocelot (.NET) | Rate limiting, routing, JWT passthrough |
| **Midterm API** | ASP.NET Core 8 | Business logic + PostgreSQL (Supabase) |

---

## Features

- **Natural language flight search** — "Find me a flight from Istanbul to Izmir on April 22"
- **Conversational booking** — "Book flight TK2314 for John Doe"
- **Check-in** — "Check in John Doe for flight TK2314"
- **Multi-turn conversation** — Agent remembers context within a session
- **Tool call badges** — UI shows which API was invoked per message
- **Local LLM** — No external API keys required; runs entirely on-device with Ollama
- **Switchable models** — Change `OLLAMA_MODEL` env var to use `llama3.1`, `qwen2.5:3b`, or `mistral`

---

## Supported Ollama Models

| Model | Size | Tool Use |
|-------|------|----------|
| `qwen2.5:7b` | 4.7 GB | Excellent (default) |
| `llama3.1:latest` | 4.9 GB | Very good |
| `qwen2.5:3b` | 1.9 GB | Good (faster) |
| `mistral:latest` | 4.4 GB | Limited |

---

## Project Structure

```
AiAgentFlight/
├── backend/
│   ├── main.py          # FastAPI app — /chat endpoint, MCP lifespan, sessions
│   ├── agent.py         # LLM orchestration loop (Ollama native API via httpx)
│   ├── mcp_client.py    # Persistent MCP client (spawns mcp_server.py over stdio)
│   ├── mcp_server.py    # Standalone MCP server — exposes the 3 airline tools
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    └── src/
        ├── App.jsx              # Session management, message state
        ├── components/
        │   ├── ChatWindow.jsx   # Message list, input bar, typing indicator
        │   ├── ChatWindow.css
        │   ├── Sidebar.jsx      # Quick action buttons
        │   └── Sidebar.css
        ├── index.css
        └── main.jsx
```

---

## Setup & Running

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.11+
- Node.js 18+

```bash
# Pull a model (if not already done)
ollama pull qwen2.5:7b
```

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env — set AIRLINE_USERNAME, AIRLINE_PASSWORD

# Start server (automatically spawns the MCP server subprocess via stdio)
uvicorn main:app --port 8000
```

> The FastAPI app launches `mcp_server.py` as a child process at startup and
> connects to it over stdio — you do **not** need to start the MCP server in
> a separate terminal. To exercise the MCP server on its own (for debugging
> with an MCP inspector or a different host), you can run
> `python mcp_server.py` directly.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Environment Variables

Create `backend/.env` from `backend/.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `AIRLINE_USERNAME` | `admin` | Constant login for midterm API |
| `AIRLINE_PASSWORD` | `admin123` | Constant password for midterm API |
| `GATEWAY_BASE_URL` | *(Azure gateway URL)* | Ocelot gateway base URL |

---

## API Reference

### `POST /chat`

Send a message and receive an AI response with optional tool calls.

**Request**
```json
{
  "message": "Find a flight from Istanbul to Izmir on April 22",
  "session_id": "optional-uuid"
}
```

**Response**
```json
{
  "response": "I found 2 flights from IST to ADB on April 22, 2026:\n\n- **TK2314** 08:30 → 09:45 (75 min) — 180 seats available\n...",
  "session_id": "abc-123",
  "tool_calls": [
    {
      "tool": "query_flights",
      "input": { "airport_from": "IST", "airport_to": "ADB", ... }
    }
  ]
}
```

### `DELETE /session/{session_id}`

Clear conversation history for a session.

---

## MCP Server & Tools

The backend follows the architecture prescribed by the assignment: the LLM-facing
tools live in a **separate MCP server process** (`backend/mcp_server.py`), not
inline with the FastAPI app. At startup, the agent backend spawns the MCP
server as a child process over **stdio** using the official `mcp` Python SDK,
calls `list_tools()` to discover what's available, and converts the returned
schemas into Ollama's function-calling format. Every tool invocation from the
LLM is forwarded to the MCP server via `call_tool()`, and only the MCP server
talks to the Ocelot gateway.

This means:
- The MCP server is reusable — any MCP-compatible client (Claude Desktop,
  Cursor, etc.) could connect to `mcp_server.py` directly and get the same
  three tools.
- Tool schemas are the single source of truth on the server side; the agent
  backend does not hardcode them.
- The server process is spawned once at FastAPI startup (lifespan) and kept
  alive for the life of the app, so there's no per-request subprocess cost.

The MCP server exposes three tools:

### `query_flights`
Calls `GET /gateway/flights/query` with `Client: ai-agent` header (rate limit: 3 req/min).

| Parameter | Type | Required |
|-----------|------|----------|
| `airport_from` | string | ✓ |
| `airport_to` | string | ✓ |
| `departure_date_from` | YYYY-MM-DD | ✓ |
| `departure_date_to` | YYYY-MM-DD | ✓ |
| `number_of_people` | int | — |
| `is_round_trip` | bool | — |

### `buy_ticket`
Calls `POST /gateway/tickets` with JWT Bearer token (auto-login with constant credentials).

| Parameter | Type | Required |
|-----------|------|----------|
| `flight_number` | string | ✓ |
| `departure_date` | ISO datetime | ✓ |
| `passenger_names` | string[] | ✓ |

### `check_in`
Calls `POST /gateway/checkin` (no auth required).

| Parameter | Type | Required |
|-----------|------|----------|
| `flight_number` | string | ✓ |
| `departure_date` | ISO datetime | ✓ |
| `passenger_name` | string | ✓ |

---

## Design & Technical Decisions

### Why a separate MCP server process?
The assignment explicitly calls for an **MCP server as a distinct component**
in the architecture (`Agent Backend → MCP Client → MCP Server → Gateway`).
Rather than baking tool logic into the FastAPI app, `mcp_server.py` is a
standalone program built with `FastMCP` from the official `mcp` Python SDK.
The agent backend acts as a real MCP client: it spawns the server as a child
process over **stdio transport**, issues `list_tools` and `call_tool` requests,
and never touches the gateway directly. This keeps tool definitions reusable
by any MCP-compatible host and matches the PDF's architecture diagram.

### Why Ollama over OpenAI API?
The assignment allows local LLMs. Ollama runs fully on-device — no API keys, no internet dependency, no cost per token. `qwen2.5:7b` provides reliable tool calling performance for this use case.

### Why httpx directly instead of the Ollama/OpenAI SDK?
Both the `ollama` Python SDK (Pydantic validation mismatch between Ollama server v0.17.5 and SDK v0.6.1) and the `openai` SDK v2 (which validates request bodies with Pydantic and expects `arguments` as dict) caused runtime errors when passing tool call results back to the model. Using Ollama's native `/api/chat` endpoint via `httpx` bypasses all SDK-level validation and gives full control over the message format.

### Why UTC datetime normalization?
The midterm API uses PostgreSQL `timestamptz` columns. Npgsql (EF Core's PostgreSQL driver) enforces strict `DateTimeKind` on comparisons — passing a date string without a timezone suffix (`2026-04-22`) throws an unhandled exception. The agent backend normalizes all dates: query start dates → `T00:00:00Z`, query end dates → `T23:59:59Z`, booking/check-in dates → `T00:00:00Z` (if no time provided).

### Gateway-first: all calls route through Ocelot
Per assignment requirements, every API call goes through the Ocelot gateway. The `Client` header is set on all requests to satisfy the gateway's rate-limiting client identification rule.

### Session management
Conversation history is stored in-memory (Python dict keyed by `session_id`). The frontend generates a UUID per browser session (stored in `sessionStorage`). This provides per-tab isolation without a database dependency.

---

## Issues Encountered

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Ollama SDK Pydantic error on tool calls | `ollama` SDK v0.6.1 expects `arguments` as `dict`, server returns JSON string | Replaced SDK with direct `httpx` calls to Ollama's native `/api/chat` endpoint |
| OpenAI SDK v2 same Pydantic error | `openai` v2 validates outgoing message `tool_calls.function.arguments` as dict | Same fix — native httpx |
| Flight query returning HTTP 500 | Npgsql rejects `DateTime` without UTC kind on `timestamptz` columns | Append `T00:00:00Z` / `T23:59:59Z` to all date parameters |
| Gateway rate limit rejected | Wrong client ID header (`Oc-Client`) — actual header name is `Client` | Fixed header in `tools.py` |
| LLM using wrong year (2023) | LLM has no knowledge of current date | Injected `date.today()` into system prompt at request time |
| LLM using IZM instead of ADB for Izmir | Training data maps Izmir → IZM (old IATA code) | Added Turkish airport code mapping to system prompt |

---

## Midterm Project

This assignment extends the SE4458 Midterm project:

- **Midterm Repo:** https://github.com/batikanakdenizz/SE4458-AirlineTicketing
- **Gateway:** https://gateway-midterm-begsgfcubdhxaph0.francecentral-01.azurewebsites.net
- **API Swagger:** https://api-midterm-bgareudhf2aaakar.francecentral-01.azurewebsites.net/index.html

---


## Author

**Batikan Akdeniz** — SE4458 Software Architecture, Spring 2025–2026
