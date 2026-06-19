# Enterprise MCP Operations Console

![CI](https://github.com/Diluksha-Upeka/MCP/actions/workflows/ci.yml/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

Enterprise-grade Model Context Protocol server with secure tool execution, hybrid retrieval, and human-in-the-loop approvals. Includes a Next.js UI, Docker deployment, and GitHub Actions validation.

## System Architecture & Component Flow

```mermaid
flowchart TD
    subgraph Frontend [The Manager's Dashboard]
        UI[Next.js UI / page.tsx]
        API[Next.js API Routes]
        UI <-->|HTTP/JSON| API
    end

    subgraph Backend [The Engine & Security Desk]
        Server[mcp_project/server.py\nStarlette + MCP Server]
        Auth[mcp_project/auth.py\nSecurity & JWT]
        DB_Connector[mcp_project/db.py\nRelational Connector]
        Hybrid_Connector[mcp_project/hybrid.py\nAI Retrieval Connectors]
        Server --- Auth
        Server --- DB_Connector
        Server --- Hybrid_Connector
    end

    subgraph Storage [The Storage Room / Databases]
        SQLite[(SQLite\nUsers, Logs, Approvals)]
        Qdrant[(Qdrant\nVector Search / Docs)]
        Neo4j[(Neo4j\nGraph / Relationships)]
    end

    subgraph Clients [AI Agents]
        LangGraph[Orchestrator\nlanggraph_demo.py]
    end

    API <-->|REST / SSE| Server
    LangGraph <-->|MCP Protocol| Server
    DB_Connector <--> SQLite
    Hybrid_Connector <--> Qdrant
    Hybrid_Connector <--> Neo4j
```

## Human-in-the-Loop (HITL) Execution Flow

This chart shows how sensitive actions (like deactivating a user) are safely paused and routed to a human for approval:

```mermaid
sequenceDiagram
    actor AI as AI Agent
    participant Server as Python Server (server.py)
    participant DB as SQLite DB (db.py)
    participant API as Next.js API
    actor Human as Admin Manager (UI)

    AI->>Server: Call tool: `deactivate_user(id: 5)`
    Server->>Server: Check tool sensitivity
    Note over Server: Action is dangerous!<br/>Suspending execution...
    Server->>DB: Create `approval_request` (Status: Pending)
    Server-->>AI: Return "Action suspended. Waiting for approval."
    
    Human->>API: Load Dashboard (localhost:3000)
    API->>Server: GET /api/approvals
    Server->>DB: Fetch all pending approvals
    DB-->>Server: [Request #1: Deactivate User #5]
    Server-->>API: Returns approval list
    API-->>Human: Displays pending Action #1 on screen
    
    Human->>API: Clicks "Approve"
    API->>Server: POST /api/approvals/1/approve
    Server->>DB: Update request status to "Approved"
    Server->>DB: Execute ACTUAL `deactivate_user` query
    Server->>DB: Write success to `audit_logs`
    Server-->>API: 200 OK Status
    API-->>Human: UI Updates (Action Completed)
```

## Why these schemas

- SOPs and system logs model real enterprise workflows and incident response.
- Graph entities and edges support relationship-aware retrieval for dependency reasoning.
- Audit logs and approval requests enable traceability and HITL governance.

## Core MCP primitives

- Resources: SOP catalog, recent logs, graph entities, plus schema.
- Tools: deterministic JSON schema per tool, including sensitive tool gating.
- Prompts: dynamic ops assistant prompt adapting to role and incident level.

## Security model

- OAuth/JWT verification at the MCP layer via JWKS.
- Scope-based authorization per tool.
- Full audit logging for all tool calls.
- HITL approval queue for sensitive actions.

## Quick start (local)

### 1) Setup Python

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Initialize SQLite

```bash
sqlite3 enterprise_data.db < schema.sql
```

The server auto-initializes the database if the file is missing.

### 3) Run MCP server (SSE)

```bash
set MCP_AUTH_REQUIRED=false
python mcp_project/server.py --transport sse --port 8000
```

### MCP server env vars

```
MCP_AUTH_REQUIRED=true|false
MCP_JWKS_URL=
MCP_ISSUER=
MCP_AUDIENCE=
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

See [.env.example](.env.example) and [next-app/.env.example](next-app/.env.example).

### 4) Seed hybrid backends (optional)

```bash
python scripts/seed_hybrid.py
```

## Next.js UI

### 1) Install deps

```bash
cd next-app
npm install
npm run dev
```

### 2) Env vars (Next.js)

```
MCP_BASE_URL=http://localhost:8000
MCP_DEV_TOKEN=<optional-dev-token>
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
NEXTAUTH_SECRET=<random-32-byte-base64>
NEXTAUTH_URL=http://localhost:3000
```

The UI uses NextAuth with Google OAuth. If OAuth is not configured, provide `MCP_DEV_TOKEN` and set `MCP_AUTH_REQUIRED=false` on the server.

## Docker

```bash
docker compose up --build
```

Services:
- MCP server on 8000
- Next.js UI on 3000
- Neo4j on 7474/7687
- Qdrant on 6333

## Orchestrator demo (LangGraph)

```bash
set MCP_API_URL=http://localhost:8000/api
set MCP_TOKEN=<your-jwt>
python orchestrator/langgraph_demo.py
```

## MCP tools and resources

See [mcp_project/server.py](mcp_project/server.py) for full tool definitions. Resources are exposed for SOPs, logs, graph entities, and schema.

## CI/CD

GitHub Actions builds Python and Next.js, validates the schema, and builds Docker images. See [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Streamlit Frontend (Prototype)

The project also includes a Streamlit-based chat interface that was the v1 prototype before the Next.js rewrite. It connects to the same database via `db.py` and uses Groq LLM for tool-calling.

```bash
streamlit run mcp_project/app.py
```

Requires `GROQ_API_KEY` in your `.env` file.

## Repository map

- [mcp_project/server.py](mcp_project/server.py) MCP server + REST proxy
- [mcp_project/app.py](mcp_project/app.py) Streamlit chat prototype
- [mcp_project/db.py](mcp_project/db.py) SQLite access layer
- [mcp_project/auth.py](mcp_project/auth.py) OAuth/JWT verification
- [mcp_project/hybrid.py](mcp_project/hybrid.py) Qdrant + Neo4j adapters
- [schema.sql](schema.sql) data model
- [next-app](next-app) Next.js ops console
- [orchestrator](orchestrator) LangGraph agent demo
- [docker-compose.yml](docker-compose.yml) local stack
