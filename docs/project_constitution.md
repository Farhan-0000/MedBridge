# MedBridge v3 — Project Constitution

> **Status:** Active & Permanent  
> **Authority:** Principal Software Architect & Engineering Lead  
> **Applies to:** All Developers, AI Coding Agents, Reviewers, and Architects  
> **Scope:** Entire MedBridge v3 Codebase, Infrastructure, and Lifecycle  

---

# 1. Project Mission

* **The Problem:** Hypertension patients frequently receive complex, generic, or conflicting medical advice and lack accessible, evidence-grounded guidance for interpreting readings, managing medications, and identifying acute cardiovascular risks.
* **Intended Users:** Adult hypertension patients seeking informational guidance on blood pressure management, prescribed medications, lifestyle modifications, and symptom triage.
* **Primary Objective:** Deliver a safe, deterministic, multi-turn clinical conversational agent that provides evidence-grounded hypertension guidance with verbatim citations, enforces strict emergency triage, tracks patient context through deterministic event sourcing, and prevents clinical hallucinations.

---

# 2. System Vision

MedBridge v3 is an intelligent clinical decision-support conversational application. The system ingests and indexes peer-reviewed clinical hypertension guidelines (AHA/ACC, ESC/ESH, MedlinePlus) into a hybrid dense-sparse vector store. At runtime, the application evaluates patient queries through a multi-stage guarded pipeline: it executes deterministic emergency triage, extracts structured medical facts into an append-only event stream, evaluates context sufficiency via deterministic classification gates, retrieves and reranks verified guideline evidence, and generates plain-language patient responses with inline clinical citations.

Expected outcomes include zero out-of-domain hallucinations, sub-5ms emergency crisis escalation, mathematically deterministic state tracking across conversation turns, and guaranteed patient safety via fail-safe fallback boundaries.

---

# 3. Architecture Principles

All development must strictly adhere to the following enforceable architectural rules:

1. **Separation of Concerns:** The presentation layer, backend orchestration, AI inference, state management, and persistence tiers must remain strictly decoupled into isolated modules.
2. **Single Responsibility:** Each module, service, class, and function must have exactly one reason to change and one clearly defined owner.
3. **Deterministic State Projection:** Patient state tracking must follow an Event Sourcing pattern. Snapshots are mathematical projections of immutable event logs and must never be updated directly by generative LLM output.
4. **Guarded Pipeline Execution:** All generative AI stages must be preceded by deterministic or zero-temperature classification gates. No evidence generation may proceed without evidence validation.
5. **Fail-Safe Robustness:** The system must never throw an unhandled 500 error to a patient. Every failure (timeout, parse error, API limit) must degrade deterministically to a pre-vetted clinical fallback template.
6. **Explicit & Typed Interfaces:** All inter-module communication must use strictly typed Pydantic models, SQLAlchemy ORM models, or typed Python signatures. Untyped dictionaries across module boundaries are prohibited.

---

# 4. Final System Components

* **Presentation Layer (`frontend/`):** A lightweight Streamlit interface responsible for capturing patient input, rendering multi-turn message history, displaying colored routing action badges, and presenting collapsible citation panels. It contains zero clinical or AI logic and communicates exclusively with the backend via HTTP.
* **API Gateway & Middleware (`api/`):** A FastAPI application exposing session management and messaging endpoints, enforcing request validation, managing CORS for loopback traffic, and implementing global exception filters that map failures to clinically safe responses.
* **Core Orchestrator & State Machine (`core/`):** The central deterministic runtime engine that coordinates the 8-stage pipeline, evaluates emergency triage regex patterns, executes the Context Gate loop-breaker state machine, coordinates retrieval, routes gate actions, and persists audit trails.
* **State Management Engine (`state/`):** A pure, deterministic Python projector and session manager that applies typed delta events to patient context snapshots and persists events atomically to PostgreSQL.
* **AI & Retrieval Pipeline (`ai/`, `retrieval/`):** A sequential pipeline consisting of a Resilient LLM Wrapper, Context Extractor (LLM 1), Context Gate (LLM 2), Qdrant Hybrid Retriever (Dense + Sparse + RRF), Cross-Encoder Reranker, Evidence Gate (LLM 3), and Response Generator (LLM 4).
* **Storage Tier (`db/`, Qdrant):** PostgreSQL 16 providing immutable append-only storage for clinical events and audit logs with materialized snapshots, and Qdrant providing hybrid dense-sparse vector indexing for chunked clinical guidelines.
* **Ingestion Pipeline (`ingestion/`):** An offline CLI tool that parses clinical PDFs with PyMuPDF, chunks text using section-aware boundaries (512/64 tokens), computes dense and sparse vectors, validates schema compliance, and upserts points to Qdrant.

---

# 5. Approved Technology Stack

Only the following approved technologies, frameworks, and libraries may be used. Introducing alternative frameworks is strictly prohibited without formal ADL approval.

| Layer | Approved Technology |
| :--- | :--- |
| **Frontend** | Streamlit ($\ge 1.35$), `httpx` (sync/async client) |
| **Backend Framework** | FastAPI ($\ge 0.111$), Uvicorn ($\ge 0.29$), Pydantic v2 ($\ge 2.7$), `pydantic-settings` |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (async), `asyncpg`, Alembic ($\ge 1.13$), `psycopg2-binary` |
| **Vector Store** | Qdrant ($\ge 1.9$) running via Docker container |
| **Embedding Models** | `fastembed` ($\ge 0.3$) utilizing `BAAI/bge-small-en-v1.5` (Dense) and `Qdrant/bm25` (Sparse) |
| **Reranker Model** | `sentence-transformers` ($\ge 3.0$) utilizing `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| **Primary LLM Provider** | Groq Cloud API (`llama-3.1-8b-instant`) via HTTPS REST |
| **Fallback LLM Provider** | OpenAI API (`gpt-4o-mini` or equivalent) via HTTPS REST |
| **Document Processing** | PyMuPDF / `fitz` ($\ge 1.24$) |
| **Logging & Telemetry** | `structlog` (structured JSON logging) |
| **Testing Suite** | `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` test client |
| **Infrastructure** | Docker Engine ($\ge 24.0$), Docker Compose v3.9 |

---

# 6. Data Ownership Rules

1. **Frontend Isolation:** The Streamlit frontend owns only local presentation state (`st.session_state`). It is **forbidden** from directly accessing PostgreSQL, Qdrant, or external LLM APIs.
2. **State Ownership:** The `state/` module owns the schema and business logic for mutating context snapshots and appending to `clinical_events`. No other module may write to these tables.
3. **Audit Log Immutability:** The `audit_logs` and `clinical_events` tables are write-once, append-only data stores. Database `RULE` triggers must reject all `UPDATE` and `DELETE` queries.
4. **Vector Store Ownership:** The `ingestion/` module owns write access (collection creation, vector upsert) to Qdrant. The `retrieval/` module has strictly read-only search access.
5. **Direct AI Bypass Prohibited:** AI modules (`ai/`) may not query the database or vector store directly; they must receive inputs from and return outputs to the Core Orchestrator.

---

# 7. AI System Rules

1. **XML Boundary Isolation:** All prompts containing untrusted user text must encapsulate the input within `<untrusted_user_input>` tags to neutralize prompt injection attacks. System prompts, context, and evidence must be strictly partitioned in distinct XML blocks (`<system_instructions>`, `<patient_context>`, `<clinical_evidence>`, `<user_query>`).
2. **Deterministic Gate Classification:** Context Gate (LLM 2) and Evidence Gate (LLM 3) must always execute with `temperature: 0.0` and `seed: 42`. Non-zero temperature on safety gates is strictly prohibited.
3. **Generator Temperature Constraint:** Response Generator (LLM 4) must execute with `temperature: 0.3` to balance clinical adherence with linguistic fluency.
4. **Template Bypass on Rejection:** If the Evidence Gate or Emergency Classifier evaluates to `ABSTAIN` or `ESCALATE`, the Response Generator (LLM 4) **must not be invoked**. Pre-vetted deterministic templates from `core/templates.py` must be returned immediately.
5. **Loop-Breaker Threshold:** If `soft_ask_count >= 2`, the orchestrator must override the Context Gate action to `GENERALIZE`, inject the loop-breaker transition prefix, and force progression to retrieval.
6. **Hallucination Zero-Tolerance:** The Response Generator must generate claims grounded strictly in provided `<clinical_evidence>`. Uncited clinical claims are treated as critical defects.
7. **Threadpool Offloading:** The Cross-Encoder Reranker is a CPU-bound operation and must always be invoked via `asyncio.to_thread()` to prevent blocking the FastAPI event loop.

---

# 8. Security Principles

1. **Loopback Binding:** All local service ports (FastAPI `:8000`, PostgreSQL `:5432`, Qdrant `:6333`, Streamlit `:8501`) must bind strictly to `127.0.0.1`. Binding to `0.0.0.0` in production without an authenticating reverse proxy is prohibited.
2. **Secret Management:** API keys, database credentials, and secret tokens must be loaded through `pydantic-settings` from environment variables. Hardcoding credentials in code, configuration files, or Dockerfiles is strictly forbidden.
3. **No Plaintext PHI in Prompts:** Real patient Protected Health Information (PHI) must never be sent to external LLM APIs. All testing, benchmarking, and development must use synthetic clinical vignettes.
4. **Structured Logging Sanitization:** Authorization headers, bearer tokens, API keys, and raw database passwords must be scrubbed automatically by `structlog` log processors prior to log emission.
5. **Input Length Constraints:** The API layer must reject messages exceeding 2,000 characters with HTTP 422 to prevent denial-of-service and buffer exhaustion.

---

# 9. Coding Standards

1. **Strict Type Hinting:** All Python code must include complete type annotations (arguments and return types). Code must pass `mypy --strict` without errors.
2. **Linting & Formatting:** All code must conform to standard PEP 8 rules, enforced via `ruff` with line-length 100.
3. **Error Handling Protocol:** Never use bare `except:` clauses. Catch specific exceptions (`httpx.TimeoutException`, `ValidationError`, `json.JSONDecodeError`).
4. **Async/Await Integrity:** Avoid blocking calls in async route handlers or orchestrator logic. Use async drivers (`asyncpg`, `httpx.AsyncClient`) and offload heavy CPU work to threadpools.
5. **Testing Thresholds:** Every module must maintain $\ge 85\%$ unit test coverage. All core state transitions and emergency classifier patterns must have $100\%$ branch coverage.

---

# 10. Integration Rules

```
ALLOWED:
Streamlit ──(HTTP)──▶ FastAPI Route ──▶ Orchestrator ──▶ State Projector ──▶ PostgreSQL
                                                │ ──▶ Emergency Classifier
                                                │ ──▶ Resilient LLM Wrapper ──▶ Groq Cloud API
                                                │ ──▶ Hybrid Retriever ──▶ Qdrant
                                                │ ──▶ Cross-Encoder (Threadpool)

PROHIBITED:
Streamlit ──(SQL)──❌──▶ PostgreSQL
Streamlit ──(gRPC)─❌──▶ Qdrant
AI Module ──(SQL)──❌──▶ PostgreSQL
Retriever ──(HTTP)─❌──▶ Groq Cloud API
FastAPI   ──(Raw)──❌──▶ Qdrant (bypassing Hybrid Retriever)
```

1. All external network traffic must pass through the `ResilientLLMWrapper` (for LLMs) or `HybridRetriever` (for Qdrant).
2. The orchestrator is the sole coordinator. Peer-to-peer communication between sub-pipelines (e.g. Extractor calling Retriever directly) is forbidden.

---

# 11. Development Rules

1. **Architecture Decision Records:** Any proposed change that alters component boundaries, introduces new dependencies, modifies database schemas, or changes the AI pipeline flow must be documented and approved in the `architecture_decision_log.md` before implementation.
2. **Module Modification Boundaries:** Changes to a module must not alter its public interface without updating its corresponding specification in `module_specifications.md` and downstream callers.
3. **Deterministic Testing:** Automated tests must not make live calls to external LLM APIs by default. Unit and integration tests must use deterministic mocks or recorded responses. Live API tests must be segregated into optional benchmark suites.
4. **Database Migrations:** Schema changes must be enacted exclusively through forward-compatible Alembic migration scripts. Direct schema modification via SQL console is prohibited.

---

# 12. Non-Negotiable Constraints

The following constraints are absolute and non-negotiable across the entire project lifecycle:

* **[NON-NEGOTIABLE 1] Deterministic Fast-Path Triage:** The Emergency Classifier must evaluate messages before any LLM is called and return `ESCALATE` in $<5$ms on match.
* **[NON-NEGOTIABLE 2] Append-Only Event Log:** Clinical events and audit logs must remain permanently immutable; no updates or deletes are permitted.
* **[NON-NEGOTIABLE 3] Pure Zero-Temperature Gates:** Context Gate and Evidence Gate must execute at `temperature: 0.0` with `seed: 42`.
* **[NON-NEGOTIABLE 4] Loop-Breaker Limit:** The `soft_ask_count` limit is strictly 2. Upon reaching 2, the system must force `GENERALIZE`.
* **[NON-NEGOTIABLE 5] XML Input Isolation:** Patient input must always be delimited by `<untrusted_user_input>` XML tags in all prompts.
* **[NON-NEGOTIABLE 6] Template Bypass:** `ABSTAIN` and `ESCALATE` decisions must never call the LLM Generator; they must return deterministic templates.
* **[NON-NEGOTIABLE 7] No HTTP 500 to Patients:** The backend must handle all internal exceptions gracefully and return a valid, safe fallback response.

---

# 13. Definition of Done

A task, feature, or pull request is complete and accepted into the codebase only when all of the following criteria are satisfied:

- [ ] **Functional Compliance:** Implements all acceptance criteria defined in the Development Backlog task.
- [ ] **Architecture Adherence:** Respects all data ownership rules, integration constraints, and non-negotiable boundaries.
- [ ] **Unit Tests Passing:** Complete unit test suite implemented with $\ge 85\%$ line coverage and zero failures.
- [ ] **Integration Verified:** Verified against running PostgreSQL and Qdrant instances with clean transaction commits and rollbacks.
- [ ] **Type & Lint Cleanliness:** Passes `ruff check .` and `mypy --strict` with zero warnings or errors.
- [ ] **Deterministic Behavior:** Verified that safety gates and emergency checks operate deterministically.
- [ ] **Documentation Updated:** Module specifications, API schemas, and runbooks updated to reflect any authorized modifications.
- [ ] **Security Verified:** No hardcoded secrets, input length validated, and XML isolation tags present on all prompt templates.
