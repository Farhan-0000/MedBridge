# MedBridge v3 — Development Backlog

> **Document Type:** Implementation-Ready Development Backlog & Task Breakdown  
> **Source Artifacts:** Revised Master Project Context, Revised Technical Specification, Revised Module Specifications  
> **Total Tasks:** 36 granular tasks across 8 execution phases  
> **Architecture Baseline:** Corrected Architecture (incorporating all 26 ADL decisions)  
> **Date:** 2026-08-16  

---

## Backlog Summary & Phase Roadmap

```mermaid
flowchart LR
    P1["Phase 1<br/>Project Foundation"] --> P2["Phase 2<br/>Core Infrastructure"]
    P2 --> P3["Phase 3<br/>Backend Services"]
    P3 --> P4["Phase 4<br/>AI/RAG Pipeline"]
    P4 --> P5["Phase 5<br/>Frontend Features"]
    P5 --> P6["Phase 6<br/>Integration"]
    P6 --> P7["Phase 7<br/>Testing & Validation"]
    P7 --> P8["Phase 8<br/>Deployment & Ops"]
```

| Phase | Focus Area | Task IDs | Task Count | Target Output |
| :--- | :--- | :---: | :---: | :--- |
| **Phase 1** | Project Foundation | TASK-01 – TASK-04 | 4 | Directory tree, configuration, environment setup, structured logging |
| **Phase 2** | Core Infrastructure | TASK-05 – TASK-10 | 6 | Docker Compose, Postgres connection, models, migrations, embedding models |
| **Phase 3** | Backend Services | TASK-11 – TASK-16 | 6 | Schemas, enums, State Projector, Session Manager, Emergency Classifier, Templates |
| **Phase 4** | AI/RAG Pipeline | TASK-17 – TASK-24 | 8 | Resilient LLM Wrapper, Extractor, Gates 1 & 2, Hybrid Retriever, Generator, Orchestrator, Ingestion CLI |
| **Phase 5** | Frontend Features | TASK-25 – TASK-27 | 3 | Streamlit API client, Session Manager, UI components, multi-turn chat UI |
| **Phase 6** | Integration | TASK-28 – TASK-30 | 3 | Error handling middleware, FastAPI routes, application entry point (`main.py`) |
| **Phase 7** | Testing & Validation | TASK-31 – TASK-33 | 3 | End-to-end integration tests, MedBridge-AQ benchmark suite, adversarial testing |
| **Phase 8** | Deployment | TASK-34 – TASK-36 | 3 | Guideline ingestion run, smoke testing, operational documentation & runbooks |

---

# Phase 1: Project Foundation

### TASK-01: Project Directory Structure & Environment Scaffolding
- **Module:** M-01 (Configuration) / Infrastructure
- **Description:** Initialize the complete project directory structure according to Appendix C of the Technical Specification. Configure `.gitignore`, `.env.example`, and Python package markers (`__init__.py`).
- **Dependencies:** None
- **Inputs:** Technical Specification Appendix C directory tree.
- **Outputs:** File tree in `medbridge/` with empty module files and `__init__.py` files.
- **Acceptance Criteria:**
  - Complete folder structure matching `medbridge/{api,core,state,ai,retrieval,db,ingestion,frontend,tests}` created.
  - `.gitignore` ignores `.env`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `data/`, `pgdata/`, `qdrant_data/`.
  - `.env.example` created with template variables for all configuration keys.
- **Testing Requirements:** Directory existence verification script.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `chore(setup): scaffold project directory structure and environment files`

---

### TASK-02: Configuration Management (`config.py`)
- **Module:** M-01 (Configuration)
- **Description:** Implement `Settings` class using `pydantic-settings` to load, validate, and provide typed access to all application settings from environment variables and `.env`.
- **Dependencies:** TASK-01
- **Inputs:** M-01 Module Specification, `.env.example`.
- **Outputs:** `medbridge/config.py` containing `Settings` class and `get_settings()` cached accessor.
- **Acceptance Criteria:**
  - All variables defined in M-01 (LLM, Database, Qdrant, Retrieval, Safety, Server) implemented with correct types and defaults.
  - `get_settings()` decorated with `@lru_cache()` to return a singleton.
  - Validates required fields (`GROQ_API_KEY`, `POSTGRES_PASSWORD`) on startup and fails fast if missing.
  - `CORS_ORIGINS` parsed properly as `list[str]`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_config.py`:
    - `test_defaults_applied`
    - `test_missing_required_raises`
    - `test_type_coercion`
    - `test_singleton_behavior`
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(config): implement pydantic-settings configuration manager`

---

### TASK-03: Dependency Management & Environment Lock
- **Module:** M-01 (Configuration) / Infrastructure
- **Description:** Create `requirements.txt` and `pyproject.toml` specifying all runtime, AI, database, retrieval, and testing dependencies with locked version constraints.
- **Dependencies:** TASK-01
- **Inputs:** Technical Specification Parts I–VI dependencies sections.
- **Outputs:** `requirements.txt`, `pyproject.toml`.
- **Acceptance Criteria:**
  - Includes: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]>=2.0`, `asyncpg`, `alembic`, `psycopg2-binary`, `qdrant-client>=1.9`, `fastembed>=0.3`, `sentence-transformers>=3.0`, `httpx>=0.27`, `streamlit>=1.35`, `pymupdf>=1.24`, `structlog`, `pytest`, `pytest-asyncio`.
  - Installs cleanly in a fresh Python 3.11 virtual environment without dependency conflicts.
- **Testing Requirements:** Automated install check in test environment.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `chore(deps): specify project dependencies and requirements`

---

### TASK-04: Structured Logging Configuration (`logging_config.py`)
- **Module:** M-01 (Configuration) / Infrastructure
- **Description:** Implement structured JSON logging using `structlog` for production and colored console logging for local development. Configure log formatters, timestamp formatting, and log-level filters.
- **Dependencies:** TASK-02, TASK-03
- **Inputs:** M-01 Configuration, Technical Specification Logging Requirements.
- **Outputs:** `medbridge/logging_config.py` with `configure_logging()` function.
- **Acceptance Criteria:**
  - Outputs structured JSON format with `timestamp`, `level`, `event`, and contextual metadata fields.
  - Binds request context (e.g. `session_id`, `call_name`) automatically to log entries.
  - Masks sensitive authorization headers and API keys from log payloads.
- **Testing Requirements:**
  - Unit test in `tests/unit/test_logging.py`: verify JSON log emission and context variable binding.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(logging): configure structlog structured json logging`

---

# Phase 2: Core Infrastructure

### TASK-05: Docker Compose Infrastructure Definition (`docker-compose.yml`)
- **Module:** M-02 (Database) / Deployment
- **Description:** Author the authoritative `docker-compose.yml` to orchestrate PostgreSQL 16 and Qdrant containers with healthchecks, persistent volumes, and loopback-only port bindings.
- **Dependencies:** TASK-01, TASK-02
- **Inputs:** Technical Specification Part VI §5 Docker Compose.
- **Outputs:** `docker-compose.yml`.
- **Acceptance Criteria:**
  - PostgreSQL 16 container bound to `127.0.0.1:5432` with healthcheck (`pg_isready -U medbridge_app -d medbridge`).
  - Qdrant container bound to `127.0.0.1:6333` and `127.0.0.1:6334` with HTTP healthcheck (`curl -sf http://localhost:6333/healthz`).
  - Restart policy set to `unless-stopped`.
  - Named persistent volumes `pgdata` and `qdrant_data` configured.
- **Testing Requirements:**
  - Integration smoke test: `docker compose up -d` brings both services to `healthy` status.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `infra(docker): add authoritative docker-compose for postgres and qdrant`

---

### TASK-06: Database Models Definition (`db/models.py`)
- **Module:** M-02 (Database Layer)
- **Description:** Define SQLAlchemy 2.0 async ORM declarative models for all 5 database entities: `Session`, `ClinicalEvent`, `ContextSnapshot`, `AuditLog`, `MessageHistory`.
- **Dependencies:** TASK-03
- **Inputs:** M-02 Module Specification §Internal Classes, Technical Specification Part IV §3.2.
- **Outputs:** `medbridge/db/models.py`.
- **Acceptance Criteria:**
  - All tables, columns, UUID primary keys, JSONB fields, ENUM types, and Foreign Key constraints accurately defined.
  - Bidirectional relationships and back-populates configured on `Session`.
  - Default JSONB factory set to empty dictionary/list where required.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_db_models.py`:
    - Verify table names, column mappings, and relationship properties.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(db): define sqlalchemy declarative orm models`

---

### TASK-07: Async Database Connection & Session Management (`db/connection.py`)
- **Module:** M-02 (Database Layer)
- **Description:** Implement async engine creation, connection pooling, session maker, and FastAPI dependency provider (`get_session`). Implement startup lifecycle initialization and shutdown hooks.
- **Dependencies:** TASK-02, TASK-06
- **Inputs:** M-02 Module Specification §Services, `medbridge/config.py`.
- **Outputs:** `medbridge/db/connection.py`.
- **Acceptance Criteria:**
  - `get_engine()` creates a singleton `AsyncEngine` with configured pool size.
  - `get_session()` yields an `AsyncSession` with automatic rollback on error.
  - `init_db()` executes `SELECT 1` to verify connectivity on application startup.
  - `close_db()` disposes the connection pool cleanly on shutdown.
- **Testing Requirements:**
  - Integration test in `tests/integration/test_db_connection.py`:
    - Connect to running Postgres, obtain session, execute basic query, disconnect.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(db): implement async connection pool and session lifecycle`

---

### TASK-08: Alembic Migrations & PostgreSQL Rules (`alembic/`)
- **Module:** M-02 (Database Layer)
- **Description:** Configure Alembic for async migrations (`env.py`, `alembic.ini`) and generate baseline migration script including table DDL, indexes, and PostgreSQL append-only rules for `clinical_events` and `audit_logs`.
- **Dependencies:** TASK-05, TASK-06, TASK-07
- **Inputs:** Technical Specification Part IV §3.2 SQL DDL.
- **Outputs:** `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`.
- **Acceptance Criteria:**
  - `uuid-ossp` extension enabled.
  - PostgreSQL rules `no_update_events`, `no_delete_events`, `no_update_audit`, `no_delete_audit` created.
  - `alembic upgrade head` applies cleanly on empty database.
  - `alembic downgrade base` rolls back all tables and types cleanly.
- **Testing Requirements:**
  - Integration tests in `tests/integration/test_migrations.py`:
    - Run up/down migrations.
    - Test that `UPDATE` and `DELETE` on `clinical_events` and `audit_logs` are rejected or no-ops.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(db): configure alembic and initial schema migration with immutability rules`

---

### TASK-09: FastEmbed Embedding Client (`retrieval/embedder.py`)
- **Module:** M-15 (Embedding Client)
- **Description:** Implement `EmbeddingClient` providing a unified interface for dense (`bge-small-en-v1.5`) and sparse (`Qdrant/bm25`) embedding generation using `fastembed`.
- **Dependencies:** TASK-02, TASK-03
- **Inputs:** M-15 Module Specification.
- **Outputs:** `medbridge/retrieval/embedder.py`.
- **Acceptance Criteria:**
  - `embed_dense(text)` returns 384-dimensional `list[float]`.
  - `embed_sparse(text)` returns sparse indices and values.
  - Supports batch processing methods `embed_dense_batch` and `embed_sparse_batch`.
  - Thread-safe model caching and initialization on first use.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_embedder.py`:
    - `test_dense_dimension_384`
    - `test_sparse_indices_values`
    - `test_batch_consistency`
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(retrieval): implement dense and sparse embedding client with fastembed`

---

### TASK-10: Cross-Encoder Reranker Service (`retrieval/reranker.py`)
- **Module:** M-17 (Cross-Encoder Reranker)
- **Description:** Implement `CrossEncoderReranker` using `ms-marco-MiniLM-L-6-v2`. Offload CPU-bound inference to `asyncio.to_thread()` to prevent event loop blocking (ADL-020).
- **Dependencies:** TASK-02, TASK-03
- **Inputs:** M-17 Module Specification, Technical Specification Part III §3.6.
- **Outputs:** `medbridge/retrieval/reranker.py`.
- **Acceptance Criteria:**
  - `rerank(query, chunks, top_k=5)` scores pairs and returns top-5 sorted by score descending.
  - Computation executed via `asyncio.to_thread(_sync_rerank)` without blocking event loop.
  - Handles empty chunks list and `k > len(chunks)` gracefully.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_reranker.py`:
    - `test_rerank_output_count`
    - `test_score_sorting_descending`
    - `test_empty_chunks_handling`
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(retrieval): implement threadpool-offloaded cross-encoder reranker`

---

# Phase 3: Backend Services & State Management

### TASK-11: Core Enumerations & Shared Types (`api/schemas/enums.py`)
- **Module:** M-03 (API Schemas & Middleware)
- **Description:** Define `ActionEnum` (`SOFT-ASK`, `ANSWER`, `GENERALIZE`, `ABSTAIN`, `ESCALATE`) and `EventTypeEnum` (`BP_READING`, `MEDICATION_ADDED`, `MEDICATION_STOPPED`, `SYMPTOM_REPORTED`, `DEMOGRAPHIC`, `LAB_RESULT`).
- **Dependencies:** TASK-01
- **Inputs:** M-03 Module Specification §Internal Classes.
- **Outputs:** `medbridge/api/schemas/enums.py`.
- **Acceptance Criteria:**
  - Inherits from `str, Enum` (or `StrEnum`).
  - Values match exact casing specified in architecture decisions (ADL-008).
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_enums.py`: verify all enum members and string representations.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(api): define core action and event type enums`

---

### TASK-12: API Request & Response Pydantic Models (`api/schemas/`)
- **Module:** M-03 (API Schemas & Middleware)
- **Description:** Define all request/response Pydantic models: `MessageRequest`, `MessageResponse`, `CitationResponse`, `SessionResponse`, `HistoryResponse`, `ErrorResponse`, `HealthResponse`.
- **Dependencies:** TASK-11
- **Inputs:** M-03 Module Specification, Technical Specification Part II §5.1.
- **Outputs:** `medbridge/api/schemas/requests.py`, `medbridge/api/schemas/responses.py`.
- **Acceptance Criteria:**
  - `MessageRequest.message` enforced with `min_length=1`, `max_length=2000`.
  - `CitationResponse` contains `marker`, `chunk_id`, `source`, `section`, `excerpt`.
  - All schemas serialize/deserialize cleanly with proper JSON schema validation.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_schemas.py`:
    - Test validation boundaries (empty string, 2000 chars, 2001 chars).
    - Test JSON serialization format.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(api): implement pydantic request and response schemas`

---

### TASK-13: Deterministic State Projector (`state/projector.py`)
- **Module:** M-06 (State Projector)
- **Description:** Implement pure Python deterministic state projection logic that applies delta events to the context snapshot and persists events/snapshot to PostgreSQL in a single transaction (ADL-001).
- **Dependencies:** TASK-06, TASK-07, TASK-11
- **Inputs:** M-06 Module Specification, Technical Specification Part IV §3.3.
- **Outputs:** `medbridge/state/projector.py`.
- **Acceptance Criteria:**
  - Implements all 6 projection rules:
    - `BP_READING`: Appends reading; keeps last 5.
    - `MEDICATION_ADDED`: Deduplicates by drug name (case-insensitive); adds medication.
    - `MEDICATION_STOPPED`: Removes from current; appends to discontinued with reason.
    - `SYMPTOM_REPORTED`: Deduplicates and appends symptom.
    - `DEMOGRAPHIC`: Merges and overwrites demographic fields.
    - `LAB_RESULT`: Appends lab; keeps last 3 per lab type.
  - `persist_and_project()` executes event insertion and snapshot upsert within a single DB transaction.
  - `reconstruct_from_events()` re-creates snapshot identically from scratch for validation.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_projector.py`:
    - Test all 6 event projection rules individually.
    - Test 5-item BP truncation and 3-item lab truncation.
    - Test `reconstruct_from_events` matches `apply_events`.
  - Integration tests in `tests/integration/test_projector_db.py`:
    - Test transactional atomic persistence to Postgres.
- **Estimated Complexity:** Medium (3 SP)
- **Suggested Commit Scope:** `feat(state): implement deterministic state projector and event persistence`

---

### TASK-14: Database Session Manager (`state/session_manager.py`)
- **Module:** M-05 (Session Manager)
- **Description:** Implement session CRUD operations, session state loading (snapshot + `soft_ask_count`), message history logging, and loop-breaker counter management (ADL-014).
- **Dependencies:** TASK-06, TASK-07, TASK-12
- **Inputs:** M-05 Module Specification, Technical Specification Part IV §4.
- **Outputs:** `medbridge/state/session_manager.py`.
- **Acceptance Criteria:**
  - `create_session(db)` generates and returns new session UUID.
  - `load_session_state(db, session_id)` retrieves snapshot and `soft_ask_count`; raises `SessionNotFoundError` if missing.
  - `save_message(db, ...)` appends message to `message_history`.
  - `increment_soft_ask_count(db, session_id)` and `reset_soft_ask_count(db, session_id)` update counter accurately.
  - `get_message_history(db, session_id)` returns chronological message list.
- **Testing Requirements:**
  - Integration tests in `tests/integration/test_session_manager.py`:
    - Test session creation, loading, counter increment/reset, message history ordering.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(state): implement session manager for session lifecycle and history`

---

### TASK-15: Deterministic Emergency Classifier (`core/emergency_classifier.py`)
- **Module:** M-07 (Emergency Classifier)
- **Description:** Implement the regex-based sub-5ms triage classifier that detects hypertensive crises, red-flag symptoms, and acute danger in raw messages before any LLM invocation (ADL-002).
- **Dependencies:** TASK-11
- **Inputs:** M-07 Module Specification, Technical Specification Part III §3.2.
- **Outputs:** `medbridge/core/emergency_classifier.py`.
- **Acceptance Criteria:**
  - Compiles patterns at import time for:
    - Hypertensive crisis: BP systolic $\ge 180$ or diastolic $\ge 120$.
    - Symptoms: chest pain, difficulty breathing, sudden severe headache, vision changes, numbness/slurred speech, fainting/seizure, blood in urine/stool, self-harm.
  - `classify(message)` returns `ActionEnum.ESCALATE` on match, or `None` if safe.
  - Execution latency verified under 5ms.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_emergency_classifier.py`:
    - True positive test suite (crisis BP values, symptom keywords).
    - True negative test suite (routine BP values, general medication questions).
    - Case insensitivity and whitespace variation tests.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(core): implement deterministic regex emergency classifier`

---

### TASK-16: Deterministic Response Templates (`core/templates.py`)
- **Module:** M-09 (Response Templates)
- **Description:** Implement pre-vetted, immutable response templates for `ESCALATE` and `ABSTAIN` actions, as well as the `SOFT-ASK` loop-breaker prefix (ADL-015).
- **Dependencies:** TASK-11
- **Inputs:** M-09 Module Specification, Technical Specification Appendix B.
- **Outputs:** `medbridge/core/templates.py`.
- **Acceptance Criteria:**
  - `get_template(ActionEnum.ESCALATE)` returns crisis hotline/emergency referral text.
  - `get_template(ActionEnum.ABSTAIN)` returns primary care physician referral text.
  - `get_loop_breaker_prefix()` returns standard non-blocking conversational transition.
  - Templates contain no hallucinated clinical claims or dynamic placeholders.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_templates.py`: verify non-empty strings and proper exceptions on invalid actions.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(core): define pre-vetted deterministic response templates`

---

# Phase 4: AI/RAG Pipeline

### TASK-17: Resilient LLM Wrapper (`ai/llm_wrapper.py`)
- **Module:** M-10 (Resilient LLM Wrapper)
- **Description:** Implement `ResilientLLMWrapper` providing retry logic with exponential backoff, JSON extraction and repair, Pydantic schema validation, and fallback provider failover (ADL-004).
- **Dependencies:** TASK-02, TASK-04, TASK-12
- **Inputs:** M-10 Module Specification, Technical Specification Part III §3.9.
- **Outputs:** `medbridge/ai/llm_wrapper.py`.
- **Acceptance Criteria:**
  - Executes async HTTP requests to Groq Cloud API (with optional OpenAI failover).
  - Automatically parses markdown code blocks (` ```json `) to raw JSON.
  - Repaires common malformed JSON (trailing commas, unclosed brackets).
  - Retries up to 3 times on parse or timeout errors with exponential backoff.
  - Returns validated Pydantic model instance or `None` on permanent failure.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_llm_wrapper.py`:
    - Mocked valid JSON response parsing.
    - JSON repair on malformed strings.
    - Retry on timeout / 5xx errors.
    - Graceful return of `None` after 3 failed attempts.
- **Estimated Complexity:** High (3 SP)
- **Suggested Commit Scope:** `feat(ai): implement resilient llm wrapper with retry and json repair`

---

### TASK-18: Context Extractor — LLM Call 1 (`ai/context_extractor.py`)
- **Module:** M-11 (Context Extractor)
- **Description:** Implement LLM Call 1 to extract structured delta events, reformulate clinical search query, and capture raw patient intent from incoming messages using XML-wrapped inputs (ADL-018, ADL-023).
- **Dependencies:** TASK-11, TASK-17
- **Inputs:** M-11 Module Specification, Technical Specification Part III §3.3.
- **Outputs:** `medbridge/ai/context_extractor.py`, `medbridge/ai/schemas/extractor.py`.
- **Acceptance Criteria:**
  - System prompt instructs JSON-only structured fact extraction.
  - User message is strictly encapsulated within `<untrusted_user_input>` tags.
  - Outputs `ExtractorOutput` Pydantic model (`delta_events`, `search_query`, `raw_intent`).
  - Uses temperature `0.0` and seed `42` for determinism.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_context_extractor.py`:
    - Verify prompt formatting and XML tag isolation.
    - Test schema parsing of extracted medical events.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(ai): implement context extractor for delta events and search query`

---

### TASK-19: Context Gate — LLM Call 2 (`ai/context_gate.py`)
- **Module:** M-12 (Context Gate)
- **Description:** Implement LLM Call 2 to perform binary classification (`SOFT-ASK` vs `PROCEED`) based on whether accumulated context is clinically sufficient for personalized guidance (ADL-023).
- **Dependencies:** TASK-11, TASK-17
- **Inputs:** M-12 Module Specification, Technical Specification Part III §3.4.
- **Outputs:** `medbridge/ai/context_gate.py`, `medbridge/ai/schemas/context_gate.py`.
- **Acceptance Criteria:**
  - Pure classification prompt evaluating snapshot vs question intent.
  - Outputs `ContextGateOutput` (`action`: `SOFT-ASK` | `PROCEED`, `missing_fields`, `rationale`).
  - Evaluates with temperature `0.0` and seed `42`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_context_gate.py`:
    - Mocked prompt evaluations for sufficient vs missing clinical parameters.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(ai): implement context gate binary sufficiency classifier`

---

### TASK-20: Qdrant Hybrid Retriever (`retrieval/hybrid_retriever.py`)
- **Module:** M-16 (Hybrid Retriever)
- **Description:** Implement hybrid retrieval against Qdrant combining dense embeddings (`bge-small-en-v1.5`) and sparse BM25 vectors using Reciprocal Rank Fusion (RRF, $k=60$) to retrieve Top-20 candidates (ADL-022).
- **Dependencies:** TASK-02, TASK-09
- **Inputs:** M-16 Module Specification, Technical Specification Part III §3.5.
- **Outputs:** `medbridge/retrieval/hybrid_retriever.py`.
- **Acceptance Criteria:**
  - Generates query dense and sparse vectors via `EmbeddingClient`.
  - Executes Qdrant `query_points` with dense/sparse prefetch and `models.Fusion.RRF`.
  - Maps results to `list[RetrievedChunk]` with all metadata (`guideline_id`, `section_title`, `page_number`, `source_url`, `chunk_text`).
  - Returns empty list gracefully on connection failure or empty collection.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_hybrid_retriever.py`: mock Qdrant client responses and score mapping.
  - Integration tests in `tests/integration/test_hybrid_retriever_qdrant.py`: verify real hybrid search against test Qdrant collection.
- **Estimated Complexity:** Medium (3 SP)
- **Suggested Commit Scope:** `feat(retrieval): implement hybrid dense-sparse retriever with rrf fusion`

---

### TASK-21: Evidence Gate — LLM Call 3 (`ai/evidence_gate.py`)
- **Module:** M-13 (Evidence Gate)
- **Description:** Implement LLM Call 3 to evaluate whether retrieved Top-5 guideline chunks provide sufficient evidence to answer the query, classifying into `ANSWER`, `GENERALIZE`, `ABSTAIN`, or `ESCALATE` (ADL-024).
- **Dependencies:** TASK-11, TASK-17
- **Inputs:** M-13 Module Specification, Technical Specification Part III §3.7.
- **Outputs:** `medbridge/ai/evidence_gate.py`, `medbridge/ai/schemas/evidence_gate.py`.
- **Acceptance Criteria:**
  - Evaluates snapshot, patient query, and formatted Top-5 chunks.
  - Outputs `EvidenceGateOutput` (`action`, `evidence_sufficient`, `rationale`).
  - Uses temperature `0.0` and seed `42`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_evidence_gate.py`: verify routing decision classification across standard vignettes.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(ai): implement evidence gate 4-way routing evaluator`

---

### TASK-22: Response Generator — LLM Call 4 (`ai/response_generator.py`)
- **Module:** M-14 (Response Generator)
- **Description:** Implement LLM Call 4 to generate evidence-grounded clinical responses with inline numeric citation markers (`[1]`, `[2]`) using strict XML-isolated prompt boundaries (ADL-018, ADL-025).
- **Dependencies:** TASK-11, TASK-17
- **Inputs:** M-14 Module Specification, Technical Specification Part III §3.8.
- **Outputs:** `medbridge/ai/response_generator.py`, `medbridge/ai/schemas/response_generator.py`.
- **Acceptance Criteria:**
  - Prompt structured with XML tags: `<system_instructions>`, `<patient_context>`, `<clinical_evidence>`, `<user_query>`.
  - Only invoked for `ANSWER`, `GENERALIZE`, and `SOFT-ASK` actions (bypassed for `ABSTAIN`/`ESCALATE`).
  - Generates `ResponseGeneratorOutput` (`response_text`, `citations`).
  - Uses temperature `0.3` for natural fluency.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_response_generator.py`: verify XML prompt construction and citation parsing.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(ai): implement response generator with xml prompt isolation and citations`

---

### TASK-23: Pipeline Orchestrator (`core/orchestrator.py`)
- **Module:** M-08 (Pipeline Orchestrator)
- **Description:** Implement the complete 8-stage pipeline orchestrator coordinating emergency check, context extraction, state projection, Context Gate state machine, retrieval, reranking, Evidence Gate routing, generation, and audit logging.
- **Dependencies:** TASK-13, TASK-14, TASK-15, TASK-16, TASK-18, TASK-19, TASK-20, TASK-10, TASK-21, TASK-22
- **Inputs:** M-08 Module Specification, Technical Specification Part III §3.1.
- **Outputs:** `medbridge/core/orchestrator.py`.
- **Acceptance Criteria:**
  - Implements the complete runtime sequence:
    1. Load session state from DB.
    2. Fast-path emergency check $\to$ return `ESCALATE` template if matched.
    3. Run Extractor $\to$ update DB event log and snapshot via State Projector.
    4. Run Context Gate:
       - If `SOFT-ASK` and count $< 2$: increment count, generate clarifying question.
       - If `SOFT-ASK` and count $\ge 2$: force `GENERALIZE` (loop-breaker).
       - If `PROCEED`: reset count to 0.
    5. Run Hybrid Retrieval $\to$ Cross-Encoder Reranker.
    6. Run Evidence Gate:
       - If `ABSTAIN` or `ESCALATE`: return deterministic template.
       - If `ANSWER` or `GENERALIZE`: invoke Response Generator.
    7. Atomically log audit record to `audit_logs` and messages to `message_history`.
  - **Guaranteed non-throwing execution**: all fallback paths resolve to a valid `MessageResponse`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_orchestrator.py`:
    - Test all 5 routing paths with mocked LLM calls.
    - Test loop-breaker threshold trigger (`soft_ask_count >= 2`).
    - Test emergency fast-path bypass.
    - Test fallback behaviors on individual LLM call failures.
- **Estimated Complexity:** High (4 SP)
- **Suggested Commit Scope:** `feat(core): implement central pipeline orchestrator and state machine`

---

### TASK-24: Knowledge Ingestion CLI Pipeline (`ingestion/`)
- **Module:** M-18 (Ingestion Pipeline)
- **Description:** Implement offline CLI tool to parse clinical guideline PDFs, split text into section-aware chunks (512 tokens, 64 overlap), compute dense and sparse vectors, validate schemas, and upsert to Qdrant (ADL-003).
- **Dependencies:** TASK-02, TASK-09, TASK-20
- **Inputs:** M-18 Module Specification, Technical Specification Part V §3.2–3.4.
- **Outputs:** `medbridge/ingestion/{__main__.py, parser.py, chunker.py, indexer.py}`.
- **Acceptance Criteria:**
  - `parser.py` extracts text and page numbers from PDFs using PyMuPDF.
  - `chunker.py` performs section-aware chunking preserving guideline headers and token limits.
  - `indexer.py` validates payload schema and performs batch upsert to Qdrant.
  - CLI supports `--pdf-dir`, `--qdrant-url`, `--collection`, `--chunk-size`, `--chunk-overlap`, `--recreate`, `--dry-run`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_ingestion.py`:
    - Test chunking token limits and overlap.
    - Test chunk validation logic.
    - Test `--dry-run` flag bypasses database writes.
- **Estimated Complexity:** Medium (3 SP)
- **Suggested Commit Scope:** `feat(ingestion): implement section-aware pdf ingestion and indexing pipeline`

---

# Phase 5: Frontend Features

### TASK-25: Frontend API Client & State Service (`frontend/services/`)
- **Module:** M-20 (Streamlit Frontend)
- **Description:** Implement `APIClient` for asynchronous/synchronous communication with FastAPI backend and `SessionManager` for managing Streamlit session state and URL query parameters.
- **Dependencies:** TASK-12
- **Inputs:** M-20 Module Specification §Internal Classes.
- **Outputs:** `medbridge/frontend/services/api_client.py`, `medbridge/frontend/services/session.py`.
- **Acceptance Criteria:**
  - `APIClient` implements `create_session()`, `send_message()`, `get_history()`, `health_check()` using `httpx`.
  - Handles network timeouts and backend connection errors gracefully.
  - `SessionManager` reads/writes `session_id` to `st.session_state` and syncs with `st.query_params`.
- **Testing Requirements:**
  - Unit tests in `tests/unit/test_frontend_services.py`: mock API responses and verify session handling.
- **Estimated Complexity:** Low (2 SP)
- **Suggested Commit Scope:** `feat(frontend): implement backend api client and session state manager`

---

### TASK-26: UI Components — Disclaimer, Badges & Citations (`frontend/components/`)
- **Module:** M-20 (Streamlit Frontend)
- **Description:** Implement modular Streamlit UI presentation components for the medical disclaimer, colored routing action badges, collapsible citations expander, and sidebar.
- **Dependencies:** TASK-11, TASK-12
- **Inputs:** M-20 Module Specification §Functions, Technical Specification Part I §3.3.
- **Outputs:** `medbridge/frontend/components/{disclaimer.py, chat.py, citations.py, sidebar.py}`.
- **Acceptance Criteria:**
  - `render_disclaimer()` renders persistent disclaimer banner at top of UI.
  - `render_action_badge(action)` renders styled badge (e.g. green for `ANSWER`, red for `ESCALATE`, amber for `SOFT-ASK`).
  - `render_citations_panel(citations)` renders collapsible accordion with source guideline, section, and excerpt.
  - `render_sidebar()` displays session UUID and "New Chat" button.
- **Testing Requirements:**
  - Component rendering unit tests with mocked Streamlit contexts.
- **Estimated Complexity:** Low (2 SP)
- **Suggested Commit Scope:** `feat(frontend): implement disclaimer, badge, and citation panel components`

---

### TASK-27: Chat Interface & Streamlit Main Page (`frontend/app.py`)
- **Module:** M-20 (Streamlit Frontend)
- **Description:** Assemble the multi-turn conversational chat interface in `frontend/app.py`, connecting session initialization, message input, spinner feedback, response rendering, and citation display.
- **Dependencies:** TASK-25, TASK-26
- **Inputs:** M-20 Module Specification, Technical Specification Part I §3.2.
- **Outputs:** `medbridge/frontend/app.py`.
- **Acceptance Criteria:**
  - Initializes session UUID on first visit and persists across refreshes.
  - Renders complete chat history from state/backend.
  - Displays conversational input box with max character validation.
  - Shows spinner during API processing.
  - Displays assistant responses with action badge and associated citation expander.
- **Testing Requirements:**
  - Manual UI verification: run `streamlit run medbridge/frontend/app.py`.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(frontend): assemble streamlit chat interface and application layout`

---

# Phase 6: Integration & API Exposure

### TASK-28: Global Exception Handlers & Middleware (`api/middleware/`)
- **Module:** M-03 (API Schemas & Middleware)
- **Description:** Implement global error handling middleware in FastAPI that catches all unhandled exceptions, logs them with stack traces server-side, and guarantees a safe fallback JSON response to clients (never raw 500).
- **Dependencies:** TASK-04, TASK-12
- **Inputs:** M-03 Module Specification §Services, Technical Specification Part II §9.
- **Outputs:** `medbridge/api/middleware/error_handler.py`.
- **Acceptance Criteria:**
  - Unhandled exceptions return HTTP 500 with `ErrorResponse` containing safe clinical fallback message.
  - `SessionNotFoundError` returns HTTP 404 with structured `ErrorResponse`.
  - Request validation errors return HTTP 422 with field-level details.
  - Server stack traces are never leaked in client responses.
- **Testing Requirements:**
  - Unit/Integration tests in `tests/unit/test_error_handler.py`:
    - Verify 500 handler returns `ErrorResponse`.
    - Verify 404 handler returns `SESSION_NOT_FOUND`.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(api): implement global error handling middleware with safe fallback`

---

### TASK-29: FastAPI REST Route Handlers (`api/routes/`)
- **Module:** M-04 (API Routes)
- **Description:** Implement API route handlers for session creation, message processing, conversation history retrieval, and system health checks.
- **Dependencies:** TASK-07, TASK-12, TASK-14, TASK-23
- **Inputs:** M-04 Module Specification, Technical Specification Part II §4.
- **Outputs:** `medbridge/api/routes/sessions.py`, `medbridge/api/routes/messages.py`.
- **Acceptance Criteria:**
  - `POST /api/sessions`: Creates session and returns UUID (HTTP 201).
  - `POST /api/sessions/{session_id}/messages`: Invokes orchestrator and returns `MessageResponse` (HTTP 200).
  - `GET /api/sessions/{session_id}/history`: Returns `HistoryResponse` with all messages (HTTP 200).
  - `GET /health`: Verifies DB and Qdrant connectivity; returns `HealthResponse` (HTTP 200/503).
- **Testing Requirements:**
  - Integration tests in `tests/integration/test_routes.py`:
    - Test all 4 endpoints with mocked/live database.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `feat(api): implement fastapi rest routes for sessions, messages, and health`

---

### TASK-30: Application Lifespan & Entry Point (`main.py`)
- **Module:** M-19 (Application Entry Point)
- **Description:** Assemble the primary FastAPI application in `medbridge/main.py`. Register lifespan startup/shutdown handlers (DB pool, LLM wrapper, Embedder), attach CORS middleware, register error handlers, and mount API routers.
- **Dependencies:** TASK-07, TASK-09, TASK-17, TASK-28, TASK-29
- **Inputs:** M-19 Module Specification, Technical Specification Part II §3.
- **Outputs:** `medbridge/main.py`.
- **Acceptance Criteria:**
  - Startup lifespan initializes DB connection pool and preloads embedding models.
  - Shutdown lifespan closes DB pool and HTTP client connections.
  - CORS middleware configured with origins from `Settings.CORS_ORIGINS`.
  - All routers mounted under `/api` prefix.
- **Testing Requirements:**
  - Integration tests in `tests/integration/test_main_app.py`:
    - Test app startup/shutdown lifecycle.
    - Test CORS headers on test requests.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `feat(api): assemble main fastapi application with lifespan and cors`

---

# Phase 7: Testing & Validation

### TASK-31: End-to-End Pipeline Integration Tests
- **Module:** Testing & Validation
- **Description:** Implement comprehensive end-to-end integration test suite verifying full multi-turn conversational flows against live PostgreSQL and Qdrant instances with mocked LLM responses.
- **Dependencies:** TASK-23, TASK-29, TASK-30
- **Inputs:** Technical Specification Appendix A Interaction Catalog.
- **Outputs:** `tests/integration/test_e2e_pipeline.py`.
- **Acceptance Criteria:**
  - Validates full round-trip: Session creation $\to$ Message 1 (context accumulation) $\to$ Message 2 (SOFT-ASK) $\to$ Message 3 (ANSWER with citations) $\to$ Audit log verification.
  - Validates loop-breaker transition when SOFT-ASK count reaches 2.
  - Validates emergency fast-path triggers within $<10$ms.
- **Testing Requirements:** Pytest test suite execution with coverage report $>85\%$.
- **Estimated Complexity:** High (3 SP)
- **Suggested Commit Scope:** `test(integration): add end-to-end multi-turn pipeline test suite`

---

### TASK-32: MedBridge-AQ Clinical Vignette Benchmark Harness
- **Module:** Testing & Validation / AI Evaluation
- **Description:** Implement the MedBridge-AQ benchmark evaluation runner to execute 200+ clinical hypertension vignettes across 6 test subsets and compute routing accuracy, citation precision, and safety metrics.
- **Dependencies:** TASK-23
- **Inputs:** Master Project Context §AI Evaluation & Safety Benchmarks.
- **Outputs:** `tests/benchmark/benchmark_runner.py`, `tests/benchmark/vignettes/`.
- **Acceptance Criteria:**
  - Automated runner evaluates:
    - Routing accuracy across actions ($\ge 90\%$).
    - Citation precision ($\ge 90\%$).
    - Emergency detection recall ($100\%$).
    - Hallucination rate on out-of-domain queries ($0\%$).
  - Outputs a structured markdown evaluation summary report.
- **Testing Requirements:** Test runner execution on sample evaluation subset.
- **Estimated Complexity:** High (3 SP)
- **Suggested Commit Scope:** `test(benchmark): implement medbridge-aq clinical benchmark evaluation harness`

---

### TASK-33: Adversarial Robustness & Security Validation
- **Module:** Testing & Validation / Security
- **Description:** Implement adversarial test suite evaluating prompt injection resilience (via XML tag isolation), brand-generic drug name substitution (RABBITS benchmark), and SQL injection attempts.
- **Dependencies:** TASK-23, TASK-28
- **Inputs:** Master Project Context §Adversarial Evaluation, Module Specs §Security.
- **Outputs:** `tests/adversarial/test_security_adversarial.py`.
- **Acceptance Criteria:**
  - Injected prompts attempting system prompt leakage or safety bypass fail to alter routing.
  - Drug brand name variations (e.g. Norvasc $\leftrightarrow$ Amlodipine) resolve to identical clinical guidance.
  - Malicious SQL inputs in user messages produce no syntax or security errors.
- **Testing Requirements:** Automated execution of adversarial test suite.
- **Estimated Complexity:** Medium (2 SP)
- **Suggested Commit Scope:** `test(security): add adversarial prompt injection and brand-substitution tests`

---

# Phase 8: Deployment & Operational Readiness

### TASK-34: Guideline Ingestion & Collection Indexing Execution
- **Module:** M-18 (Ingestion Pipeline) / Operations
- **Description:** Execute the knowledge ingestion pipeline on official clinical guideline source PDFs (AHA/ACC 2025, ESC/ESH 2024, MedlinePlus) to populate the production `clinical_guidelines` Qdrant collection.
- **Dependencies:** TASK-05, TASK-24
- **Inputs:** Source PDFs in `data/guidelines/`.
- **Outputs:** Populated Qdrant vector database collection.
- **Acceptance Criteria:**
  - Collection created with 384-dim dense and BM25 sparse vector configurations.
  - All guideline documents indexed without chunk validation errors.
  - Verification query confirms non-empty top-K search results across key clinical topics.
- **Testing Requirements:** Run ingestion CLI with `--dry-run` followed by live ingestion and point count verification.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `chore(ingestion): index clinical guideline knowledge base in qdrant`

---

### TASK-35: End-to-End System Smoke Test & Health Verification
- **Module:** Operations & Deployment
- **Description:** Perform full-stack operational verification starting containers, applying database migrations, starting backend Uvicorn server, and launching Streamlit frontend.
- **Dependencies:** TASK-05, TASK-08, TASK-30, TASK-27, TASK-34
- **Inputs:** Technical Specification Part VI §6 Startup Sequence.
- **Outputs:** Verification test log and healthy running application.
- **Acceptance Criteria:**
  - `GET http://localhost:8000/health` returns `status: "healthy"` with both Postgres and Qdrant connected.
  - Streamlit UI accessible at `http://localhost:8501`.
  - Submitting sample question produces valid response with inline citations and action badge.
- **Testing Requirements:** Smoke test execution checklist.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `chore(release): verify full-stack startup sequence and system health`

---

### TASK-36: Documentation, Runbooks & Developer Guide (`README.md`)
- **Module:** Operations & Documentation
- **Description:** Produce the comprehensive project `README.md` and developer runbook detailing prerequisites, environment setup, local execution steps, Docker management, testing commands, and architecture overview.
- **Dependencies:** TASK-35
- **Inputs:** Master Project Context, Technical Specification.
- **Outputs:** `README.md`.
- **Acceptance Criteria:**
  - Step-by-step setup guide from clone to running frontend/backend.
  - Clear explanations of environment variables and configuration.
  - Commands for running unit, integration, benchmark, and adversarial test suites.
  - Troubleshooting guide for database, vector store, and LLM API issues.
- **Testing Requirements:** Manual review of markdown documentation.
- **Estimated Complexity:** Low (1 SP)
- **Suggested Commit Scope:** `docs: add comprehensive readme, startup runbook, and developer guide`

---

## Complete Dependency Matrix

| Task ID | Task Name | Strict Pre-requisites (Dependencies) |
| :--- | :--- | :--- |
| **TASK-01** | Directory Structure & Scaffolding | *None* |
| **TASK-02** | Configuration Management (`config.py`) | TASK-01 |
| **TASK-03** | Dependency Management (`requirements.txt`) | TASK-01 |
| **TASK-04** | Structured Logging (`logging_config.py`) | TASK-02, TASK-03 |
| **TASK-05** | Docker Compose Definition | TASK-01, TASK-02 |
| **TASK-06** | Database Models (`db/models.py`) | TASK-03 |
| **TASK-07** | Database Connection (`db/connection.py`) | TASK-02, TASK-06 |
| **TASK-08** | Alembic Migrations & Rules | TASK-05, TASK-06, TASK-07 |
| **TASK-09** | FastEmbed Embedding Client | TASK-02, TASK-03 |
| **TASK-10** | Cross-Encoder Reranker Service | TASK-02, TASK-03 |
| **TASK-11** | Core Enumerations (`enums.py`) | TASK-01 |
| **TASK-12** | API Pydantic Models (`schemas/`) | TASK-11 |
| **TASK-13** | Deterministic State Projector | TASK-06, TASK-07, TASK-11 |
| **TASK-14** | Database Session Manager | TASK-06, TASK-07, TASK-12 |
| **TASK-15** | Emergency Classifier (`classifier.py`) | TASK-11 |
| **TASK-16** | Deterministic Response Templates | TASK-11 |
| **TASK-17** | Resilient LLM Wrapper | TASK-02, TASK-04, TASK-12 |
| **TASK-18** | Context Extractor (LLM Call 1) | TASK-11, TASK-17 |
| **TASK-19** | Context Gate (LLM Call 2) | TASK-11, TASK-17 |
| **TASK-20** | Qdrant Hybrid Retriever | TASK-02, TASK-09 |
| **TASK-21** | Evidence Gate (LLM Call 3) | TASK-11, TASK-17 |
| **TASK-22** | Response Generator (LLM Call 4) | TASK-11, TASK-17 |
| **TASK-23** | Pipeline Orchestrator | TASK-13, TASK-14, TASK-15, TASK-16, TASK-18, TASK-19, TASK-20, TASK-10, TASK-21, TASK-22 |
| **TASK-24** | Knowledge Ingestion CLI Pipeline | TASK-02, TASK-09, TASK-20 |
| **TASK-25** | Frontend API Client & State Service | TASK-12 |
| **TASK-26** | Frontend UI Components | TASK-11, TASK-12 |
| **TASK-27** | Streamlit Chat Interface (`app.py`) | TASK-25, TASK-26 |
| **TASK-28** | Exception Middleware & Error Handling | TASK-04, TASK-12 |
| **TASK-29** | FastAPI REST Route Handlers | TASK-07, TASK-12, TASK-14, TASK-23 |
| **TASK-30** | Application Entry Point (`main.py`) | TASK-07, TASK-09, TASK-17, TASK-28, TASK-29 |
| **TASK-31** | End-to-End Integration Tests | TASK-23, TASK-29, TASK-30 |
| **TASK-32** | MedBridge-AQ Benchmark Suite | TASK-23 |
| **TASK-33** | Adversarial Security Validation | TASK-23, TASK-28 |
| **TASK-34** | Guideline Ingestion Execution | TASK-05, TASK-24 |
| **TASK-35** | System Smoke Test & Verification | TASK-05, TASK-08, TASK-30, TASK-27, TASK-34 |
| **TASK-36** | Documentation & Runbooks (`README.md`) | TASK-35 |
