# Walkthrough: Repository Structure Setup

The MedBridge v3 repository skeleton has been successfully created. The folder structure, placeholder files, and configuration files have been populated strictly according to the Project Constitution and Technical Specification.

## 1. Folder Tree

```text
medbridge/
├── alembic/
│   └── versions/
├── data/
│   └── guidelines/
├── frontend/
│   ├── components/
│   └── services/
├── medbridge/
│   ├── ai/
│   │   └── schemas/
│   ├── api/
│   │   ├── middleware/
│   │   ├── routes/
│   │   └── schemas/
│   ├── core/
│   ├── db/
│   │   └── migrations/
│   ├── ingestion/
│   ├── retrieval/
│   └── state/
└── tests/
    ├── evaluation/
    │   └── fixtures/
    │       └── medbridge_aq/
    ├── integration/
    └── unit/
```

## 2. File List

- `alembic.ini`
- `.env.example`
- `docker-compose.yml`
- `.gitignore`
- `pyproject.toml`
- `requirements.txt`
- `alembic/env.py`
- `alembic/versions/001_initial_schema.py`
- `data/guidelines/aha_acc_2025.pdf`
- `data/guidelines/esc_esh_2024.pdf`
- `data/guidelines/medlineplus_hbp.pdf`
- `frontend/app.py`
- `frontend/README.md`
- `frontend/components/__init__.py`
- `frontend/components/chat.py`
- `frontend/components/citations.py`
- `frontend/components/disclaimer.py`
- `frontend/services/__init__.py`
- `frontend/services/api_client.py`
- `frontend/services/session.py`
- `medbridge/__init__.py`
- `medbridge/config.py`
- `medbridge/main.py`
- `medbridge/README.md`
- `medbridge/ai/__init__.py`
- `medbridge/ai/context_extractor.py`
- `medbridge/ai/context_gate.py`
- `medbridge/ai/evidence_gate.py`
- `medbridge/ai/llm_wrapper.py`
- `medbridge/ai/response_generator.py`
- `medbridge/ai/schemas/__init__.py`
- `medbridge/ai/schemas/context_gate.py`
- `medbridge/ai/schemas/evidence_gate.py`
- `medbridge/ai/schemas/extractor.py`
- `medbridge/ai/schemas/response_generator.py`
- `medbridge/api/__init__.py`
- `medbridge/api/middleware/__init__.py`
- `medbridge/api/middleware/error_handler.py`
- `medbridge/api/routes/__init__.py`
- `medbridge/api/routes/messages.py`
- `medbridge/api/routes/sessions.py`
- `medbridge/api/schemas/__init__.py`
- `medbridge/api/schemas/enums.py`
- `medbridge/api/schemas/requests.py`
- `medbridge/api/schemas/responses.py`
- `medbridge/core/__init__.py`
- `medbridge/core/emergency_classifier.py`
- `medbridge/core/orchestrator.py`
- `medbridge/core/README.md`
- `medbridge/core/templates.py`
- `medbridge/db/__init__.py`
- `medbridge/db/connection.py`
- `medbridge/db/migrations/__init__.py`
- `medbridge/db/models.py`
- `medbridge/ingestion/__init__.py`
- `medbridge/ingestion/__main__.py`
- `medbridge/ingestion/chunker.py`
- `medbridge/ingestion/indexer.py`
- `medbridge/ingestion/parser.py`
- `medbridge/ingestion/README.md`
- `medbridge/retrieval/__init__.py`
- `medbridge/retrieval/embedder.py`
- `medbridge/retrieval/hybrid_retriever.py`
- `medbridge/retrieval/reranker.py`
- `medbridge/state/__init__.py`
- `medbridge/state/projector.py`
- `medbridge/state/README.md`
- `medbridge/state/session_manager.py`
- `tests/conftest.py`
- `tests/evaluation/benchmark_runner.py`
- `tests/evaluation/rabbits_runner.py`
- `tests/integration/test_database.py`
- `tests/integration/test_pipeline_e2e.py`
- `tests/integration/test_retrieval.py`
- `tests/unit/test_context_gate.py`
- `tests/unit/test_emergency_classifier.py`
- `tests/unit/test_evidence_gate.py`
- `tests/unit/test_llm_wrapper.py`
- `tests/unit/test_reranker.py`
- `tests/unit/test_state_projector.py`

## 3. Directory Descriptions

| Directory | Purpose | Responsibilities | Dependencies |
| --- | --- | --- | --- |
| `frontend/` | Presentation Layer | Renders Streamlit chat UI, submits requests, displays citations and routing badges. Contains no AI/business logic. | Streamlit, httpx |
| `medbridge/api/` | API Gateway & Middleware | Exposes FastAPI endpoints for sessions/messages, enforces request validation, handles errors via global middleware. | FastAPI, Uvicorn, Pydantic |
| `medbridge/core/` | Core Orchestrator | Coordinates the 8-stage AI pipeline, processes the contextual state machine, executes deterministic triage. | Pydantic, medbridge internal modules |
| `medbridge/ai/` | AI & Pipeline Generators | Orchestrates LLM inferences for context extraction, gates, and response generation securely (via resiliant wrapper). | Groq Cloud API, httpx |
| `medbridge/retrieval/` | Hybrid Retrieval | Implements dense+sparse search querying via Qdrant and post-retrieval cross-encoder reranking via threadpools. | qdrant-client, fastembed, sentence-transformers |
| `medbridge/state/` | State Management | Computes and projects deterministic state from patient message events (Event Sourcing) and coordinates with the DB. | PostgreSQL, medbridge internal modules |
| `medbridge/db/` | Database Storage | Immutable tracking and persistence for context snapshots, clinical events, and audit logs. | PostgreSQL, asyncpg, SQLAlchemy |
| `medbridge/ingestion/` | Data Ingestion | Offline CLI tool to extract, chunk, embed, and index clinical PDFs into the vector store. | PyMuPDF, fastembed, qdrant-client |
| `data/` | Static Assets | Houses the root PDF guidelines which represent the single source of truth for the RAG system. | None |
| `tests/` | Testing Suites | Contains all unit, integration, and evaluation suites to assert high coverage and behavior determinism. | pytest, pytest-asyncio |

The repository is now fully initialized and ready for component-by-component implementation.
