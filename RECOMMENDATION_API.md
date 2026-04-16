# AI Recommendation System - API Documentation

## Overview

The Recommendation Agent is a real-time AI system that analyzes user's code or English text and provides constructive, actionable recommendations using Google Gemini 2.0 Flash and retrieval-augmented generation (RAG) from Milvus vector database.

### Key Features

- **Real-time Streaming**: Uses Server-Sent Events (SSE) for live recommendations
- **Multi-Domain Support**: Code analysis and English language learning
- **RAG Integration**: Personalized recommendations based on knowledge base
- **Configurable Triggers**: Customizable line count thresholds for recommendations
- **Auto-reconnect**: Browser automatically reconnects on connection loss

## Endpoints

### 1. Stream Recommendations (SSE)

**Endpoint**: `POST /api/v1/recommendations/stream`

**Authentication**: Required (Bearer token)

**Purpose**: Stream AI recommendations in real-time as recommendations are generated

#### Request Body

```json
{
  "content": "def hello(name):\n    print(f'Hello {name}')\n    print('Welcome')",
  "content_type": "code",
  "user_context": "Python beginner, learning functions",
  "trigger_lines": 10
}
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | ✓ | Code snippet or English text to analyze |
| `content_type` | string | ✓ | Type of content: `"code"` or `"english"` |
| `user_context` | string | ✗ | User's skill level, goals, or additional context for personalization |
| `trigger_lines` | integer | ✗ | Minimum lines required to trigger recommendation (default: 10) |

#### Response Format (SSE)

The response streams Server-Sent Events with JSON data:

```
data: {"status": "started", "content_type": "code"}

data: {"chunk": "Here are recommendations for your code:\n\n1. Variable Naming: The variable name 'name' is clear..."}

data: {"chunk": "2. Documentation: Consider adding a docstring..."}

data: {"status": "completed"}
```

#### Response Examples

**Start Event**:
```json
{"status": "started", "content_type": "code"}
```

**Chunk Event** (repeated for each text chunk):
```json
{"chunk": "Here are some recommendations for improvement..."}
```

**Completion Event**:
```json
{"status": "completed"}
```

**Error Event**:
```json
{"error": "Error message here"}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Streaming started successfully |
| 400 | Invalid content_type or request format |
| 422 | Content doesn't meet minimum line requirement |
| 503 | Recommendation service not available (missing GEMINI_API_KEY) |

#### Example Usage (JavaScript)

```javascript
const eventSource = new EventSource('/api/v1/recommendations/stream', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    content: userCode,
    content_type: 'code',
    user_context: 'Intermediate Python developer',
    trigger_lines: 10
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.status === 'started') {
    console.log('Recommendations starting...');
  } else if (data.chunk) {
    console.log('Recommendation chunk:', data.chunk);
  } else if (data.status === 'completed') {
    console.log('Recommendations completed!');
    eventSource.close();
  }
};

eventSource.onerror = () => {
  console.error('Stream error');
  eventSource.close();
};
```

#### Example Usage (Python)

```python
import requests
import json

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

data = {
    'content': 'def greet(name):\n    print(f"Hello {name}")',
    'content_type': 'code',
    'user_context': 'Python beginner'
}

with requests.post(
    'http://localhost:8000/api/v1/recommendations/stream',
    json=data,
    headers=headers,
    stream=True
) as response:
    for line in response.iter_lines():
        if line:
            event = json.loads(line.decode('utf-8').replace('data: ', ''))
            print(event)
```

---

### 2. Add Content to RAG

**Endpoint**: `POST /api/v1/recommendations/add-to-rag`

**Authentication**: Required (Bearer token)

**Purpose**: Add user's content to the knowledge base for personalized future recommendations

#### Request Body

```json
{
  "content": "For efficient CSV processing, use pandas with appropriate chunk size",
  "content_type": "code",
  "source_type": "user_note",
  "metadata": {
    "language": "python",
    "topic": "data_processing"
  }
}
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | ✓ | Content to add to knowledge base |
| `content_type` | string | ✓ | Type of content: `"code"` or `"english"` |
| `source_type` | string | ✗ | Source type: `"user_note"`, `"tip"`, `"resource"` (default: `"user_note"`) |
| `metadata` | object | ✗ | Additional metadata (language, topic, difficulty, etc.) |

#### Response

```json
{
  "success": true,
  "message": "Content added to knowledge base",
  "content_id": null
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Content successfully added |
| 400 | Invalid content_type |
| 500 | Internal server error |
| 503 | RAG service not available |

---

### 3. Health Check

**Endpoint**: `GET /api/v1/recommendations/health`

**Authentication**: Not required

**Purpose**: Check if the recommendation service is available

#### Response

```json
{
  "status": "healthy",
  "service": "RecommendationAgent",
  "ready": true
}
```

Or if not configured:

```json
{
  "status": "unavailable",
  "service": "RecommendationAgent",
  "ready": false
}
```

---

## Milvus Collections Schema

### Collection: `coding`

Used for storing and finding similar code snippets, programming tips, and best practices.

**Fields**:
- `id` (INT64, Primary Key, Auto-increment)
- `content` (VARCHAR, max 65535) - The code snippet or tip
- `embeddings` (FLOAT_VECTOR, dim=384) - Vector embeddings for semantic search
- `metadata` (VARCHAR, max 2048) - JSON metadata (language, difficulty, etc.)
- `source_type` (VARCHAR, max 50) - `user_note`, `tip`, `resource`
- `created_at` (INT64) - Unix timestamp
- `user_id` (INT64) - Owner of the content

**Index**: HNSW on embeddings field (COSINE metric)

### Collection: `english`

Used for storing English learning materials and language improvement tips.

**Fields**: (Same schema as `coding`)
- `id`, `content`, `embeddings`, `metadata`, `source_type`, `created_at`, `user_id`

**Index**: HNSW on embeddings field (COSINE metric)

---

## Configuration

Add these environment variables to `.env`:

```env
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Milvus Configuration (default already set)
MILVUS_URI=http://localhost:19530

# Recommendation Settings
RECOMMENDATION_THRESHOLD=0.5
RECOMMENDATION_TRIGGER_LINES=10
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
```

---

## Recommendation Triggers

The recommendation system can be triggered in multiple ways:

### 1. **Manual Trigger via SSE**
User explicitly requests recommendations via the `/stream` endpoint.

### 2. **Condition-Based Trigger** (Planned)
Automatically trigger when:
- User completes specified number of lines of code (configurable)
- User hasn't received a recommendation in X minutes
- User takes notes in specific subject areas

### 3. **Event-Based Trigger** (Planned)
Trigger on events like:
- Code submission to Judge0
- Note creation/update
- Milestone achievement

---

## Content Types & Recommendations Focus

### Code Analysis (`content_type: "code"`)

The agent analyzes for:
1. **Code Quality** - Readability, structure, naming conventions
2. **Performance** - Optimization opportunities, computational complexity
3. **Best Practices** - Design patterns, SOLID principles
4. **Potential Issues** - Bugs, edge cases, error handling
5. **Security** - Input validation, injection risks, data protection

**Example Recommendation**:
```
1. Variable Naming: Consider renaming 'x' to 'count' for clarity
2. Performance: Use list comprehension instead of loop for 3x speedup
3. Best Practice: Add error handling for file operations
```

### English Learning (`content_type: "english"`)

The agent analyzes for:
1. **Grammar** - Syntax errors, tense consistency
2. **Vocabulary** - Word choice suggestions, synonyms
3. **Style** - Clarity, conciseness, tone
4. **Structure** - Organization, flow, coherence
5. **Fluency** - Natural expression, idioms

**Example Recommendation**:
```
1. Grammar: Change "I has finished" to "I have finished"
2. Vocabulary: Replace "really good" with "excellent" or "outstanding"
3. Structure: Consider moving this sentence to the previous paragraph
```

---

## Error Handling

### Common Errors

**1. GEMINI_API_KEY not configured**
```
Status: 503
Response: {"detail": "Recommendation service not available. GEMINI_API_KEY not configured."}
```

**2. Invalid content_type**
```
Status: 400
Response: {"detail": "content_type must be 'code' or 'english'"}
```

**3. Content too short**
```
Status: 422
Response: {"detail": "Content must be at least 10 lines. Current: 5 lines"}
```

---

## Performance Considerations

- **Streaming Response**: Recommendations start appearing immediately (not waiting for full generation)
- **Token Limits**: Gemini 2.0 Flash has built-in rate limiting
- **RAG Latency**: Milvus queries add ~100-200ms per search
- **Timeout**: SSE streams have a default timeout (configure in frontend)

---

## Best Practices

1. **Set User Context**: Provide `user_context` to get more personalized recommendations
2. **Build Knowledge Base**: Use `/add-to-rag` endpoint to build personalized knowledge
3. **Progressive Triggers**: Start with higher `trigger_lines` value, decrease as system learns
4. **Error Handling**: Always handle stream errors in frontend
5. **Rate Limiting**: Consider implementing client-side rate limiting for cost control

---

## Frontend Integration Example

```typescript
// React Hook for SSE-based recommendations
const useRecommendations = () => {
  const [recommendations, setRecommendations] = useState('');
  const [loading, setLoading] = useState(false);

  const getRecommendations = async (
    content: string,
    contentType: 'code' | 'english',
    userContext?: string
  ) => {
    setLoading(true);
    setRecommendations('');

    try {
      const response = await fetch('/api/v1/recommendations/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          content,
          content_type: contentType,
          user_context: userContext
        })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        const text = decoder.decode(value);
        const events = text.split('\n\n');

        for (const event of events) {
          if (event.startsWith('data: ')) {
            const data = JSON.parse(event.replace('data: ', ''));
            if (data.chunk) {
              setRecommendations(prev => prev + data.chunk);
            }
          }
        }
      }
    } finally {
      setLoading(false);
    }
  };

  return { recommendations, loading, getRecommendations };
};
```

---

## Roadmap

- [ ] Embedding model integration (sentence-transformers)
- [ ] Automatic trigger system (time-based, event-based)
- [ ] User feedback system to improve recommendations
- [ ] Multi-language support
- [ ] Custom recommendation rules per user
- [ ] Analytics dashboard for recommendation effectiveness
- [ ] Integration with code review workflow

---

## Support

For issues or questions:
1. Check `/api/v1/recommendations/health` status
2. Verify GEMINI_API_KEY is configured in `.env`
3. Ensure Milvus service is running on `http://localhost:19530`
4. Check backend logs for detailed error messages
