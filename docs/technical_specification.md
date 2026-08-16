# MedBridge v3 — Technical Specification Document

> **Document Status:** Implementation-Ready
> **Architecture Baseline:** Corrected architecture incorporating all 26 ADL resolutions
> **Date:** 2026-08-15
> **Source Artifacts:** Master Project Context, Architecture Decision Log, 5 Architecture Diagrams

---

## Table of Contents

- [Part I: Frontend Architecture](#part-i-frontend-architecture)
- [Part II: Backend Architecture](#part-ii-backend-architecture)
- [Part III: AI/RAG Architecture](#part-iii-airag-architecture)
- [Part IV: Database Architecture](#part-iv-database-architecture)
- [Part V: Storage Architecture (Vector Store & Ingestion)](#part-v-storage-architecture)
- [Part VI: Deployment Architecture](#part-vi-deployment-architecture)
- [Appendix A: Interaction Catalog](#appendix-a-interaction-catalog)
- [Appendix B: Deterministic Response Templates](#appendix-b-deterministic-response-templates)
- [Appendix C: Project Directory Structure](#appendix-c-project-directory-structure)

---

# Part I: Frontend Architecture

## 1. Purpose

Provide a conversational web interface for hypertension patients to submit clinical questions and receive evidence-grounded responses with inline citations. The frontend is a thin presentation layer with no AI logic; all intelligence resides in the backend.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-FE-01** | Render a multi-turn chat interface with message history |
| **R-FE-02** | Submit patient messages to the backend API and display streaming or polled responses |
| **R-FE-03** | Display the routing action badge (`ANSWER`, `SOFT-ASK`, `GENERALIZE`, `ABSTAIN`, `ESCALATE`) for each response |
| **R-FE-04** | Render a collapsible citations panel showing source guideline, section, and excerpt for each inline marker |
| **R-FE-05** | Manage session lifecycle: create a new `session_id` on first visit, persist it across page reloads via URL query parameter |
| **R-FE-06** | Display a persistent disclaimer banner: *"This tool provides informational guidance only. It does not replace professional medical advice."* |

## 3. Internal Components

### 3.1 Technology Selection

| Property | Value | Rationale |
| :--- | :--- | :--- |
| **Framework** | Streamlit | Python-only stack; rapid prototyping; built-in session state; no Node.js dependency (ADL-007) |
| **Runtime** | Python / Tornado | Port 8501 |
| **HTTP Client** | `httpx` (async) | Communicate with FastAPI backend |

### 3.2 Page Structure

```
┌──────────────────────────────────────────────────────────┐
│  MedBridge — Clinical Guidance Assistant                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  ⚠ DISCLAIMER BANNER (persistent, not dismissable)  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌─────────────────────────────┬────────────────────────┐ │
│  │       CHAT PANEL            │   CITATIONS PANEL      │ │
│  │                             │   (collapsible)        │ │
│  │  [Patient]: My BP is        │                        │ │
│  │  145/92 this morning...     │   ┌──────────────────┐ │ │
│  │                             │   │ [1] AHA/ACC 2025 │ │ │
│  │  [MedBridge]: Based on      │   │ Section 8.2      │ │ │
│  │  current guidelines [1],    │   │ "For adults with  │ │ │
│  │  a BP of 145/92...          │   │  diabetes, target │ │ │
│  │  ┌────────────────────┐     │   │  BP is <130/80"  │ │ │
│  │  │ 🟢 ANSWER          │     │   └──────────────────┘ │ │
│  │  └────────────────────┘     │                        │ │
│  │                             │   ┌──────────────────┐ │ │
│  │                             │   │ [2] ESC/ESH 2024 │ │ │
│  │                             │   │ Section 6.4      │ │ │
│  │                             │   │ "Consider..."    │ │ │
│  │                             │   └──────────────────┘ │ │
│  ├─────────────────────────────┴────────────────────────┤ │
│  │  [  Type your question here...              ] [Send] │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 3.3 Component Tree

| Component | File | Responsibility |
| :--- | :--- | :--- |
| `app.py` | Entry point | Streamlit page config, layout, session state initialization |
| `chat_panel` | `components/chat.py` | Renders message history with action badges; handles user input |
| `citations_panel` | `components/citations.py` | Renders collapsible citation cards from the latest response |
| `disclaimer_banner` | `components/disclaimer.py` | Persistent non-dismissable safety notice |
| `api_client` | `services/api_client.py` | `httpx`-based client for backend communication |
| `session_manager` | `services/session.py` | Create/resume sessions via URL query params + `st.session_state` |

## 4. APIs (Consumed)

The frontend consumes the following backend endpoints:

### 4.1 Send Message

| Property | Value |
| :--- | :--- |
| **Endpoint** | `POST /api/sessions/{session_id}/messages` |
| **Request Body** | `{ "message": "string" }` |
| **Response Body** | `MessageResponse` (see §II.4.1) |
| **Error Response** | `{ "error_code": "string", "message": "string", "safe_fallback": "string" }` |

### 4.2 Create Session

| Property | Value |
| :--- | :--- |
| **Endpoint** | `POST /api/sessions` |
| **Request Body** | `{}` (empty) |
| **Response Body** | `{ "session_id": "uuid" }` |

### 4.3 Get Session History

| Property | Value |
| :--- | :--- |
| **Endpoint** | `GET /api/sessions/{session_id}/history` |
| **Response Body** | `{ "session_id": "uuid", "messages": [ { "role": "patient" | "assistant", "content": "string", "action": "string", "citations": [...], "timestamp": "iso8601" } ] }` |

## 5. Data Models (Frontend)

```python
# Frontend-side models (for display purposes)

@dataclass
class Citation:
    marker: str          # "[1]"
    source: str          # "AHA/ACC 2025"
    section: str         # "Section 8.2"
    excerpt: str         # Truncated guideline text

@dataclass
class ChatMessage:
    role: str            # "patient" | "assistant"
    content: str         # Message text (with inline [1], [2] markers)
    action: str | None   # "ANSWER" | "SOFT-ASK" | "GENERALIZE" | "ABSTAIN" | "ESCALATE"
    citations: list[Citation]
    timestamp: str
```

## 6. Interfaces

| Interface | Direction | Protocol | Data |
| :--- | :--- | :--- | :--- |
| Frontend → Backend | Outbound | HTTP POST/GET (JSON) | Patient messages, session requests |
| Backend → Frontend | Inbound | HTTP Response (JSON) | `MessageResponse` with action, text, citations |

## 7. Dependencies

| Package | Version | Purpose |
| :--- | :--- | :--- |
| `streamlit` | ≥ 1.35 | UI framework |
| `httpx` | ≥ 0.27 | Async HTTP client |

## 8. Security Considerations

| Concern | Mitigation |
| :--- | :--- |
| **No authentication** | Sessions identified by UUID in URL. Acceptable for academic prototype (ASM-01). |
| **XSS in chat messages** | Streamlit's `st.markdown` auto-escapes HTML. Do not use `unsafe_allow_html=True` for patient-sourced content. |
| **Session hijacking** | UUIDs are unguessable (128-bit random). No mitigation beyond this for semester scope. |

## 9. Error Handling

| Error Condition | Frontend Behavior |
| :--- | :--- |
| Backend returns HTTP 4xx/5xx | Display `safe_fallback` message from error response body. If no body, show: *"We're unable to process your question right now. Please try again, or consult your healthcare provider."* |
| Network timeout (> 15 seconds) | Display timeout message with retry button |
| Backend unreachable | Display connection error with guidance to check if the server is running |

## 10. Configuration Requirements

| Config | Source | Default |
| :--- | :--- | :--- |
| `MEDBRIDGE_API_URL` | Environment variable | `http://localhost:8000` |
| Streamlit port | CLI argument | `8501` |
| Page title | Hardcoded | `"MedBridge — Clinical Guidance Assistant"` |

## 11. Logging Requirements

| Event | Level | Content |
| :--- | :--- | :--- |
| API request sent | `DEBUG` | Endpoint, session_id, message length |
| API response received | `INFO` | session_id, action, response time (ms) |
| API error | `ERROR` | Status code, error body, session_id |
| Session created | `INFO` | New session_id |

## 12. Testing Considerations

| Test Type | Scope |
| :--- | :--- |
| **Unit** | `api_client` request/response serialization; `session_manager` UUID generation and persistence |
| **Integration** | Full round-trip: submit message → receive response → verify action badge and citations render |
| **Manual** | Visual inspection of layout, citation panel toggle, disclaimer visibility, action badge colors |

---

# Part II: Backend Architecture

## 1. Purpose

Serve as the API gateway, session manager, and pipeline orchestrator. The backend receives patient messages, coordinates all AI pipeline stages, manages persistent state via PostgreSQL, and returns safe responses.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-BE-01** | Expose REST API endpoints for session creation, message submission, and history retrieval |
| **R-BE-02** | Manage session lifecycle: create, load, and update session state in PostgreSQL |
| **R-BE-03** | Orchestrate the full AI pipeline: Emergency Classifier → Context Extractor → State Projector → Context Gate → Hybrid Retrieval → Reranking → Evidence Gate → Response Generator |
| **R-BE-04** | Enforce the Context Gate state machine: SOFT-ASK (count < 2), forced GENERALIZE (count ≥ 2), or PROCEED |
| **R-BE-05** | Enforce Evidence Gate routing: bypass LLM Call 4 for ABSTAIN/ESCALATE with deterministic templates |
| **R-BE-06** | Write audit logs for every request with complete gate decision data |
| **R-BE-07** | Handle all errors gracefully: never return HTTP 500 to the patient |

## 3. Internal Components

### 3.1 Technology Stack

| Component | Technology |
| :--- | :--- |
| **Framework** | FastAPI 0.111+ |
| **ASGI Server** | Uvicorn (Python 3.11) |
| **ORM** | SQLAlchemy 2.0 (async mode) |
| **DB Driver** | asyncpg |
| **Validation** | Pydantic v2 |
| **HTTP Client** | httpx (async, for LLM APIs) |

### 3.2 Module Structure

```
medbridge/
├── main.py                          # FastAPI app factory, lifespan, middleware
├── config.py                        # Settings (Pydantic BaseSettings from env)
├── api/
│   ├── routes/
│   │   ├── sessions.py              # POST /api/sessions, GET /api/sessions/{id}/history
│   │   └── messages.py              # POST /api/sessions/{id}/messages
│   ├── schemas/
│   │   ├── requests.py              # MessageRequest
│   │   ├── responses.py             # MessageResponse, SessionResponse, ErrorResponse
│   │   └── enums.py                 # ActionEnum, EventTypeEnum
│   └── middleware/
│       └── error_handler.py         # Global exception → safe fallback response
├── core/
│   ├── orchestrator.py              # Pipeline orchestration (the main control flow)
│   ├── emergency_classifier.py      # Deterministic fast-path (ADL-002)
│   └── templates.py                 # Pre-vetted ABSTAIN/ESCALATE response templates
├── ai/
│   ├── llm_wrapper.py               # Resilient LLM Wrapper (retry, JSON repair, fallback)
│   ├── context_extractor.py         # LLM Call 1
│   ├── context_gate.py              # LLM Call 2
│   ├── evidence_gate.py             # LLM Call 3
│   ├── response_generator.py        # LLM Call 4
│   └── schemas/
│       ├── extractor.py             # ExtractorOutput Pydantic model
│       ├── context_gate.py          # ContextGateOutput Pydantic model
│       ├── evidence_gate.py         # EvidenceGateOutput Pydantic model
│       └── response_generator.py    # ResponseGeneratorOutput Pydantic model
├── retrieval/
│   ├── hybrid_retriever.py          # BM25 + Dense search with RRF fusion
│   ├── reranker.py                  # Cross-encoder reranking (threadpool-offloaded)
│   └── embedder.py                  # Dense + sparse embedding client (fastembed + bge)
├── state/
│   ├── projector.py                 # Deterministic State Projector (ADL-001)
│   └── session_manager.py           # Session CRUD, snapshot load/save, soft_ask_count
├── db/
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── connection.py                # Async engine + session factory
│   └── migrations/                  # Alembic migrations
└── ingestion/
    ├── __main__.py                  # CLI entry: python -m medbridge.ingestion
    ├── parser.py                    # PyMuPDF PDF extraction
    ├── chunker.py                   # Section-aware text chunking
    └── indexer.py                   # Qdrant upsert with schema validation
```

## 4. APIs (Exposed)

### 4.1 Send Message — `POST /api/sessions/{session_id}/messages`

This is the primary endpoint. It orchestrates the entire AI pipeline.

**Request:**

```json
{
  "message": "My BP was 145/92 this morning. I take Amlodipine 5mg daily. Is this controlled?"
}
```

**Success Response (HTTP 200):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_text": "Based on current AHA/ACC guidelines [1], a blood pressure of 145/92 mmHg is above the recommended target...",
  "action": "ANSWER",
  "citations": [
    {
      "marker": "[1]",
      "chunk_id": "aha_2025_s8_c3",
      "source": "AHA/ACC 2025",
      "section": "Section 8.2",
      "excerpt": "For adults with diabetes, the recommended BP target is <130/80 mmHg."
    }
  ],
  "soft_ask_count": 0,
  "timestamp": "2026-08-15T02:10:00Z"
}
```

**Error Response (HTTP 422 / 500):**

```json
{
  "error_code": "PIPELINE_FAILURE",
  "message": "Unable to process your question at this time.",
  "safe_fallback": "For immediate health concerns, please contact your healthcare provider or call emergency services."
}
```

### 4.2 Create Session — `POST /api/sessions`

**Response (HTTP 201):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 4.3 Get Session History — `GET /api/sessions/{session_id}/history`

**Response (HTTP 200):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "role": "patient",
      "content": "What is a good BP target for someone my age?",
      "action": null,
      "citations": [],
      "timestamp": "2026-08-15T02:05:00Z"
    },
    {
      "role": "assistant",
      "content": "To give you personalized guidance, could you share your age and any current medications?",
      "action": "SOFT-ASK",
      "citations": [],
      "timestamp": "2026-08-15T02:05:02Z"
    }
  ]
}
```

### 4.4 Health Check — `GET /health`

**Response (HTTP 200):**

```json
{
  "status": "healthy",
  "postgres": "connected",
  "qdrant": "connected",
  "llm_provider": "groq",
  "timestamp": "2026-08-15T02:10:00Z"
}
```

## 5. Data Models (Backend — Pydantic)

### 5.1 API Schemas

```python
# api/schemas/enums.py
from enum import StrEnum

class ActionEnum(StrEnum):
    SOFT_ASK = "SOFT-ASK"
    ANSWER = "ANSWER"
    GENERALIZE = "GENERALIZE"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"

class EventTypeEnum(StrEnum):
    BP_READING = "BP_READING"
    MEDICATION_ADDED = "MEDICATION_ADDED"
    MEDICATION_STOPPED = "MEDICATION_STOPPED"
    SYMPTOM_REPORTED = "SYMPTOM_REPORTED"
    DEMOGRAPHIC = "DEMOGRAPHIC"
    LAB_RESULT = "LAB_RESULT"
```

```python
# api/schemas/requests.py
from pydantic import BaseModel, Field

class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000,
                         description="Patient's clinical question")
```

```python
# api/schemas/responses.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class CitationResponse(BaseModel):
    marker: str                # "[1]"
    chunk_id: str              # "aha_2025_s8_c3"
    source: str                # "AHA/ACC 2025"
    section: str               # "Section 8.2"
    excerpt: str               # Truncated evidence text

class MessageResponse(BaseModel):
    session_id: UUID
    response_text: str
    action: ActionEnum
    citations: list[CitationResponse]
    soft_ask_count: int
    timestamp: datetime

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    safe_fallback: str
```

### 5.2 AI Pipeline Schemas

```python
# ai/schemas/extractor.py
from pydantic import BaseModel
from typing import Any

class DeltaEvent(BaseModel):
    event_type: EventTypeEnum
    payload: dict[str, Any]

class ExtractorOutput(BaseModel):
    delta_events: list[DeltaEvent]
    search_query: str
    raw_intent: str
```

```python
# ai/schemas/context_gate.py
from pydantic import BaseModel
from typing import Literal

class ContextGateOutput(BaseModel):
    action: Literal["SOFT-ASK", "PROCEED"]
    missing_fields: list[str]
    rationale: str
```

```python
# ai/schemas/evidence_gate.py
from pydantic import BaseModel
from typing import Literal

class EvidenceGateOutput(BaseModel):
    action: Literal["ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]
    evidence_sufficient: bool
    rationale: str
```

```python
# ai/schemas/response_generator.py
from pydantic import BaseModel

class GeneratedCitation(BaseModel):
    marker: str          # "[1]"
    chunk_id: str        # "aha_2025_s8_c3"
    source: str          # "AHA/ACC 2025"
    section: str         # "Section 8.2"
    excerpt: str         # Relevant excerpt

class ResponseGeneratorOutput(BaseModel):
    response_text: str
    citations: list[GeneratedCitation]
```

## 6. Interfaces

### 6.1 Inbound Interfaces

| Interface | Source | Protocol | Authentication |
| :--- | :--- | :--- | :--- |
| REST API | Streamlit Frontend | HTTP/JSON on :8000 | None (session_id in URL path) |

### 6.2 Outbound Interfaces

| Interface | Destination | Protocol | Authentication |
| :--- | :--- | :--- | :--- |
| LLM Inference | Groq Cloud API | HTTPS/JSON on :443 | Bearer token (`GROQ_API_KEY`) |
| LLM Inference (fallback) | OpenAI API | HTTPS/JSON on :443 | Bearer token (`OPENAI_API_KEY`) |
| Database | PostgreSQL | TCP/SQL on :5432 | Username/password (env vars) |
| Vector Store | Qdrant | HTTP/gRPC on :6333 | None (loopback-only binding) |

## 7. Dependencies

| Package | Version | Purpose |
| :--- | :--- | :--- |
| `fastapi` | ≥ 0.111 | Web framework |
| `uvicorn[standard]` | ≥ 0.30 | ASGI server |
| `pydantic` | ≥ 2.7 | Data validation |
| `sqlalchemy[asyncio]` | ≥ 2.0 | ORM (async mode) |
| `asyncpg` | ≥ 0.29 | PostgreSQL async driver |
| `httpx` | ≥ 0.27 | Async HTTP client for LLM APIs |
| `qdrant-client` | ≥ 1.9 | Qdrant SDK |
| `fastembed` | ≥ 0.3 | Dense + sparse embedding |
| `sentence-transformers` | ≥ 3.0 | Cross-encoder reranker |
| `pymupdf` | ≥ 1.24 | PDF parsing (ingestion) |
| `alembic` | ≥ 1.13 | Database migrations |
| `pydantic-settings` | ≥ 2.3 | Settings from environment |

## 8. Security Considerations

| Concern | Implementation |
| :--- | :--- |
| **Input validation** | Pydantic enforces `message` max length (2000 chars), required `session_id` UUID format |
| **Prompt injection mitigation** | All LLM prompts use XML-delimited structure: `<untrusted_user_input>` separates patient text from system instructions (ADL-018) |
| **API key protection** | `GROQ_API_KEY` and `OPENAI_API_KEY` loaded from `.env`, never logged or returned in responses |
| **Database port binding** | PostgreSQL and Qdrant bound to `127.0.0.1` only (ADL-019) |
| **PII exposure** | Acknowledged gap: patient data is sent to Groq/OpenAI unredacted. Use synthetic data for all testing (ADL-017) |
| **CORS** | Restrict `allow_origins` to `["http://localhost:8501"]` (Streamlit origin only) |

## 9. Error Handling

### 9.1 Global Error Handler Middleware

```python
# api/middleware/error_handler.py
# Catches ALL unhandled exceptions and returns a safe ErrorResponse

SAFE_FALLBACK = (
    "We're unable to process your question right now. "
    "For immediate health concerns, please contact your healthcare provider "
    "or call emergency services."
)

@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An internal error occurred.",
            safe_fallback=SAFE_FALLBACK
        ).model_dump()
    )
```

### 9.2 Error Scenarios

| Error | Status | Behavior |
| :--- | :--- | :--- |
| Invalid `session_id` format | 422 | Pydantic validation error with field details |
| Session not found | 404 | `{ "error_code": "SESSION_NOT_FOUND", ... }` |
| Empty message | 422 | Pydantic `min_length=1` constraint |
| LLM API timeout | 200 | Resilient wrapper retries 3×; on permanent failure, returns `GENERALIZE` or `ESCALATE` template |
| LLM malformed JSON | 200 | Resilient wrapper retries with JSON repair; on failure, deterministic fallback |
| PostgreSQL connection failure | 503 | `{ "error_code": "DATABASE_UNAVAILABLE", ... }` |
| Qdrant connection failure | 200 | Skip retrieval; route to `GENERALIZE` with cached general guidance |

## 10. Configuration Requirements

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    GROQ_API_KEY: str
    OPENAI_API_KEY: str = ""                          # Optional fallback
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE_GATES: float = 0.0
    LLM_TEMPERATURE_GENERATOR: float = 0.3
    LLM_MAX_TOKENS_GATES: int = 512
    LLM_MAX_TOKENS_GENERATOR: int = 1024
    LLM_SEED: int = 42
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 1.0                # Seconds

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://medbridge_app:password@127.0.0.1:5432/medbridge"

    # Qdrant
    QDRANT_URL: str = "http://127.0.0.1:6333"
    QDRANT_COLLECTION: str = "clinical_guidelines"

    # Retrieval
    RETRIEVAL_TOP_K_CANDIDATES: int = 20
    RETRIEVAL_TOP_K_RERANKED: int = 5
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    SPARSE_MODEL: str = "Qdrant/bm25"

    # Safety
    SOFT_ASK_MAX_COUNT: int = 2

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:8501"]

    class Config:
        env_file = ".env"
```

## 11. Logging Requirements

### 11.1 Structured Logging Format

All backend logs use structured JSON format via Python `structlog`:

```json
{
  "timestamp": "2026-08-15T02:10:00.123Z",
  "level": "INFO",
  "event": "pipeline_complete",
  "session_id": "550e8400-...",
  "gate_1_action": "PROCEED",
  "gate_2_action": "ANSWER",
  "final_action": "ANSWER",
  "latency_ms": 4230,
  "llm_calls": 4,
  "retrieval_count": 20,
  "reranked_count": 5
}
```

### 11.2 Log Events

| Event | Level | Fields |
| :--- | :--- | :--- |
| `request_received` | INFO | session_id, message_length |
| `emergency_detected` | WARN | session_id, matched_pattern |
| `extractor_complete` | DEBUG | session_id, event_count, search_query |
| `state_projected` | DEBUG | session_id, snapshot_size_bytes |
| `context_gate_result` | INFO | session_id, action, missing_fields, rationale |
| `retrieval_complete` | DEBUG | session_id, candidate_count, latency_ms |
| `reranker_complete` | DEBUG | session_id, top5_scores, latency_ms |
| `evidence_gate_result` | INFO | session_id, action, evidence_sufficient, rationale |
| `response_generated` | INFO | session_id, action, citation_count, response_length |
| `llm_call_failed` | ERROR | session_id, call_name, attempt, error_type |
| `llm_fallback_triggered` | WARN | session_id, call_name, fallback_action |
| `pipeline_complete` | INFO | session_id, final_action, total_latency_ms |
| `audit_log_written` | DEBUG | session_id, audit_id |

## 12. Testing Considerations

| Test Type | Scope | Tooling |
| :--- | :--- | :--- |
| **Unit** | Each AI pipeline stage in isolation (mock LLM responses); State Projector event-folding rules; Emergency classifier pattern matching | `pytest`, `pytest-asyncio` |
| **Integration** | Full pipeline end-to-end with mocked LLM; Database CRUD operations; Qdrant search with test collection | `pytest`, `httpx.AsyncClient`, `testcontainers` |
| **Contract** | Validate all 4 LLM output schemas against sample responses | Pydantic model validation |
| **Benchmark** | MedBridge-AQ evaluation suite (200+ vignettes); RABBITS adversarial tests | Custom evaluation scripts |

---

# Part III: AI/RAG Architecture

## 1. Purpose

Implement the Two-Stage Answerability Engine: a sequential AI pipeline that extracts patient context, evaluates sufficiency, retrieves evidence, evaluates evidence adequacy, and generates grounded clinical responses.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-AI-01** | Extract structured medical facts from unstructured patient text (LLM Call 1) |
| **R-AI-02** | Classify patient context sufficiency for safe personalization (LLM Call 2) |
| **R-AI-03** | Retrieve and rank clinical guideline evidence via hybrid search (BM25 + Dense + Reranking) |
| **R-AI-04** | Classify evidence sufficiency and determine routing action (LLM Call 3) |
| **R-AI-05** | Generate grounded, cited responses using XML-isolated prompts (LLM Call 4) |
| **R-AI-06** | Wrap all LLM calls in resilient retry logic with deterministic fallbacks |

## 3. Internal Components

### 3.1 Pipeline Stages (Corrected Architecture)

```mermaid
flowchart TD
    INPUT["Patient Message"] --> EC{"Emergency\nClassifier"}
    EC -->|"🔴 EMERGENCY"| TEMPLATE_E["Return ESCALATE\nTemplate"]
    EC -->|"✅ SAFE"| LLM1["LLM Call 1\nContext Extractor"]

    LLM1 --> SP["Deterministic\nState Projector"]
    SP --> DB_W[("PostgreSQL\nAppend Event +\nUpdate Snapshot")]
    DB_W --> LLM2["LLM Call 2\nContext Gate"]

    LLM2 -->|"PROCEED"| RETRIEVE
    LLM2 -->|"SOFT-ASK\n(count < 2)"| LLM4_SA["LLM Call 4\nSOFT-ASK Synthesis"]
    LLM2 -->|"SOFT-ASK\n(count ≥ 2)"| FORCE["Force\nGENERALIZE"]
    FORCE --> RETRIEVE

    RETRIEVE["Hybrid Retriever\n(BM25 + Dense + RRF)"] --> QD[("Qdrant")]
    QD --> RERANK["Cross-Encoder\nReranker\n(threadpool)"]
    RERANK --> LLM3["LLM Call 3\nEvidence Gate"]

    LLM3 -->|"ANSWER"| LLM4["LLM Call 4\nResponse Generator"]
    LLM3 -->|"GENERALIZE"| LLM4
    LLM3 -->|"ABSTAIN"| TEMPLATE_A["Return ABSTAIN\nTemplate"]
    LLM3 -->|"ESCALATE"| TEMPLATE_E2["Return ESCALATE\nTemplate"]

    LLM4 --> OUTPUT["Response +\nCitations"]
    LLM4_SA --> OUTPUT_SA["SOFT-ASK\nResponse"]
```

### 3.2 Emergency Triage Classifier

| Property | Value |
| :--- | :--- |
| **Type** | Deterministic (regex + keyword matching) |
| **Location** | `core/emergency_classifier.py` |
| **Invocation** | Before any LLM call, as the very first pipeline step |
| **Latency Target** | < 5ms |

**Detection Patterns:**

```python
EMERGENCY_PATTERNS = [
    # Hypertensive emergency indicators
    r"(?:bp|blood pressure).*(?:2[0-9]{2}|1[89][0-9])\s*/\s*(?:1[2-9][0-9]|[2-9][0-9]{2})",
    r"chest\s+pain",
    r"difficulty\s+breathing",
    r"sudden\s+(?:severe\s+)?headache",
    r"vision\s+(?:loss|changes|blurr)",
    r"numbness.*(?:face|arm|leg)",
    r"slurred?\s+speech",
    r"(?:faint|pass(?:ed)?\s+out|unconscious|seizure)",
    r"blood\s+in\s+(?:urine|stool)",
    r"(?:suicid|self[- ]harm|kill\s+my)",
]
```

**Return:** If matched → `ActionEnum.ESCALATE` + pre-vetted template. If not matched → `None` (continue pipeline).

### 3.3 LLM Call 1 — Context Extractor

**System Prompt:**

```
You are a clinical context extraction engine. Given a patient's message and their
existing medical context snapshot, extract NEW medical facts as structured delta events.
Also produce a reformulated clinical search query suitable for retrieving hypertension
guidelines, and a brief summary of what the patient is asking.

Output ONLY valid JSON matching the schema below. Do not include explanations.

Schema:
{
  "delta_events": [{"event_type": "BP_READING|MEDICATION_ADDED|MEDICATION_STOPPED|SYMPTOM_REPORTED|DEMOGRAPHIC|LAB_RESULT", "payload": {...}}],
  "search_query": "clinical search query for guideline retrieval",
  "raw_intent": "what the patient wants to know"
}
```

**Input construction:**

```
Current patient context:
{context_snapshot_json}

New patient message:
<untrusted_user_input>
{user_message}
</untrusted_user_input>
```

### 3.4 LLM Call 2 — Context Gate

**System Prompt:**

```
You are a clinical context sufficiency classifier. Given a patient's accumulated
medical context and their question intent, determine whether sufficient information
exists to safely provide PERSONALIZED clinical guidance.

If critical context is missing (e.g., age, current medications for a drug-specific
question, relevant comorbidities for a treatment question), output SOFT-ASK.
If context is sufficient for the question type, output PROCEED.

Output ONLY valid JSON. Schema:
{
  "action": "SOFT-ASK" | "PROCEED",
  "missing_fields": ["field1", "field2"],
  "rationale": "explanation"
}
```

### 3.5 Hybrid Retriever

| Property | Value |
| :--- | :--- |
| **Dense Model** | `bge-small-en-v1.5` (384-dim, loaded via `fastembed`) |
| **Sparse Model** | `Qdrant/bm25` (client-side tokenization via `fastembed`) |
| **Fusion** | Reciprocal Rank Fusion: $\text{RRF}(d) = \sum_{r \in \{sparse, dense\}} \frac{1}{k + \text{rank}_r(d)}$ where $k = 60$ |
| **Top-K Candidates** | 20 |
| **Collection** | `clinical_guidelines` |

**Implementation Detail:**

```python
# retrieval/hybrid_retriever.py
async def hybrid_search(query: str, top_k: int = 20) -> list[RetrievedChunk]:
    # 1. Generate dense embedding
    dense_vector = embedding_model.encode(query)  # 384-dim

    # 2. Generate sparse vector (client-side BM25 tokenization)
    sparse_vector = sparse_model.encode(query)     # Sparse indices + values

    # 3. Execute Qdrant hybrid search with RRF fusion
    results = await qdrant_client.query_points(
        collection_name="clinical_guidelines",
        prefetch=[
            models.Prefetch(query=dense_vector, using="dense", limit=top_k),
            models.Prefetch(query=sparse_vector, using="sparse", limit=top_k),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
    )

    return [to_retrieved_chunk(point) for point in results.points]
```

### 3.6 Cross-Encoder Reranker

| Property | Value |
| :--- | :--- |
| **Model** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M params) |
| **Input** | 20 (query, chunk_text) pairs |
| **Output** | Top-5 chunks sorted by reranker score |
| **Execution** | Offloaded to `asyncio.to_thread()` to avoid blocking the event loop (ADL-020) |

```python
# retrieval/reranker.py
from sentence_transformers import CrossEncoder
import asyncio

_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def _sync_rerank(query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    pairs = [(query, c.chunk_text) for c in chunks]
    scores = _reranker.predict(pairs)
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in ranked[:top_k]]

async def rerank(query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
    return await asyncio.to_thread(_sync_rerank, query, chunks, top_k)
```

### 3.7 LLM Call 3 — Evidence Gate

**System Prompt:**

```
You are a clinical evidence sufficiency evaluator. Given a patient's context,
their question, and the top-5 retrieved guideline chunks, determine the
appropriate routing action:

- ANSWER: Evidence directly addresses the patient's specific clinical parameters.
- GENERALIZE: Evidence covers the general topic but not the patient's exact scenario.
- ABSTAIN: Evidence is irrelevant or query is outside the knowledge base domain.
- ESCALATE: Query indicates acute clinical danger regardless of evidence.

Output ONLY valid JSON. Schema:
{
  "action": "ANSWER" | "GENERALIZE" | "ABSTAIN" | "ESCALATE",
  "evidence_sufficient": true | false,
  "rationale": "explanation"
}
```

### 3.8 LLM Call 4 — Response Generator

Invoked **only** for `ANSWER` and `GENERALIZE` actions. `ABSTAIN` and `ESCALATE` bypass this call entirely and use deterministic templates (ADL-015).

**XML-Isolated Prompt:**

```xml
<system_instructions>
You are a clinical communication assistant. Generate a response using
ONLY the evidence provided in <clinical_evidence>. Do not assume or
infer patient information not present in <patient_context>. Follow
the routing action: {action_decision}.
Include inline citation markers [1], [2], etc. for each clinical claim.
Do not provide diagnosis or prescriptions. Use empathetic, plain language.

Output ONLY valid JSON. Schema:
{
  "response_text": "your response with [1] [2] markers",
  "citations": [{"marker":"[1]","chunk_id":"...","source":"...","section":"...","excerpt":"..."}]
}
</system_instructions>

<patient_context>
{context_snapshot_json}
</patient_context>

<clinical_evidence>
<chunk id="1" source="{guideline_id}" section="{section_title}">
{chunk_text}
</chunk>
<!-- up to 5 chunks -->
</clinical_evidence>

<user_query>
<untrusted_user_input>
{original_user_message}
</untrusted_user_input>
</user_query>
```

### 3.9 Resilient LLM Wrapper

```python
# ai/llm_wrapper.py

class ResilientLLMWrapper:
    """Wraps all LLM calls with retry, JSON repair, and deterministic fallback."""

    async def call(
        self,
        call_name: str,                   # "context_extractor", "context_gate", etc.
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],   # Pydantic model class for validation
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> BaseModel | None:
        """
        Returns: Validated Pydantic model instance, or None on permanent failure.
        On None, the orchestrator must apply deterministic fallback logic.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                raw_response = await self._call_llm_api(
                    system_prompt, user_prompt, temperature, max_tokens
                )
                json_str = self._extract_json(raw_response)

                if attempt > 1:
                    json_str = self._repair_json(json_str)

                parsed = output_schema.model_validate_json(json_str)
                return parsed

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"LLM parse failure", call=call_name,
                              attempt=attempt, error=str(e))
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
                continue

            except httpx.TimeoutException:
                logger.error(f"LLM timeout", call=call_name, attempt=attempt)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
                continue

        # Permanent failure
        logger.error(f"LLM permanent failure after {self.max_retries} attempts",
                    call=call_name)
        return None
```

**Fallback Logic (in Orchestrator):**

| Failed Call | Fallback Behavior |
| :--- | :--- |
| LLM Call 1 (Extractor) | Skip extraction; pass raw message to Context Gate with empty delta_events |
| LLM Call 2 (Context Gate) | Default to `PROCEED` (conservative: allow retrieval rather than loop SOFT-ASK) |
| LLM Call 3 (Evidence Gate) | Default to `GENERALIZE` (safe: provide general info without personalization) |
| LLM Call 4 (Generator) | Return pre-vetted `GENERALIZE` template with disclaimer |

## 4. APIs

The AI pipeline does not expose external REST endpoints — it is invoked internally by the backend orchestrator. The following table documents the internal Python API surface (method signatures) for each pipeline component.

| Component | Module | Method Signature | Returns |
| :--- | :--- | :--- | :--- |
| Emergency Classifier | `core/emergency_classifier.py` | `classify(message: str) → ActionEnum \| None` | `ActionEnum.ESCALATE` if emergency detected, else `None` |
| Context Extractor | `ai/context_extractor.py` | `async extract(message: str, snapshot: dict) → ExtractorOutput \| None` | `ExtractorOutput` Pydantic model, or `None` on permanent LLM failure |
| State Projector | `state/projector.py` | `apply_events(snapshot: dict, events: list[DeltaEvent]) → dict` | Updated snapshot dictionary |
| State Projector | `state/projector.py` | `reconstruct_from_events(events: list[DeltaEvent]) → dict` | Fresh snapshot from full replay (validation only) |
| Context Gate | `ai/context_gate.py` | `async evaluate(snapshot: dict, message: str, raw_intent: str) → ContextGateOutput \| None` | `ContextGateOutput` Pydantic model, or `None` on failure |
| Hybrid Retriever | `retrieval/hybrid_retriever.py` | `async hybrid_search(query: str, top_k: int = 20) → list[RetrievedChunk]` | List of `RetrievedChunk` with payload metadata |
| Cross-Encoder Reranker | `retrieval/reranker.py` | `async rerank(query: str, chunks: list[RetrievedChunk], top_k: int = 5) → list[RetrievedChunk]` | Top-K reranked chunks sorted by score |
| Evidence Gate | `ai/evidence_gate.py` | `async evaluate(chunks: list[RetrievedChunk], snapshot: dict, query: str) → EvidenceGateOutput \| None` | `EvidenceGateOutput` Pydantic model, or `None` on failure |
| Response Generator | `ai/response_generator.py` | `async generate(action: ActionEnum, chunks: list[RetrievedChunk], snapshot: dict, query: str) → ResponseGeneratorOutput \| None` | `ResponseGeneratorOutput` Pydantic model, or `None` on failure |
| Resilient LLM Wrapper | `ai/llm_wrapper.py` | `async call(call_name: str, system_prompt: str, user_prompt: str, output_schema: type[BaseModel], temperature: float, max_tokens: int) → BaseModel \| None` | Validated Pydantic model, or `None` on permanent failure |
| Pipeline Orchestrator | `core/orchestrator.py` | `async process_message(session_id: UUID, message: str) → MessageResponse` | Complete `MessageResponse` (always succeeds — fallback guarantees) |

## 5. Data Models

All AI pipeline Pydantic schemas are defined in Part II §5.2. For quick reference:

| Schema | Module | Fields |
| :--- | :--- | :--- |
| `ExtractorOutput` | `ai/schemas/extractor.py` | `delta_events: list[DeltaEvent]`, `search_query: str`, `raw_intent: str` |
| `ContextGateOutput` | `ai/schemas/context_gate.py` | `action: Literal["SOFT-ASK", "PROCEED"]`, `missing_fields: list[str]`, `rationale: str` |
| `EvidenceGateOutput` | `ai/schemas/evidence_gate.py` | `action: Literal["ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]`, `evidence_sufficient: bool`, `rationale: str` |
| `ResponseGeneratorOutput` | `ai/schemas/response_generator.py` | `response_text: str`, `citations: list[GeneratedCitation]` |
| `RetrievedChunk` | `retrieval/hybrid_retriever.py` | `chunk_id: str`, `chunk_text: str`, `guideline_id: str`, `section_title: str`, `page_number: int`, `source_url: str`, `score: float` |

## 6. Interfaces

| Interface | Source → Destination | Protocol |
| :--- | :--- | :--- |
| Orchestrator → LLM Wrapper | Internal Python call | In-process |
| LLM Wrapper → Groq API | HTTPS REST | Bearer token auth |
| Orchestrator → Hybrid Retriever | Internal Python call | In-process |
| Hybrid Retriever → Qdrant | HTTP/gRPC | Loopback network |
| Orchestrator → State Projector | Internal Python call | In-process |
| State Projector → PostgreSQL | SQL via SQLAlchemy | TCP loopback |

## 7. Dependencies

(Subset of backend dependencies specific to AI)

| Package | Purpose |
| :--- | :--- |
| `httpx` | Async LLM API calls |
| `qdrant-client` | Vector search |
| `fastembed` | Dense + sparse embedding (bge-small-en-v1.5, Qdrant/bm25) |
| `sentence-transformers` | Cross-encoder reranker (ms-marco-MiniLM-L-6-v2) |

## 8. Security Considerations

| Concern | Mitigation |
| :--- | :--- |
| **Prompt injection** | All LLM prompts use XML-delimited structure with `<untrusted_user_input>` tags isolating patient text from system instructions (ADL-018). Patient messages are never concatenated directly into system prompts. |
| **Gate bypass attacks** | Context Gate and Evidence Gate operate on structured snapshot data (produced by the Extractor), not on raw patient text. An attacker cannot directly manipulate the gate classification input. |
| **PHI/PII leakage** | Patient context is sent unredacted to Groq/OpenAI. Acknowledged gap (ADL-017). Mitigated by using synthetic data for all testing. Production deployment requires a PII scrubbing layer before LLM calls. |
| **Deterministic safety** | Gate LLM calls use `temperature: 0.0` and `seed: 42` to ensure reproducible routing decisions. Non-deterministic behavior would undermine safety guarantees. |
| **Hallucination containment** | Response Generator prompt restricts output to evidence provided in `<clinical_evidence>` tags. ABSTAIN and ESCALATE actions bypass the generator entirely, using pre-vetted templates (ADL-015). |
| **API key protection** | LLM API keys are loaded from environment variables, never embedded in prompts, logged, or returned in responses. |

## 9. Error Handling

| Error Scenario | Pipeline Stage | Behavior |
| :--- | :--- | :--- |
| LLM returns malformed JSON | Any LLM call (1–4) | Resilient Wrapper retries with JSON repair → re-prompt → deterministic fallback (§3.9) |
| LLM API timeout (> 30s) | Any LLM call (1–4) | Retry with exponential backoff (1s, 2s, 4s). On permanent failure, apply fallback per call (see §3.9 fallback table) |
| LLM API rate limited (HTTP 429) | Any LLM call (1–4) | Respect `Retry-After` header. If Groq exhausted, attempt provider failover to OpenAI if `OPENAI_API_KEY` configured |
| Pydantic validation failure | Any LLM call (1–4) | Treated as parse failure; triggers retry cycle in Resilient Wrapper |
| Qdrant search returns 0 results | Hybrid Retriever | Return empty evidence package; Evidence Gate will route to `ABSTAIN` |
| Cross-encoder model load failure | Reranker | Skip reranking; pass Top-20 unsorted to Evidence Gate (degraded but functional) |
| Embedding model load failure | Hybrid Retriever | Fatal at startup; backend fails health check; operator must verify model availability |
| Emergency classifier regex error | Emergency Classifier | Log error; skip classifier; continue to full pipeline (safe: does not skip gates) |

## 10. Configuration Requirements

| Parameter | Calls 1–3 (Gates) | Call 4 (Generator) |
| :--- | :--- | :--- |
| `model` | `llama-3.1-8b-instant` | `llama-3.1-8b-instant` |
| `temperature` | 0.0 | 0.3 |
| `top_p` | 1.0 | 0.95 |
| `seed` | 42 | — |
| `max_tokens` | 512 | 1024 |
| `response_format` | `{"type": "json_object"}` | `{"type": "json_object"}` |
| `timeout` | 30 seconds | 30 seconds |

Additional configuration:

| Config | Default | Description |
| :--- | :--- | :--- |
| `LLM_MAX_RETRIES` | 3 | Maximum retry attempts per LLM call |
| `LLM_RETRY_BASE_DELAY` | 1.0 | Base delay in seconds for exponential backoff |
| `RETRIEVAL_TOP_K_CANDIDATES` | 20 | Number of candidates from hybrid search |
| `RETRIEVAL_TOP_K_RERANKED` | 5 | Number of chunks after reranking |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model identifier |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Dense embedding model |
| `SPARSE_MODEL` | `Qdrant/bm25` | Sparse tokenization model |
| `SOFT_ASK_MAX_COUNT` | 2 | Loop-breaker threshold before forced GENERALIZE |

## 11. Logging Requirements

| Event | Level | Fields |
| :--- | :--- | :--- |
| `emergency_check_result` | DEBUG | session_id, is_emergency, matched_pattern (if any) |
| `extractor_complete` | DEBUG | session_id, delta_event_count, search_query, raw_intent |
| `extractor_failed` | ERROR | session_id, attempt, error_type, error_message |
| `state_projection_complete` | DEBUG | session_id, snapshot_keys, snapshot_size_bytes |
| `context_gate_result` | INFO | session_id, action, missing_fields, rationale |
| `context_gate_failed` | ERROR | session_id, attempt, error_type; fallback applied: PROCEED |
| `retrieval_complete` | DEBUG | session_id, candidate_count, dense_latency_ms, sparse_latency_ms, fusion_latency_ms |
| `reranker_complete` | DEBUG | session_id, top5_chunk_ids, top5_scores, latency_ms |
| `reranker_skipped` | WARN | session_id, reason (model load failure) |
| `evidence_gate_result` | INFO | session_id, action, evidence_sufficient, rationale |
| `evidence_gate_failed` | ERROR | session_id, attempt, error_type; fallback applied: GENERALIZE |
| `generator_complete` | INFO | session_id, action, citation_count, response_length_chars |
| `generator_failed` | ERROR | session_id, attempt, error_type; fallback applied: template |
| `llm_api_call` | DEBUG | call_name, model, temperature, max_tokens, latency_ms, token_usage |
| `llm_provider_failover` | WARN | call_name, from_provider, to_provider, reason |

## 12. Testing Considerations

| Test Type | Scope |
| :--- | :--- |
| **Unit (mocked LLM)** | Each pipeline stage: verify correct Pydantic schema parsing, fallback behavior, state machine transitions |
| **Unit (State Projector)** | Every event type: BP_READING appends to list; MEDICATION_STOPPED moves drug from current to discontinued; DEMOGRAPHIC merges fields; idempotent replay |
| **Unit (Emergency Classifier)** | Pattern matching: true positives (emergency BP, chest pain, stroke symptoms); true negatives (routine queries); edge cases (borderline BP values) |
| **Unit (Resilient Wrapper)** | JSON repair logic; retry count enforcement; fallback return values per call type; exponential backoff timing |
| **Integration** | Full pipeline with real Qdrant (test collection) and mocked LLM: verify retrieval → reranking → gate routing |
| **Benchmark** | MedBridge-AQ (200+ vignettes): measure routing accuracy, citation precision, hallucination rate |
| **Adversarial** | RABBITS (brand ↔ generic substitution); prompt injection attempts against XML-isolated prompts |

---

# Part IV: Database Architecture

## 1. Purpose

Provide persistent storage for patient session state using an Event Sourcing pattern (append-only event log + materialized snapshot), plus immutable audit logging for all pipeline decisions.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-DB-01** | Store session metadata (creation time, last activity) |
| **R-DB-02** | Append clinical events to an immutable event log |
| **R-DB-03** | Store and update the materialized context snapshot per session |
| **R-DB-04** | Track `soft_ask_count` per session for loop-breaker enforcement |
| **R-DB-05** | Record complete audit logs for every pipeline request |
| **R-DB-06** | Store conversation message history for UI retrieval |

## 3. Internal Components

### 3.1 Technology

| Component | Value |
| :--- | :--- |
| **RDBMS** | PostgreSQL 16 |
| **Container** | Docker (port `127.0.0.1:5432`) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Driver** | asyncpg |
| **Migrations** | Alembic |

### 3.2 Schema — DDL

```sql
-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Table: sessions
-- ============================================================
CREATE TABLE sessions (
    session_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_last_active ON sessions (last_active_at);

-- ============================================================
-- Table: clinical_events (append-only event log)
-- ============================================================
CREATE TYPE event_type_enum AS ENUM (
    'BP_READING',
    'MEDICATION_ADDED',
    'MEDICATION_STOPPED',
    'SYMPTOM_REPORTED',
    'DEMOGRAPHIC',
    'LAB_RESULT'
);

CREATE TABLE clinical_events (
    event_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    event_type  event_type_enum NOT NULL,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_session ON clinical_events (session_id, created_at);

-- Prevent updates and deletes (append-only enforcement)
CREATE RULE no_update_events AS ON UPDATE TO clinical_events DO INSTEAD NOTHING;
CREATE RULE no_delete_events AS ON DELETE TO clinical_events DO INSTEAD NOTHING;

-- ============================================================
-- Table: context_snapshots (materialized projection)
-- ============================================================
CREATE TABLE context_snapshots (
    session_id      UUID PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
    snapshot        JSONB NOT NULL DEFAULT '{}',
    soft_ask_count  INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Table: audit_logs (immutable pipeline decision trail)
-- ============================================================
CREATE TYPE gate_1_action_enum AS ENUM ('SOFT-ASK', 'PROCEED');
CREATE TYPE gate_2_action_enum AS ENUM ('ANSWER', 'GENERALIZE', 'ABSTAIN', 'ESCALATE');
CREATE TYPE final_action_enum AS ENUM ('SOFT-ASK', 'ANSWER', 'GENERALIZE', 'ABSTAIN', 'ESCALATE');

CREATE TABLE audit_logs (
    audit_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    request_message     TEXT NOT NULL,
    gate_1_action       gate_1_action_enum,
    gate_1_rationale    TEXT,
    gate_2_action       gate_2_action_enum,
    gate_2_rationale    TEXT,
    final_action        final_action_enum NOT NULL,
    evidence_chunk_ids  TEXT[],
    response_text       TEXT NOT NULL,
    latency_ms          INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_session ON audit_logs (session_id, created_at);

-- Prevent updates and deletes (immutable audit trail)
CREATE RULE no_update_audit AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE no_delete_audit AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

-- ============================================================
-- Table: message_history (for UI conversation display)
-- ============================================================
CREATE TABLE message_history (
    message_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role        VARCHAR(10) NOT NULL CHECK (role IN ('patient', 'assistant')),
    content     TEXT NOT NULL,
    action      final_action_enum,
    citations   JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON message_history (session_id, created_at);
```

### 3.3 Deterministic State Projector

The State Projector is a pure Python module that applies typed delta events to the context snapshot using deterministic merge rules. It does **not** use the LLM.

### 4.1 Projection Rules

| Event Type | Projection Logic |
| :--- | :--- |
| `BP_READING` | Append to `recent_bp_readings[]`. Keep only last 5 readings. |
| `MEDICATION_ADDED` | Add to `current_medications[]` if not already present (match on drug name, case-insensitive). |
| `MEDICATION_STOPPED` | Remove from `current_medications[]` (match on drug name). Add to `discontinued_medications[]` with timestamp. |
| `SYMPTOM_REPORTED` | Append to `symptoms[]` (deduplicated, case-insensitive). |
| `DEMOGRAPHIC` | Merge into `demographics{}`. Overwrite existing fields (e.g., updated age). |
| `LAB_RESULT` | Append to `lab_results[]`. Keep only last 3 per lab type. |

### 4.2 Snapshot Reconstruction Validator

For testing and integrity checking, the Projector includes a `reconstruct_from_events()` method that replays the full event stream for a session and produces a fresh snapshot. The stored snapshot must exactly match the reconstructed one.

```python
# state/projector.py

class StateProjector:
    def apply_events(self, snapshot: dict, events: list[DeltaEvent]) -> dict:
        """Apply delta events to existing snapshot. Returns updated snapshot."""
        for event in events:
            snapshot = self._apply_single(snapshot, event)
        return snapshot

    def reconstruct_from_events(self, events: list[DeltaEvent]) -> dict:
        """Replay full event stream from scratch. For validation only."""
        return self.apply_events({}, events)

    def _apply_single(self, snapshot: dict, event: DeltaEvent) -> dict:
        match event.event_type:
            case "BP_READING":
                readings = snapshot.setdefault("recent_bp_readings", [])
                readings.append(event.payload)
                snapshot["recent_bp_readings"] = readings[-5:]  # Keep last 5
            case "MEDICATION_ADDED":
                meds = snapshot.setdefault("current_medications", [])
                name = event.payload["drug_name"].lower()
                if not any(m["drug"].lower() == name for m in meds):
                    meds.append({
                        "drug": event.payload["drug_name"],
                        "dosage": event.payload.get("dosage", ""),
                        "frequency": event.payload.get("frequency", ""),
                    })
            case "MEDICATION_STOPPED":
                name = event.payload["drug_name"].lower()
                current = snapshot.get("current_medications", [])
                stopped = [m for m in current if m["drug"].lower() == name]
                snapshot["current_medications"] = [
                    m for m in current if m["drug"].lower() != name
                ]
                disc = snapshot.setdefault("discontinued_medications", [])
                for m in stopped:
                    disc.append({**m, "reason": event.payload.get("reason", "")})
            case "SYMPTOM_REPORTED":
                symptoms = snapshot.setdefault("symptoms", [])
                new = event.payload.get("symptom", "").lower()
                if new and new not in [s.lower() for s in symptoms]:
                    symptoms.append(event.payload["symptom"])
            case "DEMOGRAPHIC":
                demo = snapshot.setdefault("demographics", {})
                demo.update(event.payload)
            case "LAB_RESULT":
                labs = snapshot.setdefault("lab_results", [])
                labs.append(event.payload)
                snapshot["lab_results"] = labs[-3:]
        return snapshot
```

## 4. APIs

The database does not expose external REST endpoints. Access is via SQLAlchemy ORM methods in the `state/session_manager.py` module. The following table catalogs all SQL operations.

| Operation | Table(s) | SQL Type | Caller | Description |
| :--- | :--- | :--- | :--- | :--- |
| Create session | `sessions` | `INSERT` | `session_manager.create_session()` | Insert new session row; return `session_id` UUID |
| Load session state | `sessions`, `context_snapshots` | `SELECT` + `JOIN` | `session_manager.load_session()` | Load snapshot JSONB + `soft_ask_count` at start of each request (ADL-014) |
| Append clinical events | `clinical_events` | `INSERT` (batch) | `state/projector.py` | Bulk insert delta events from Context Extractor |
| Upsert context snapshot | `context_snapshots` | `INSERT ON CONFLICT UPDATE` | `state/projector.py` | Write updated snapshot + increment `soft_ask_count` |
| Write audit log | `audit_logs` | `INSERT` | `core/orchestrator.py` | Record complete gate decision trail |
| Append message | `message_history` | `INSERT` | `core/orchestrator.py` | Record patient message and assistant response |
| Get message history | `message_history` | `SELECT ORDER BY created_at` | `api/routes/sessions.py` | Retrieve conversation history for UI display |
| Reset soft_ask_count | `context_snapshots` | `UPDATE` | `state/session_manager.py` | Reset counter when Context Gate returns `PROCEED` |

**Transaction boundaries:**

| Transaction | Operations Grouped | Isolation Level |
| :--- | :--- | :--- |
| **State update** | Append events + upsert snapshot | `READ COMMITTED` |
| **Audit write** | Insert audit_log + insert message_history (patient) + insert message_history (assistant) | `READ COMMITTED` |

## 5. Data Models

Defined as PostgreSQL DDL in §3.2 above. The corresponding SQLAlchemy ORM models reside in `db/models.py`:

| ORM Model | Table | Primary Key | Key Relationships |
| :--- | :--- | :--- | :--- |
| `Session` | `sessions` | `session_id` (UUID) | Has many `ClinicalEvent`, one `ContextSnapshot`, many `AuditLog`, many `MessageHistory` |
| `ClinicalEvent` | `clinical_events` | `event_id` (UUID) | Belongs to `Session` via `session_id` FK |
| `ContextSnapshot` | `context_snapshots` | `session_id` (UUID) | One-to-one with `Session` |
| `AuditLog` | `audit_logs` | `audit_id` (UUID) | Belongs to `Session` via `session_id` FK |
| `MessageHistory` | `message_history` | `message_id` (UUID) | Belongs to `Session` via `session_id` FK |

## 6. Interfaces

| Interface | Direction | Description |
| :--- | :--- | :--- |
| FastAPI → PostgreSQL | Read | Load session, snapshot, soft_ask_count, message history |
| FastAPI → PostgreSQL | Write | Create session, append events, upsert snapshot, write audit log, append message |
| State Projector → PostgreSQL | Write | Append events + upsert snapshot (within a single transaction) |

## 7. Dependencies

| Package | Version | Purpose |
| :--- | :--- | :--- |
| `sqlalchemy[asyncio]` | ≥ 2.0 | ORM with async session support |
| `asyncpg` | ≥ 0.29 | PostgreSQL async driver (used by SQLAlchemy) |
| `alembic` | ≥ 1.13 | Database schema migrations |
| `psycopg2-binary` | ≥ 2.9 | Alembic migration runner (sync driver for DDL operations) |

## 8. Security Considerations

| Concern | Mitigation |
| :--- | :--- |
| **Port exposure** | Bound to `127.0.0.1:5432` (ADL-019) |
| **Authentication** | Username/password via environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`) |
| **Event immutability** | PostgreSQL rules prevent `UPDATE` and `DELETE` on `clinical_events` and `audit_logs` |
| **SQL injection** | SQLAlchemy parameterized queries (never raw string interpolation) |

## 9. Error Handling

| Error | Behavior |
| :--- | :--- |
| Connection refused | Return HTTP 503 with `safe_fallback` message |
| Transaction deadlock | Retry once; if persistent, return `GENERALIZE` template |
| Unique constraint violation (duplicate event) | Idempotent: skip the duplicate event, log warning |

## 10. Configuration Requirements

| Config | Value |
| :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://medbridge_app:{pass}@127.0.0.1:5432/medbridge` |
| Connection pool size | 5 (semester scale) |
| Statement timeout | 10 seconds |

## 11. Logging Requirements

| Event | Level | Content |
| :--- | :--- | :--- |
| `session_created` | INFO | session_id |
| `events_appended` | DEBUG | session_id, event_count, event_types |
| `snapshot_updated` | DEBUG | session_id, snapshot_size |
| `audit_written` | DEBUG | session_id, audit_id, final_action |
| `db_connection_error` | ERROR | error_message, retry_count |

## 12. Testing Considerations

| Test Type | Scope |
| :--- | :--- |
| **Unit** | State Projector: every event type; idempotent replay; reconstruction matches stored snapshot |
| **Integration** | Full CRUD cycle: create session → append events → read snapshot → write audit |
| **Constraint** | Verify `UPDATE`/`DELETE` rules reject mutations on events and audit logs |
| **Migration** | Alembic up/down migrations run cleanly on empty database |

---

# Part V: Storage Architecture

## (Vector Store & Ingestion Pipeline)

## 1. Purpose

Store pre-indexed clinical guideline text as dense and sparse vectors in Qdrant for hybrid retrieval. Provide a reproducible, schema-validated offline ingestion pipeline for guideline PDFs.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-VS-01** | Store clinical guideline chunks with dense (bge-small-en-v1.5) and sparse (BM25) vectors |
| **R-VS-02** | Support hybrid search (dense + sparse + RRF fusion) returning Top-20 candidates with payload metadata |
| **R-VS-03** | Provide a CLI-based ingestion pipeline for one-time offline indexing of guideline PDFs |
| **R-VS-04** | Validate vector and payload schema on ingestion to prevent runtime query mismatches |

## 3. Internal Components

### 3.1 Qdrant Collection Specification

```python
# Collection creation specification
from qdrant_client import models

COLLECTION_CONFIG = {
    "collection_name": "clinical_guidelines",
    "vectors_config": {
        "dense": models.VectorParams(
            size=384,
            distance=models.Distance.COSINE,
        ),
    },
    "sparse_vectors_config": {
        "sparse": models.SparseVectorParams(
            modifier=models.Modifier.IDF,
        ),
    },
}
```

### 3.2 Ingestion Pipeline

```
┌────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  PDF Source     │────▶│  PyMuPDF     │────▶│  Section-Aware   │
│  (Local File)  │     │  Extractor   │     │  Chunker         │
└────────────────┘     └──────────────┘     └────────┬─────────┘
                                                      │
                                            ┌─────────▼─────────┐
                                            │  Embedding Stage   │
                                            │  • Dense: bge-     │
                                            │    small-en-v1.5   │
                                            │  • Sparse: BM25    │
                                            │    (fastembed)     │
                                            └─────────┬─────────┘
                                                      │
                                            ┌─────────▼─────────┐
                                            │  Schema Validator  │
                                            │  + Qdrant Upsert   │
                                            └───────────────────┘
```

### 3.3 Chunking Configuration

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| **Chunk size** | 512 tokens | Balance between context window usage and retrieval granularity |
| **Overlap** | 64 tokens | Preserve cross-boundary context |
| **Splitting strategy** | Section-aware (split at section headers, then sentence boundaries) | Preserve clinical context units |
| **Metadata preserved** | `guideline_id`, `section_title`, `page_number`, `source_url` | Required for citation generation |

### 3.4 Ingestion CLI

```bash
# Run ingestion
python -m medbridge.ingestion \
  --pdf-dir ./data/guidelines/ \
  --qdrant-url http://127.0.0.1:6333 \
  --collection clinical_guidelines \
  --dry-run      # Validate without writing

# Supported flags
# --pdf-dir         Path to directory containing guideline PDFs
# --qdrant-url      Qdrant server URL
# --collection      Target collection name
# --chunk-size      Token count per chunk (default: 512)
# --chunk-overlap   Overlap tokens (default: 64)
# --recreate        Drop and recreate collection before indexing
# --dry-run         Parse and validate only, do not write to Qdrant
```

## 4. APIs

The vector store does not expose custom REST endpoints. Access is via the `qdrant-client` SDK and the ingestion CLI. The following table catalogs all operations.

### 4.1 Runtime APIs (Query-Time)

| Operation | Caller | SDK Method | Input | Output |
| :--- | :--- | :--- | :--- | :--- |
| Hybrid search | `retrieval/hybrid_retriever.py` | `qdrant_client.query_points()` | Dense vector (384-dim) + sparse vector (BM25) + RRF fusion config | `list[ScoredPoint]` with payload metadata (Top-20) |
| Collection info | `core/orchestrator.py` (health check) | `qdrant_client.get_collection()` | Collection name | `CollectionInfo` (point count, vector config) |

### 4.2 Ingestion APIs (Offline)

| Operation | Caller | SDK Method | Input | Output |
| :--- | :--- | :--- | :--- | :--- |
| Create collection | `ingestion/indexer.py` | `qdrant_client.create_collection()` | `COLLECTION_CONFIG` (dense + sparse vector params) | Success / already exists |
| Delete collection | `ingestion/indexer.py` | `qdrant_client.delete_collection()` | Collection name (used with `--recreate` flag) | Success |
| Batch upsert | `ingestion/indexer.py` | `qdrant_client.upsert()` | `list[PointStruct]` (batch of chunks with vectors + payload) | Upsert count |
| Count points | `ingestion/indexer.py` | `qdrant_client.count()` | Collection name | Integer point count (for validation) |

### 4.3 Ingestion CLI Interface

```bash
python -m medbridge.ingestion [OPTIONS]

Options:
  --pdf-dir PATH        Directory containing guideline PDFs [required]
  --qdrant-url TEXT      Qdrant server URL [default: http://127.0.0.1:6333]
  --collection TEXT      Target collection name [default: clinical_guidelines]
  --chunk-size INT       Token count per chunk [default: 512]
  --chunk-overlap INT    Overlap tokens [default: 64]
  --recreate             Drop and recreate collection before indexing
  --dry-run              Parse and validate only, do not write to Qdrant
  --help                 Show help message
```

## 5. Data Models

**Qdrant Point Structure:**

```python
@dataclass
class GuidelineChunk:
    chunk_id: str              # "{guideline_id}_{section}_{index}" e.g. "aha_2025_s8_c3"
    guideline_id: str          # "AHA_ACC_2025" | "ESC_ESH_2024" | "MEDLINEPLUS"
    section_title: str         # "Section 8.2: Pharmacological Treatment"
    page_number: int           # Source PDF page
    chunk_text: str            # Full text content
    source_url: str            # Document reference URL
    dense_vector: list[float]  # 384-dim bge-small-en-v1.5 embedding
    sparse_vector: SparseVector  # fastembed BM25 indices + values
```

## 6. Knowledge Sources

| Source | Document | Content Scope |
| :--- | :--- | :--- |
| **AHA/ACC 2025** | Hypertension Clinical Practice Guideline | BP classification, treatment thresholds, drug therapy, special populations |
| **ESC/ESH 2024** | Arterial Hypertension Guidelines | European perspectives, drug combinations, target organ damage |
| **MedlinePlus** | High Blood Pressure consumer information | General lifestyle guidance, medication overviews, plain-language explanations |

## 7. Interfaces

| Interface | Direction | Protocol |
| :--- | :--- | :--- |
| Ingestion Worker → Qdrant | Write (upsert) | HTTP/gRPC on :6333 |
| Hybrid Retriever → Qdrant | Read (search) | HTTP/gRPC on :6333 |

## 8. Dependencies

| Package | Purpose |
| :--- | :--- |
| `qdrant-client` | Qdrant SDK (search + upsert) |
| `fastembed` | Dense embedding (bge-small-en-v1.5) + sparse tokenization (Qdrant/bm25) |
| `pymupdf` | PDF text extraction with page-level metadata |

## 9. Security Considerations

| Concern | Mitigation |
| :--- | :--- |
| **Qdrant port exposure** | Bound to `127.0.0.1:6333` (ADL-019) |
| **Data integrity** | Ingestion includes schema validation; `--dry-run` mode for pre-flight checks |
| **Vector tampering** | No authentication on Qdrant API. Acceptable for loopback-only access. |

## 10. Error Handling

| Error | Behavior |
| :--- | :--- |
| PDF parsing failure (corrupted file) | Skip file, log error, continue with remaining files |
| Embedding model load failure | Abort ingestion with clear error message |
| Qdrant connection failure | Abort ingestion (non-transient error for offline batch process) |
| Schema validation failure | Skip chunk, log error with chunk_id, continue |

## 11. Configuration Requirements

| Config | Default | Description |
| :--- | :--- | :--- |
| `QDRANT_URL` | `http://127.0.0.1:6333` | Qdrant server URL |
| `QDRANT_COLLECTION` | `clinical_guidelines` | Collection name |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Dense embedding model |
| `SPARSE_MODEL` | `Qdrant/bm25` | Sparse tokenization model |
| `CHUNK_SIZE` | 512 | Tokens per chunk |
| `CHUNK_OVERLAP` | 64 | Overlap tokens |

## 12. Logging Requirements

| Event | Level | Content |
| :--- | :--- | :--- |
| `ingestion_started` | INFO | pdf_dir, collection, chunk_size, overlap |
| `pdf_parsed` | INFO | filename, page_count, text_length |
| `chunks_created` | INFO | filename, chunk_count |
| `chunks_embedded` | DEBUG | chunk_count, embedding_time_ms |
| `chunks_upserted` | INFO | chunk_count, qdrant_collection |
| `ingestion_complete` | INFO | total_pdfs, total_chunks, total_time_s |
| `ingestion_error` | ERROR | filename/chunk_id, error_message |

## 13. Testing Considerations

| Test Type | Scope |
| :--- | :--- |
| **Unit** | Chunker: verify section-aware splitting preserves headers, respects token limits, produces valid overlap |
| **Unit** | Schema validator: reject chunks missing required payload fields |
| **Integration** | Full pipeline: parse test PDF → chunk → embed → upsert → search → verify results |
| **Dry-run** | Validate `--dry-run` mode parses and validates without writing |

---

# Part VI: Deployment Architecture

## 1. Purpose

Define the complete physical deployment topology, startup procedures, health checks, and operational commands for the MedBridge system on a single local development machine.

## 2. Responsibilities

| Responsibility | Description |
| :--- | :--- |
| **R-DP-01** | Manage PostgreSQL and Qdrant containers via Docker Compose |
| **R-DP-02** | Run FastAPI backend as a local Python process |
| **R-DP-03** | Run Streamlit frontend as a local Python process |
| **R-DP-04** | Route LLM inference to external Groq Cloud API via HTTPS |
| **R-DP-05** | Provide health check endpoints for all services |

## 3. Internal Components

| Component | Type | Technology | Port | Container |
| :--- | :--- | :--- | :---: | :---: |
| **Streamlit Frontend** | Python process | Streamlit / Tornado | 8501 | No |
| **FastAPI Backend** | Python process | FastAPI / Uvicorn | 8000 | No |
| **AI Pipeline** | In-process module | Python (within FastAPI process) | — | No |
| **PostgreSQL** | Data store | PostgreSQL 16 | 5432 | **Yes** (Docker) |
| **Qdrant** | Vector store | Qdrant latest | 6333 / 6334 (gRPC) | **Yes** (Docker) |
| **Groq Cloud API** | External SaaS | HTTPS REST | 443 | N/A |

**Container Management:** Docker Compose v3.9 with named volumes and health checks.
**Non-Containerized Services:** Streamlit and FastAPI run as local Python processes, started manually. They are not containerized to simplify debugging and hot-reloading during development.

## 4. Topology

```
┌─────────────────────────────────────────────────────────────┐
│               Local Machine (Single Node)                    │
│                                                              │
│  ┌──────────────┐    HTTP :8000    ┌──────────────────────┐ │
│  │  Streamlit   │ ──────────────▶  │  FastAPI / Uvicorn   │ │
│  │  :8501       │  ◀──────────────  │  :8000               │ │
│  └──────────────┘                  │                      │ │
│                                    │  ┌────────────────┐  │ │
│                                    │  │ AI Pipeline    │  │ │
│                                    │  │ (in-process)   │  │ │
│                                    │  └────────────────┘  │ │
│                                    └───────┬──────┬───────┘ │
│                                   SQL :5432│      │gRPC     │
│                                            │      │:6333    │
│  ┌─────────────────────────┐               │      │         │
│  │  Docker Compose          │              │      │         │
│  │  ┌───────────────────┐   │   ◀──────────┘      │         │
│  │  │  PostgreSQL 16    │   │                      │         │
│  │  │  127.0.0.1:5432   │   │                      │         │
│  │  └───────────────────┘   │                      │         │
│  │  ┌───────────────────┐   │   ◀──────────────────┘         │
│  │  │  Qdrant           │   │                                │
│  │  │  127.0.0.1:6333   │   │                                │
│  │  └───────────────────┘   │                                │
│  └─────────────────────────┘                                 │
└──────────────────────────────────┬───────────────────────────┘
                                   │ HTTPS :443
                            ┌──────▼──────────┐
                            │  Groq Cloud API  │
                            │  (External SaaS) │
                            └─────────────────┘
```

## 5. Docker Compose (Authoritative)

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgres:16
    container_name: medbridge-postgres
    restart: unless-stopped
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_DB: medbridge
      POSTGRES_USER: medbridge_app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medbridge_app -d medbridge"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    container_name: medbridge-qdrant
    restart: unless-stopped
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"   # gRPC port
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:6333/healthz || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
  qdrant_data:
```

## 6. Environment Configuration

```bash
# .env (template — do not commit real values to version control)
# ============================================================
# LLM Provider
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=                          # Optional fallback
LLM_MODEL=llama-3.1-8b-instant

# Database
POSTGRES_PASSWORD=medbridge_secure_pwd_2026
DATABASE_URL=postgresql+asyncpg://medbridge_app:medbridge_secure_pwd_2026@127.0.0.1:5432/medbridge

# Vector Store
QDRANT_URL=http://127.0.0.1:6333

# Application
CORS_ORIGINS=["http://localhost:8501"]
```

## 7. Startup Sequence

```bash
# 1. Start infrastructure containers
docker compose up -d
docker compose ps     # Verify both services are healthy

# 2. Apply database migrations
cd medbridge/
alembic upgrade head

# 3. Run one-time knowledge ingestion (first time only)
python -m medbridge.ingestion --pdf-dir ./data/guidelines/

# 4. Start the backend API server
uvicorn medbridge.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start the frontend (separate terminal)
streamlit run medbridge/frontend/app.py --server.port 8501
```

## 8. APIs

The deployment layer exposes health check and operational endpoints.

| Endpoint | Method | Purpose | Expected Response |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Application health check | `{"status":"healthy", "postgres":"connected", "qdrant":"connected", "llm_provider":"groq"}` |
| `pg_isready -U medbridge_app -d medbridge` | Shell | PostgreSQL container health | Exit code 0 |
| `http://127.0.0.1:6333/healthz` | `GET` | Qdrant container health | `{"status":"ok"}` |
| `http://localhost:8501` | Browser | Streamlit frontend health | Chat UI renders |

**Operational Commands:**

| Command | Purpose |
| :--- | :--- |
| `docker compose up -d` | Start infrastructure containers |
| `docker compose down` | Stop containers (preserve volumes) |
| `docker compose down -v` | Stop containers and delete all data |
| `docker compose logs -f postgres` | Tail PostgreSQL logs |
| `docker compose logs -f qdrant` | Tail Qdrant logs |
| `docker compose ps` | Check container status and health |
| `alembic upgrade head` | Apply database migrations |
| `python -m medbridge.ingestion --pdf-dir ./data/guidelines/` | Run knowledge ingestion |

## 9. Data Models

The deployment architecture does not define its own data models. All data schemas are owned by:
- **Database layer** (Part IV): PostgreSQL DDL and SQLAlchemy ORM models
- **Vector store layer** (Part V): Qdrant collection and point schemas
- **Backend layer** (Part II): Pydantic API request/response schemas

The deployment layer's responsibility is ensuring these schemas are applied correctly via the startup sequence (migrations + ingestion).

## 10. Interfaces

| Source | Destination | Protocol | Port | Direction |
| :--- | :--- | :--- | :---: | :--- |
| Streamlit Frontend | FastAPI Backend | HTTP (plain, not HTTPS — ADL-021) | 8000 | Outbound |
| FastAPI Backend | PostgreSQL | TCP/SQL via asyncpg | 5432 | Outbound |
| FastAPI Backend | Qdrant | HTTP/gRPC | 6333 / 6334 | Outbound |
| FastAPI Backend | Groq Cloud API | HTTPS REST | 443 | Outbound (internet) |
| Patient Browser | Streamlit Frontend | HTTP | 8501 | Inbound |

All local interfaces are bound to `127.0.0.1` (loopback only). The only outbound internet connection is to Groq Cloud API.

## 11. Dependencies

### 11.1 Infrastructure Dependencies

| Dependency | Version | Purpose |
| :--- | :--- | :--- |
| Docker Engine | ≥ 24.0 | Container runtime for PostgreSQL and Qdrant |
| Docker Compose | ≥ 2.20 (V2 plugin) | Multi-container orchestration |
| Python | ≥ 3.11 | Backend and frontend runtime |
| pip / pipx | Latest | Python package management |

### 11.2 Compute Requirements

| Resource | Minimum | Recommended |
| :--- | :--- | :--- |
| **CPU** | 4 cores | 8 cores |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 5 GB | 10 GB |
| **GPU** | Not required | Not required |
| **Network** | Internet access (for Groq API) | Stable broadband |
| **OS** | Windows 10+, macOS 12+, Ubuntu 22.04+ | Any with Docker support |

## 12. Security Considerations

| Concern | Mitigation |
| :--- | :--- |
| **Container ports** | Bound to `127.0.0.1` only; not accessible from LAN |
| **API keys** | Stored in `.env` file, loaded via `pydantic-settings`, never logged |
| **Docker secrets** | `POSTGRES_PASSWORD` injected via env, not hardcoded |
| **`.env` file** | Added to `.gitignore`; template provided as `.env.example` |

## 13. Error Handling

| Scenario | Recovery |
| :--- | :--- |
| Docker container crashes | `restart: unless-stopped` policy auto-restarts |
| PostgreSQL data corruption | Restore from Docker volume backup |
| Qdrant index loss | Re-run ingestion pipeline (`python -m medbridge.ingestion --recreate`) |
| Groq API key invalid | FastAPI health check reports `llm_provider: "error"`; update `.env` |

## 14. Logging Requirements

| Service | Log Location | Format |
| :--- | :--- | :--- |
| PostgreSQL | Docker stdout (`docker compose logs postgres`) | Standard Postgres log format |
| Qdrant | Docker stdout (`docker compose logs qdrant`) | Qdrant default format |
| FastAPI | stdout (structured JSON via `structlog`) | JSON |
| Streamlit | stdout | Standard Streamlit log format |

## 15. Testing Considerations

| Test Type | Scope |
| :--- | :--- |
| **Smoke** | `docker compose up -d` → verify both containers healthy → run health check |
| **Integration** | Full startup sequence → send test message → verify end-to-end response |
| **Teardown** | `docker compose down -v` removes all containers and volumes cleanly |

---

# Appendix A: Interaction Catalog

Every system interaction, with source, processor, data, and result.

## A.1 Runtime Interactions

| # | Request Source | Processing Component | Data Exchanged | Result Returned |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Patient (browser) | Streamlit Chat UI | Keyboard input (text) | Message displayed in chat panel |
| 2 | Streamlit Chat UI | FastAPI Backend | `POST /api/sessions/{id}/messages` `{ "message": "..." }` | `MessageResponse` JSON |
| 3 | FastAPI Backend | PostgreSQL | `SELECT snapshot, soft_ask_count FROM context_snapshots WHERE session_id = :id` | Snapshot JSONB + integer |
| 4 | FastAPI Orchestrator | Emergency Classifier | Raw message string | `ActionEnum.ESCALATE` or `None` |
| 5 | FastAPI Orchestrator | LLM Wrapper → Groq API | System prompt + user prompt (Context Extractor) | `ExtractorOutput` JSON |
| 6 | FastAPI Orchestrator | State Projector | `ExtractorOutput.delta_events` + existing snapshot | Updated snapshot JSONB |
| 7 | State Projector | PostgreSQL | `INSERT INTO clinical_events ...` + `UPSERT context_snapshots ...` | Transaction committed |
| 8 | FastAPI Orchestrator | LLM Wrapper → Groq API | System prompt + snapshot + message (Context Gate) | `ContextGateOutput` JSON |
| 9a | FastAPI Orchestrator (SOFT-ASK, count < 2) | LLM Wrapper → Groq API | SOFT-ASK synthesis prompt | `ResponseGeneratorOutput` JSON |
| 9b | FastAPI Orchestrator (SOFT-ASK, count ≥ 2) | Orchestrator state machine | Force-override to GENERALIZE | Continue to step 10 |
| 10 | FastAPI Orchestrator | Hybrid Retriever → Qdrant | Dense vector (384-dim) + sparse vector (BM25 tokens) | Top-20 `ScoredPoint[]` with payload |
| 11 | FastAPI Orchestrator | Cross-Encoder Reranker (threadpool) | 20 (query, chunk_text) pairs | Top-5 reranked `RetrievedChunk[]` |
| 12 | FastAPI Orchestrator | LLM Wrapper → Groq API | System prompt + evidence + snapshot (Evidence Gate) | `EvidenceGateOutput` JSON |
| 13a | FastAPI Orchestrator (ANSWER/GENERALIZE) | LLM Wrapper → Groq API | XML-isolated prompt (Response Generator) | `ResponseGeneratorOutput` JSON |
| 13b | FastAPI Orchestrator (ABSTAIN/ESCALATE) | Templates module | Action enum | Pre-vetted template string |
| 14 | FastAPI Orchestrator | PostgreSQL | `INSERT INTO audit_logs ...` + `INSERT INTO message_history ...` | Transaction committed |
| 15 | FastAPI Backend | Streamlit Chat UI | HTTP 200 `MessageResponse` JSON | Response rendered in chat panel + citations panel |

## A.2 Offline Interactions

| # | Request Source | Processing Component | Data Exchanged | Result Returned |
| :--- | :--- | :--- | :--- | :--- |
| O1 | System Admin (CLI) | Ingestion Worker | `python -m medbridge.ingestion --pdf-dir ./data/guidelines/` | Log output |
| O2 | Ingestion Worker | PyMuPDF | PDF file path | Extracted text + page numbers |
| O3 | Ingestion Worker | Chunker | Raw text + section headers | `GuidelineChunk[]` with metadata |
| O4 | Ingestion Worker | fastembed | Chunk text | Dense vector (384-dim) + sparse vector |
| O5 | Ingestion Worker | Qdrant | `PointStruct[]` with vectors + payload | Upsert confirmation |

---

# Appendix B: Deterministic Response Templates

These templates are returned **without LLM generation** for `ABSTAIN`, `ESCALATE`, and emergency fast-path scenarios.

## B.1 ESCALATE Template

```
⚠️ IMPORTANT: Based on what you've described, this situation may require
immediate medical attention. Please contact your healthcare provider,
visit your nearest emergency room, or call emergency services right away.

This tool provides informational guidance only and cannot assess or manage
medical emergencies.

If you are in the United States, call 911 for emergencies.
```

## B.2 ABSTAIN Template

```
I don't have sufficient information in my clinical guidelines to safely
address this specific question. This may be outside the scope of
hypertension management, or the topic may require specialized medical
expertise.

I recommend discussing this question directly with your healthcare provider,
who can give you personalized guidance based on your complete medical history.
```

## B.3 SOFT-ASK Loop-Breaker Template (count ≥ 2, forced GENERALIZE)

*Note: This template is used as a prefix before the LLM-generated GENERALIZE response.*

```
I understand you may not have all your medical details handy. Here is some
general guidance based on current hypertension guidelines that may be helpful:
```

---

# Appendix C: Project Directory Structure

```
medbridge/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── data/
│   └── guidelines/
│       ├── aha_acc_2025.pdf
│       ├── esc_esh_2024.pdf
│       └── medlineplus_hbp.pdf
├── medbridge/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── sessions.py
│   │   │   └── messages.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── requests.py
│   │   │   └── responses.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── error_handler.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── emergency_classifier.py
│   │   └── templates.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm_wrapper.py
│   │   ├── context_extractor.py
│   │   ├── context_gate.py
│   │   ├── evidence_gate.py
│   │   ├── response_generator.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── extractor.py
│   │       ├── context_gate.py
│   │       ├── evidence_gate.py
│   │       └── response_generator.py
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_retriever.py
│   │   ├── reranker.py
│   │   └── embedder.py
│   ├── state/
│   │   ├── __init__.py
│   │   ├── projector.py
│   │   └── session_manager.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── connection.py
│   │   └── migrations/
│   └── ingestion/
│       ├── __init__.py
│       ├── __main__.py
│       ├── parser.py
│       ├── chunker.py
│       └── indexer.py
├── frontend/
│   ├── app.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── citations.py
│   │   └── disclaimer.py
│   └── services/
│       ├── __init__.py
│       ├── api_client.py
│       └── session.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_emergency_classifier.py
    │   ├── test_state_projector.py
    │   ├── test_context_gate.py
    │   ├── test_evidence_gate.py
    │   ├── test_reranker.py
    │   └── test_llm_wrapper.py
    ├── integration/
    │   ├── test_pipeline_e2e.py
    │   ├── test_database.py
    │   └── test_retrieval.py
    └── evaluation/
        ├── benchmark_runner.py
        ├── rabbits_runner.py
        └── fixtures/
            └── medbridge_aq/
```
