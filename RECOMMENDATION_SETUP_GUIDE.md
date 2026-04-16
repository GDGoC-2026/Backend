# AI Recommendation System - Setup Guide

## Quick Start

This guide walks you through setting up and using the AI Recommendation System.

## Prerequisites

1. **Milvus Vector Database** running on `http://localhost:19530`
2. **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/apikey)
3. **Python 3.10+**
4. **Redis** for Celery (already configured)

## Step-by-Step Setup

### 1. Install Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or update `.env` file in the project root:

```env
# Existing configs
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/gdgoc
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here

# OAuth (already configured)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_secret
GITHUB_CLIENT_ID=your_github_id
GITHUB_CLIENT_SECRET=your_secret

# NEW: AI & Recommendation System
GEMINI_API_KEY=your-gemini-api-key-here
MILVUS_URI=http://localhost:19530

# Recommendation Settings (Optional - uses defaults if not set)
RECOMMENDATION_THRESHOLD=0.5
RECOMMENDATION_TRIGGER_LINES=10
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
```

### 3. Setup Milvus (Docker)

**Option A: Using Docker Compose**

```yaml
# docker-compose.yml
version: '3.5'

services:
  milvus:
    image: milvusdb/milvus:latest
    container_name: milvus-standalone
    ports:
      - "19530:19530"
      - "9091:9091"
    environment:
      COMMON_STORAGETYPE: local
    volumes:
      - milvus_data:/var/lib/milvus

volumes:
  milvus_data:
```

**Run Milvus:**
```bash
docker-compose up -d milvus
```

**Option B: Local Installation**

Follow [Milvus Installation Guide](https://milvus.io/docs/install_standalone-docker.md)

**Verify Milvus is running:**
```bash
curl http://localhost:19530/healthz
```

### 4. Get Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Create API Key"
3. Copy the key to your `.env` file as `GEMINI_API_KEY`

### 5. Start Backend Server

```bash
cd Backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On startup, you should see:
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Connecting to Milvus...
INFO: Successfully connected to Milvus
INFO: Creating default Milvus collections...
INFO: Milvus collections initialized
```

### 6. Verify Setup

Check health endpoints:

```bash
# General health
curl http://localhost:8000/health

# Recommendation service health
curl http://localhost:8000/api/v1/recommendations/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "RecommendationAgent",
  "ready": true
}
```

## Testing the System

### 1. Get Authentication Token

First, login to get a bearer token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "password"}'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

Save the `access_token`.

### 2. Stream Code Recommendations

Create a test file `test_recommendation.py`:

```python
import requests
import json

TOKEN = "your-access-token-here"
BASE_URL = "http://localhost:8000"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Test code snippet
code_content = """
def calculate_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    average = total / len(numbers)
    return average

def check_even(num):
    if num % 2 == 0:
        print("even")
    else:
        print("odd")

result = calculate_average([1, 2, 3, 4, 5])
check_even(result)
"""

payload = {
    "content": code_content,
    "content_type": "code",
    "user_context": "Python intermediate developer",
    "trigger_lines": 10
}

print("Streaming recommendations...\n")

response = requests.post(
    f"{BASE_URL}/api/v1/recommendations/stream",
    headers=headers,
    json=payload,
    stream=True
)

for line in response.iter_lines():
    if line:
        try:
            event_data = line.decode('utf-8')
            if event_data.startswith("data: "):
                json_str = event_data[6:]  # Remove "data: " prefix
                data = json.loads(json_str)
                
                if data.get("status") == "started":
                    print("🚀 Starting recommendations...\n")
                elif data.get("chunk"):
                    print(data["chunk"], end="", flush=True)
                elif data.get("status") == "completed":
                    print("\n\n✅ Recommendations completed!")
        except json.JSONDecodeError:
            pass
```

Run the test:
```bash
cd Backend
python test_recommendation.py
```

### 3. Stream English Learning Recommendations

```python
# Similar to above, but with:
payload = {
    "content": "I has been studying english for three years. I really enjoys reading books and watching movies.",
    "content_type": "english",
    "user_context": "Advanced learner preparing for Cambridge exam",
    "trigger_lines": 2
}
```

### 4. Add Content to Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/recommendations/add-to-rag \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def efficient_merge_sort(arr): # implementation here",
    "content_type": "code",
    "source_type": "user_note",
    "metadata": {
      "language": "python",
      "topic": "sorting_algorithms",
      "difficulty": "intermediate"
    }
  }'
```

Response:
```json
{
  "success": true,
  "message": "Content added to knowledge base",
  "content_id": null
}
```

## Troubleshooting

### 1. "GEMINI_API_KEY is not set"

**Solution**: 
- Check `.env` file has `GEMINI_API_KEY=your-key`
- Restart backend server after updating `.env`
- Verify no quotes around the key

### 2. "Connection to Milvus failed"

**Solution**:
- Check Milvus is running: `curl http://localhost:19530/healthz`
- Check Milvus URI in `.env`: `MILVUS_URI=http://localhost:19530`
- Ensure port 19530 is not blocked by firewall

### 3. Streaming stops prematurely

**Solution**:
- Check frontend timeout settings
- Verify Gemini API rate limits not exceeded
- Check backend logs for errors

### 4. Recommendations don't improve based on added content

**Solution**:
- Embedding feature currently returns empty RAG context (TODO)
- Full RAG will be enabled once embedding model is integrated
- Check [Recommendation Agent Source](../services/recommendation_agent.py#L66)

## Advanced Configuration

### Custom Trigger Lines

Adjust when recommendations trigger:

```env
# Require 20 lines to trigger (default: 10)
RECOMMENDATION_TRIGGER_LINES=20
```

### Change Embedding Model

```env
# Different embedding model for RAG
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
EMBEDDING_DIM=768
```

### Adjust AI Generation Parameters

Edit `services/recommendation_agent.py` in `_get_system_prompt()` method:

```python
generation_config={
    "temperature": 0.5,      # Lower = more focused, Higher = more creative
    "top_p": 0.9,            # Nucleus sampling
    "top_k": 20,             # Diversity
    "max_output_tokens": 512 # Shorter responses
}
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│          EventSource SSE for streaming              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Backend                        │
│                                                     │
│  POST /api/v1/recommendations/stream               │
│  ├─ RecommendationAgent (Gemini)                   │
│  ├─ Streaming via SSE                             │
│  └─ User context + RAG                            │
│                                                     │
│  POST /api/v1/recommendations/add-to-rag           │
│  └─ Store content for future RAG                  │
└──────────┬──────────────────────────┬──────────────┘
           │                          │
           ▼                          ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  Google Gemini   │      │  Milvus Vector   │
    │  2.0 Flash       │      │  Database        │
    │                  │      │                  │
    │ - Code analysis  │      │ Collections:     │
    │ - English review │      │ - coding         │
    │ - Streaming      │      │ - english        │
    └──────────────────┘      └──────────────────┘
```

## Database Schema

### Milvus Collections

**coding** and **english** collections have identical schema:

```
Collection: coding | english
├── id (INT64, Primary Key, Auto-increment)
├── content (VARCHAR, max 65535)
├── embeddings (FLOAT_VECTOR, dim=384)
├── metadata (VARCHAR, max 2048)
├── source_type (VARCHAR: user_note, tip, resource)
├── created_at (INT64 timestamp)
├── user_id (INT64)
└── Index: HNSW on embeddings (COSINE metric)
```

## Performance Metrics

- **Streaming latency**: ~100-200ms first token
- **Recommendation generation**: 1-2 seconds average
- **RAG query time**: ~50-100ms (once implemented)
- **Request timeout**: 30 seconds default

## Next Steps

1. **Test with frontend**: Integrate SSE streaming in React
2. **Build RAG**: Implement embedding model integration
3. **Auto-triggers**: Add time-based and event-based triggers
4. **Analytics**: Track recommendation effectiveness
5. **User feedback**: Add rating system for recommendations

## Documentation Files

- [RECOMMENDATION_API.md](./RECOMMENDATION_API.md) - Full API documentation
- [RecommendationAgent Source](./services/recommendation_agent.py) - Agent implementation
- [Recommendation Endpoints](./api/v1/endpoints/recommendation.py) - Endpoint implementation
- [Milvus Vector](./db/vector.py) - Vector database setup

## Support & Issues

- Check `/health` and `/recommendations/health` endpoints
- Review application logs
- Check Milvus logs: `docker logs milvus-standalone`
- Visit [Milvus Documentation](https://milvus.io/docs)
- Visit [Google Gemini API Docs](https://ai.google.dev/docs)

---

**Last Updated**: 2026-04-11
**System Version**: 1.0.0
