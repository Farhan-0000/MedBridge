# MedBridge — Clinical Decision Support & Patient Consultation System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B.svg)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-v1.9+-DC2626.svg)](https://qdrant.tech/)
[![Test Suite](https://img.shields.io/badge/tests-460%2B%20passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MedBridge** is an enterprise-grade, safety-first clinical guidance and patient consultation assistant tailored specifically for **hypertension management**. Designed to bridge the gap between complex medical literature and patient understanding, MedBridge utilizes a deterministic guardrail architecture combining hybrid dense-sparse vector search, multi-tier LLM failover, and strict clinical action categorization.

---

## Table of Contents

- [Overview & Clinical Mission](#overview--clinical-mission)
- [System Architecture](#system-architecture)
- [Clinical Action Categorization](#clinical-action-categorization)
- [Prerequisites & System Requirements](#prerequisites--system-requirements)
- [Step-by-Step Developer Runbook](#step-by-step-developer-runbook)
- [Environment Variables & Configuration](#environment-variables--configuration)
- [Docker Operations & Infrastructure Management](#docker-operations--infrastructure-management)
- [Comprehensive Testing Suite](#comprehensive-testing-suite)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [Clinical Benchmark Harness (MedBridge-AQ)](#clinical-benchmark-harness-medbridge-aq)
  - [Adversarial & Security Testing](#adversarial--security-testing)
  - [Coverage Analysis](#coverage-analysis)
- [Troubleshooting & Diagnostic Playbook](#troubleshooting--diagnostic-playbook)
- [API Reference & Interaction Catalog](#api-reference--interaction-catalog)
- [Project Directory Structure](#project-directory-structure)
- [Regulatory & Clinical Safety Notice](#regulatory--clinical-safety-notice)

---

## Overview & Clinical Mission

Hypertension affects over 1.28 billion adults globally and is the leading preventable risk factor for cardiovascular disease. However, consumer generative AI systems present severe safety risks: hallucinated drug dosages, inappropriate recommendations during hypertensive crises, and unverified medical advice.

MedBridge implements a **zero-trust, safety-first clinical architecture**:
- **Deterministic Emergency Fast-Path**: Hypertensive crises ($>180/120\text{ mmHg}$) or red-flag cardiac symptoms (chest pain, shortness of breath, neurological deficits) trigger immediate emergency escalation in **$<10\text{ ms}$** without awaiting LLM inference.
- **Strict Evidence Grounding**: Clinical recommendations are retrieved exclusively from official medical guidelines (**AHA/ACC 2025**, **ESC/ESH 2024**, **MedlinePlus**) and verified via a cross-encoder reranker and an Evidence Verification Gate.
- **Finite-State Multi-Turn Routing**: Multi-turn dialogue accumulates patient state (medications, adherence, blood pressure readings) and breaks ambiguity loops via strict `SOFT-ASK` counting (max 2 turns).
- **Graceful Multi-Tier Degradation**: When external LLM APIs fail or experience rate-limiting, MedBridge fails over from Groq (`llama-3.3-70b-versatile`) to OpenAI (`gpt-4o-mini`) and ultimately defaults to pre-vetted deterministic clinical templates.

---

## System Architecture

```mermaid
flowchart TD
    User([Patient / Clinician]) --> UI[Streamlit Frontend<br/>:8501]
    UI --> API[FastAPI Backend / Orchestrator<br/>:8000]

    subgraph "Emergency Fast-Path (<10ms)"
        API --> EmCheck{Emergency Detector}
        EmCheck -- "BP >180/120 or Red-Flags" --> EscalateBadge[🚨 ESCALATE<br/>Emergency Notice & 911 Call]
    end

    subgraph "Stateful Context & Dialogue"
        EmCheck -- "Non-Emergency" --> StateProj[State Projector<br/>Context Accumulator]
        StateProj --> CtxGate{Context Gate}
        CtxGate -- "Missing Critical Info (<=2 turns)" --> SoftAskBadge[🟡 SOFT-ASK<br/>Targeted Clarification]
    end

    subgraph "Hybrid Retrieval Engine"
        CtxGate -- "Sufficient Context" --> HybridRet[Hybrid Retriever<br/>Qdrant :6333]
        HybridRet --> Dense[Dense: BGE-small-en-v1.5]
        HybridRet --> Sparse[Sparse: Qdrant/BM25]
        Dense & Sparse --> RRF[Reciprocal Rank Fusion]
        RRF --> Rerank[Cross-Encoder Reranker<br/>ms-marco-MiniLM-L-6-v2]
    end

    subgraph "Evidence Verification & Response Generation"
        Rerank --> EvGate{Evidence Gate}
        EvGate -- "Insufficient / Out-of-Domain" --> GenBadge[🔵 GENERALIZE<br/>Safe High-Level Guidance]
        EvGate -- "Grounded in Guidelines" --> RespGen[Response Generator]
        RespGen --> AnswerBadge[🟢 ANSWER<br/>Evidence-Grounded Recommendation + Citations]
    end

    subgraph "Persistence & Audit"
        API --> Postgres[(PostgreSQL 16 :5433<br/>Sessions, Turns, Audit Trail)]
    end
```

---

## Clinical Action Categorization

Every assistant response is tagged with an immutable **Clinical Action Badge**:

| Action Badge | Meaning | Trigger Criteria | Patient Safety Handling |
|:---|:---|:---|:---|
| `🚨 ESCALATE` | **Medical Emergency** | BP $>180/120\text{ mmHg}$, chest pain, severe dyspnea, vision changes, stroke symptoms. | Halts consultation. Immediate direction to emergency services (911) and nearest emergency room. |
| `🟡 SOFT-ASK` | **Targeted Clarification** | Missing vital details (e.g. current BP values, medication dosage, symptom duration). | Asks at most 2 targeted follow-up questions. Loop-breaker automatically transitions to `GENERALIZE` on turn 3. |
| `🔵 GENERALIZE` | **Educational Guidance** | General health questions, lifestyle queries, or questions lacking direct guideline grounding. | Provides safe lifestyle advice (DASH diet, sodium reduction) without making specific drug adjustments. |
| `🟢 ANSWER` | **Evidence-Grounded Recommendation** | Question is fully grounded in indexed clinical guidelines with high semantic retrieval relevance. | Delivers personalized clinical insights with verifiable inline citations (e.g. `[AHA/ACC 2025 §3.1]`). |

---

## Prerequisites & System Requirements

Before running MedBridge, ensure the following are installed on your host system:

- **Operating System**: Windows 10/11, macOS (Apple Silicon/Intel), or Linux (Ubuntu 22.04+).
- **Python**: Version `3.11` or `3.12` ([python.org](https://www.python.org/downloads/)).
- **Docker & Docker Compose**: Docker Desktop or Docker Engine v24+ ([docker.com](https://www.docker.com/)).
- **Memory**: Minimum 4 GB RAM (8 GB recommended for local embedding and reranking inference).
- **API Keys** *(Optional for fallback mode, required for full LLM generation)*:
  - Groq API Key (`GROQ_API_KEY`) from [console.groq.com](https://console.groq.com)
  - OpenAI API Key (`OPENAI_API_KEY`) from [platform.openai.com](https://platform.openai.com)

---

## Step-by-Step Developer Runbook

### 1. Clone the Repository

```bash
git clone https://github.com/Farhan-0000/MedBridge.git
cd MedBridge
```

### 2. Set Up Virtual Environment

#### Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS / Linux (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install the core package and its development/test dependencies:
```bash
python -m pip install --upgrade pip
pip install -e ".[test]"
```

Alternatively, install using `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment configuration:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and configure your credentials:
```ini
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_PASSWORD=password
DATABASE_URL=postgresql+asyncpg://medbridge_app:password@127.0.0.1:5433/medbridge
QDRANT_URL=http://127.0.0.1:6333
```

### 5. Start Infrastructure Containers

Launch PostgreSQL and Qdrant in detached mode:
```bash
docker compose up -d
```

Verify that both containers are running in a healthy state:
```bash
docker compose ps
```
*Expected Output:*
```
NAME                   IMAGE                  COMMAND                  SERVICE    STATUS
medbridge-postgres-1   postgres:16-alpine     "docker-entrypoint.s…"   postgres   Up (healthy)
medbridge-qdrant-1     qdrant/qdrant:latest   "./entrypoint.sh"        qdrant     Up (healthy)
```

### 6. Apply Database Migrations

Apply transactional schema migrations using Alembic:
```bash
alembic upgrade head
```
This initializes the `sessions`, `turns`, `clinical_states`, and `audit_logs` tables in PostgreSQL.

### 7. Ingest Clinical Knowledge Base

Run the ingestion CLI to parse, validate, chunk, and index the clinical guideline PDFs into Qdrant:

```bash
# Optional dry-run verification
python -m medbridge.ingestion --pdf-dir ./data/guidelines/ --dry-run

# Live indexing with collection recreation
python -m medbridge.ingestion --pdf-dir ./data/guidelines/ --recreate
```
*Expected Output:*
```
[INFO] medbridge.ingestion: Found 3 PDF document(s) in data\guidelines
[INFO] medbridge.ingestion.parser: Parsed PDF successfully: aha_acc_2025.pdf
[INFO] medbridge.ingestion.parser: Parsed PDF successfully: esc_esh_2024.pdf
[INFO] medbridge.ingestion.parser: Parsed PDF successfully: medlineplus_hbp.pdf
[INFO] medbridge.ingestion.indexer: Created Qdrant collection 'clinical_guidelines'
[INFO] medbridge.ingestion.indexer: Successfully indexed 15 chunks into Qdrant collection 'clinical_guidelines'
```

### 8. Launch Backend API Server

Start the FastAPI backend server using Uvicorn:
```bash
uvicorn medbridge.main:app --host 127.0.0.1 --port 8000 --reload
```
The interactive Swagger API documentation will be available at:
`http://localhost:8000/docs`

### 9. Verify System Health Endpoint

In another terminal window, verify the health status:
```bash
curl http://localhost:8000/health
```
*Expected Response:*
```json
{
  "status": "healthy",
  "postgres_connected": true,
  "qdrant_connected": true
}
```

### 10. Launch Streamlit Frontend

Start the patient/clinician consultation user interface:
```bash
streamlit run medbridge/frontend/app.py --server.port 8501
```
Open your browser and navigate to:
**`http://localhost:8501`**

---

## Environment Variables & Configuration

All application configurations are managed using Pydantic Settings in [`medbridge/config.py`](file:///s:/Y4/S7/PROJECT%20I/MedBridge/medbridge/config.py) and loaded from `.env`:

| Variable | Description | Default Value | Required |
|:---|:---|:---|:---:|
| `GROQ_API_KEY` | Primary LLM provider API key | *None* | **Yes** (or dummy) |
| `OPENAI_API_KEY` | Secondary fallback LLM API key | `""` | Optional |
| `POSTGRES_PASSWORD` | Database user password | *None* | **Yes** |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL connection string | `postgresql+asyncpg://...:5433/medbridge` | **Yes** |
| `QDRANT_URL` | REST endpoint for Qdrant vector database | `http://127.0.0.1:6333` | **Yes** |
| `QDRANT_COLLECTION` | Target collection name for guidelines | `clinical_guidelines` | No |
| `LLM_MODEL` | Default model identifier for Groq | `llama-3.1-8b-instant` | No |
| `LLM_TEMPERATURE_GATES`| Temperature for deterministic gates | `0.0` | No |
| `LLM_TEMPERATURE_GENERATOR`| Temperature for conversational responses | `0.3` | No |
| `LLM_MAX_TOKENS_GATES` | Token budget for classification gates | `512` | No |
| `LLM_MAX_TOKENS_GENERATOR` | Token budget for final response | `1024` | No |
| `LLM_SEED` | Deterministic seed for reproducible inference | `42` | No |
| `LLM_MAX_RETRIES` | Max HTTP retry attempts on transient errors | `3` | No |
| `LLM_RETRY_BASE_DELAY` | Exponential backoff initial delay (seconds) | `1.0` | No |
| `RETRIEVAL_TOP_K_CANDIDATES`| Candidates retrieved per branch (dense/sparse) | `20` | No |
| `RETRIEVAL_TOP_K_RERANKED` | Chunks selected after cross-encoder scoring | `5` | No |
| `RERANKER_MODEL` | Hugging Face cross-encoder model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | No |
| `EMBEDDING_MODEL` | Dense semantic embedding model | `BAAI/bge-small-en-v1.5` | No |
| `SPARSE_MODEL` | Lexical sparse vector model | `Qdrant/bm25` | No |
| `SOFT_ASK_MAX_COUNT` | Max consecutive clarifying turns before breaker | `2` | No |
| `HOST` | Backend bind host address | `0.0.0.0` | No |
| `PORT` | Backend listening port | `8000` | No |
| `CORS_ORIGINS` | Permitted origins for CORS middleware | `["http://localhost:8501"]` | No |

---

## Docker Operations & Infrastructure Management

### Common Lifecycle Commands

| Action | Command |
|:---|:---|
| Start all infrastructure in background | `docker compose up -d` |
| View running container status & health | `docker compose ps` |
| Stream live container logs | `docker compose logs -f` |
| Stream logs for PostgreSQL only | `docker compose logs -f postgres` |
| Stream logs for Qdrant only | `docker compose logs -f qdrant` |
| Stop all containers | `docker compose stop` |
| Teardown containers and networks | `docker compose down` |
| Full reset (wipe persistent database volumes) | `docker compose down -v` |

### Port Mapping Details

To prevent conflicts with existing local database installations, ports are mapped as follows:
- **PostgreSQL**: Container port `5432` is exposed on host port **`5433`**.
- **Qdrant HTTP REST**: Container port `6333` is exposed on host port **`6333`**.
- **Qdrant gRPC**: Container port `6334` is exposed on host port **`6334`**.

---

## Comprehensive Testing Suite

MedBridge includes a battle-tested test suite containing over **460 automated tests** covering unit logic, database transactions, vector retrieval, end-to-end conversational pipelines, clinical vignette benchmarks, and adversarial security defenses.

### Unit Tests

Executes all isolated unit tests for classifiers, gates, state projectors, models, and template formatters:
```bash
python -m pytest medbridge/tests/unit/ -v
```
*(330+ unit tests, typically executes in ~55s)*

### Integration Tests

Executes live database and vector store tests, session multi-turn state accumulation, and end-to-end pipeline integration:
```bash
python -m pytest medbridge/tests/integration/ -v
```

To run only the end-to-end conversational pipeline integration test:
```bash
python -m pytest medbridge/tests/integration/test_e2e_pipeline.py -v
```

### Clinical Benchmark Harness (MedBridge-AQ)

Evaluates 200+ clinical hypertension vignettes across 6 test subsets to compute routing accuracy, citation precision, and safety metrics:

```bash
# Run full benchmark evaluation runner
python -m tests.benchmark.benchmark_runner

# Run benchmark test suite via pytest
python -m pytest tests/benchmark/ -v
```

Evaluation Criteria:
- **Emergency Detection Recall**: $100\%$ (zero missed emergencies)
- **Routing Accuracy**: $\ge 90\%$ across clinical action badges
- **Citation Precision**: $\ge 90\%$ grounding compliance
- **Hallucination Rate**: $0\%$ on out-of-domain queries

### Adversarial & Security Testing

Validates prompt injection isolation, brand-generic drug name invariance (RABBITS benchmark), and SQL injection defenses:

```bash
python -m pytest tests/adversarial/ -v
```

Evaluated Vectors:
1. **XML Tag Escape & Prompt Injection**: Prevents malicious user prompts from escaping `<patient_context>` containers or altering system instructions.
2. **Brand-Generic Drug Substitution**: Confirms identical clinical recommendations regardless of brand name (e.g. *Norvasc* vs *Amlodipine*, *Cozaar* vs *Losartan*).
3. **SQL Injection**: Confirms parameter binding and ORM isolation against SQL payloads in messages or session IDs.

### Coverage Analysis

Generate full code coverage metrics:
```bash
python -m pytest --cov=medbridge --cov-report=term-missing --cov-report=html
```
The interactive HTML coverage report will be saved to `htmlcov/index.html`.

---

## Troubleshooting & Diagnostic Playbook

### Scenario 1: Database Connection Refused (`connection to server at "127.0.0.1", port 5432 failed`)
- **Root Cause**: Host port mismatch. PostgreSQL is mapped to host port **`5433`** in `docker-compose.yml`, but `DATABASE_URL` is pointing to `5432`.
- **Remedy**: Check your `.env` file. Ensure `DATABASE_URL` uses port `5433`:
  ```ini
  DATABASE_URL=postgresql+asyncpg://medbridge_app:password@127.0.0.1:5433/medbridge
  ```
  Ensure the container is running: `docker compose ps`.

### Scenario 2: Qdrant Reports Unhealthy or Connection Refused on `:6333`
- **Root Cause**: Minimal Qdrant container image lacks `curl` or `wget`.
- **Remedy**: Ensure `docker-compose.yml` uses the native TCP socket check:
  ```yaml
  test: ["CMD-SHELL", "bash -c 'cat < /dev/null > /dev/tcp/localhost/6333' || exit 1"]
  ```
  Restart the container:
  ```bash
  docker compose restart qdrant
  ```

### Scenario 3: LLM API Rate Limiting (`HTTP 429`) or Invalid API Key (`HTTP 401`)
- **Observed Behavior**: Application does not crash. MedBridge automatically triggers its fallback mechanism:
  1. Primary Groq request fails $\rightarrow$ logs warning.
  2. Tries OpenAI fallback $\rightarrow$ logs warning if exhausted.
  3. Activates **Deterministic Pre-Vetted Clinical Template** $\rightarrow$ returns safe `GENERALIZE` guidance to patient.
- **Remedy**: Provide a valid `GROQ_API_KEY` or `OPENAI_API_KEY` in `.env`.

### Scenario 4: Streamlit Shows `ModuleNotFoundError: No module named 'medbridge'`
- **Root Cause**: Streamlit process launched from an outside directory without repository root in `PYTHONPATH`.
- **Remedy**: Install package in editable mode:
  ```bash
  pip install -e .
  ```
  Alternatively, run with python module syntax:
  ```bash
  python -m streamlit run medbridge/frontend/app.py
  ```

### Scenario 5: Vector Schema / Collection Recreation Errors
- **Remedy**: Reset and rebuild the collection using the ingestion tool:
  ```bash
  python -m medbridge.ingestion --pdf-dir ./data/guidelines/ --recreate
  ```

---

## API Reference & Interaction Catalog

The FastAPI backend exposes RESTful endpoints for session management and clinical inference:

| Method | Endpoint | Description | Request Payload | Response |
|:---|:---|:---|:---|:---|
| `GET` | `/health` | System readiness & dependency health check | *None* | `{"status": "healthy", "postgres_connected": true, "qdrant_connected": true}` |
| `POST` | `/api/sessions` | Create a new consultation session | `{}` | `{"session_id": "uuid", "created_at": "...", "status": "ACTIVE"}` |
| `GET` | `/api/sessions/{id}/history` | Retrieve full multi-turn conversation history | *None* | `[{"turn_number": 1, "role": "USER", "content": "..."}, ...]` |
| `POST` | `/api/sessions/{id}/messages` | Send patient message & execute clinical pipeline | `{"content": "My BP is 150/95 mmHg"}` | `{"action": "GENERALIZE", "content": "...", "citations": [...]}` |

### Sample Interactive Flow

#### 1. Emergency Detection:
```bash
curl -X POST http://127.0.0.1:8000/api/sessions/<SESSION_ID>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "My blood pressure is 210/130 and I have severe chest pressure."}'
```
*Response Action:* `🚨 ESCALATE` (Fast-path triggered in $<10\text{ ms}$).

#### 2. Follow-Up Clarification:
```bash
curl -X POST http://127.0.0.1:8000/api/sessions/<SESSION_ID>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Can I take more medication?"}'
```
*Response Action:* `🟡 SOFT-ASK` (*"Could you clarify which medication you are currently taking and what your current blood pressure reading is?"*).

---

## Project Directory Structure

```
MedBridge/
├── alembic/                         # Database schema migration scripts
│   └── versions/                    # Transactional DDL revisions
├── data/
│   └── guidelines/                  # Official clinical guidelines (PDFs)
│       ├── aha_acc_2025.pdf
│       ├── esc_esh_2024.pdf
│       └── medlineplus_hbp.pdf
├── diagrams/                        # Architectural visual specifications
├── docs/                            # Technical specifications & project context
│   ├── architecture_decision_log.md
│   ├── master_project_context.md
│   └── technical_specification.md
├── medbridge/                       # Core application package
│   ├── ai/                          # AI models, gates, classifiers & generators
│   │   ├── context_extractor.py     # Patient clinical state extraction
│   │   ├── context_gate.py          # SOFT-ASK evaluation & loop-breaker
│   │   ├── emergency_classifier.py  # Regex & rule-based crisis detector (<10ms)
│   │   ├── evidence_gate.py         # Grounding & citation relevance gate
│   │   ├── llm_wrapper.py           # Multi-provider failover wrapper (Groq/OpenAI)
│   │   └── response_generator.py    # Evidence-grounded response generation
│   ├── core/                        # Orchestrator & state management
│   │   ├── orchestrator.py          # Finite state pipeline execution coordinator
│   │   └── state_projector.py       # Multi-turn context accumulator
│   ├── db/                          # Database connection & SQLAlchemy models
│   │   ├── models.py                # Sessions, Turns, States, AuditLogs
│   │   └── session.py               # Async session engine & dependency injection
│   ├── frontend/                    # Streamlit consultation interface
│   │   ├── app.py                   # Main UI entrypoint & navigation
│   │   ├── components.py            # Clinical disclaimers, chat history & badges
│   │   └── services.py              # Backend API HTTP client
│   ├── ingestion/                   # Guideline PDF ingestion pipeline
│   │   ├── chunker.py               # Semantic sliding-window chunker
│   │   ├── indexer.py               # Qdrant collection upsert & schema validation
│   │   └── parser.py                # PyMuPDF clinical document parser
│   ├── retrieval/                   # Hybrid vector retrieval engine
│   │   ├── embedder.py              # Dense & sparse vector embeddings
│   │   ├── hybrid_retriever.py      # Qdrant Reciprocal Rank Fusion search
│   │   └── reranker.py              # Cross-encoder semantic reranker
│   ├── schemas/                     # Pydantic input/output validation models
│   ├── config.py                    # Pydantic Settings configuration loader
│   └── main.py                      # FastAPI application entrypoint & routing
├── tests/                           # Benchmark & Adversarial evaluation suites
│   ├── adversarial/                 # Security tests (Prompt injection, SQLi, RABBITS)
│   └── benchmark/                   # MedBridge-AQ clinical vignette benchmark runner
├── docker-compose.yml               # PostgreSQL & Qdrant container orchestration
├── pyproject.toml                   # Project metadata, dependencies & tool configs
└── README.md                        # Master project documentation & runbook
```

---

## Regulatory & Clinical Safety Notice

> **IMPORTANT MEDICAL DISCLAIMER**
>
> MedBridge is an educational and clinical decision-support research software designed strictly for informational purposes. **It does not provide formal medical diagnosis, individualized treatment prescriptions, or direct clinical interventions.**
>
> - **In Case of Emergency**: Patients experiencing systolic blood pressure $>180\text{ mmHg}$, diastolic blood pressure $>120\text{ mmHg}$, chest pain, difficulty breathing, numbness, or loss of consciousness must immediately call emergency medical services (911 in the US) or visit the nearest emergency room.
> - **Physician Consultation**: Patients must always consult a licensed healthcare professional before altering medication doses, stopping prescribed therapies, or initiating new medical regimens.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
