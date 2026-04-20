# Learnbro Backend

A high-performance FastAPI backend for the **Leanbro** learning platform, featuring AI-driven recommendations, knowledge graphs, and automated code execution.

## 🚀 Core Features

* **Authentication:** JWT & OAuth2 (Google, GitHub).
* **AI & RAG:** Knowledge graphs via **LightRAG**, vector search with **Milvus**, and **Gemini/Vertex AI** integration.
* **Learning:** Lessons, quizzes, spaced-repetition (**FSRS algorithm**), and gamification logic.
* **Note Taking:** Integrated **Monaco editor** to render markdown notes and ingested them to AI agents.
* **Code Execution:** Integrated **Judge0** support for coding problems.
* **Async Processing:** Background tasks and scheduled notifications via **Celery + Redis**.

## 🛠 Tech Stack

| Component | Technology |
| :--- | :--- |
| **API Framework** | FastAPI (Python 3.12+), Uvicorn |
| **Database** | PostgreSQL + SQLAlchemy (async) |
| **Graph / Vector** | Neo4j / Milvus |
| **Task Queue** | Redis + Celery (+ Celery Beat) |
| **AI / LLM** | Gemini / Vertex AI + LightRAG|

## 🏗️ Architecture Overview

At runtime, the API coordinates multiple services:

- **PostgreSQL:** Users, notes, lessons, quizzes, attempts, gamification data
- **Redis:** Celery broker/result backend
- **Celery workers:** Async ingestion and notification jobs
- **Neo4j:** Note graph visualization and relationships
- **Milvus:** Vector collections for recommendation and RAG
- **LightRAG:** Knowledge ingestion/query and graph data extraction
- **Gemini or Vertex AI:** LLM and embedding providers
- **Judge0:** Code run/submit evaluation

## ⚡ Quick Start

Run all commands from the repository root.

1.  **Environment Setup:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r Backend/requirements.txt
    cp Backend/.env.example Backend/.env
    ```

2.  **Database Migrations:**
    ```bash
    alembic -c Backend/alembic.ini upgrade head
    ```

3.  **Run Services:**
    * **API:** `uvicorn Backend.main:app --reload`
    * **Worker:** `celery -A Backend.core.celery_app worker --loglevel=info`
    * **Docs:** Access at `/docs` or `/redoc`.

## 🐳 Docker

To spin up the backend container:
```bash
docker compose -f Backend/docker-compose.yml up --build
```
*Note: Ensure external services (PostgreSQL, Redis, etc.) are accessible via your `.env` configuration.*

## 💼 Background Jobs

Celery tasks currently include:
- `process_markdown_note`: chunk/process note content and sync graph state
- `ingest_lightrag_content`: queue-friendly LightRAG ingestion with retry
- `send_due_review_notifications`: scheduled push reminder task (hourly via Celery Beat)

## 🔑 Key Configuration

Detailed settings are in `Backend/.env.example`. Ensure the following are set:
* `DATABASE_URL`: Must use `postgresql+asyncpg://`.
* `GEMINI_API_KEY`: Required for RAG and recommendations.
* `NEO4J_URI` / `MILVUS_URI`: Required for knowledge graph features.

## 💡 Common Commands

* **Create Migration:** `alembic -c Backend/alembic.ini revision --autogenerate -m "description"`
* **Run Tests:** `pytest Backend`
* **Health Check:** `GET /health`

> **Note:** Always run commands from the repo root to ensure the `Backend.*` namespace resolves correctly.
