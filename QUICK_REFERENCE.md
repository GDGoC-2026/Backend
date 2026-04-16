# 🚀 Quick Reference - AI Recommendation System

## Environment Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create/update .env with:
GEMINI_API_KEY=your-api-key
MILVUS_URI=http://localhost:19530
RECOMMENDATION_TRIGGER_LINES=10

# 3. Start Milvus
docker-compose up -d milvus

# 4. Start Backend
uvicorn main:app --reload

# 5. Verify
curl http://localhost:8000/api/v1/recommendations/health
```

## API Quick Reference

### Stream Code Recommendations

```bash
curl -X POST http://localhost:8000/api/v1/recommendations/stream \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def hello():\n    print(\"hi\")",
    "content_type": "code",
    "user_context": "Python beginner",
    "trigger_lines": 5
  }' \
  --compressed
```

### Stream English Recommendations

```bash
curl -X POST http://localhost:8000/api/v1/recommendations/stream \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "I have been studying english.",
    "content_type": "english",
    "trigger_lines": 1
  }' \
  --compressed
```

### Add to Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/recommendations/add-to-rag \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "use async/await for better performance",
    "content_type": "code",
    "source_type": "tip"
  }'
```

### Health Check

```bash
curl http://localhost:8000/api/v1/recommendations/health
```

## JavaScript Frontend Integration

```javascript
const token = localStorage.getItem('token');

async function getRecommendations(content, type) {
  const response = await fetch('/api/v1/recommendations/stream', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      content,
      content_type: type,
      trigger_lines: 10
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let result = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.chunk) result += data.chunk;
      }
    }
  }

  return result;
}
```

## React Hook

```typescript
const useRecommendations = (token: string) => {
  const [recommendations, setRecommendations] = useState('');
  const [loading, setLoading] = useState(false);

  const stream = async (content: string, type: 'code' | 'english') => {
    setLoading(true);
    setRecommendations('');

    const response = await fetch('/api/v1/recommendations/stream', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content, content_type: type })
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        setRecommendations(prev => prev + chunk);
      }
    } finally {
      setLoading(false);
    }
  };

  return { recommendations, loading, stream };
};
```

## Configuration Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GEMINI_API_KEY` | string | Required | Google Gemini API key |
| `MILVUS_URI` | string | `http://localhost:19530` | Milvus connection URI |
| `RECOMMENDATION_THRESHOLD` | float | `0.5` | Min score for RAG retrieval |
| `RECOMMENDATION_TRIGGER_LINES` | int | `10` | Lines required to trigger |
| `EMBEDDING_MODEL` | string | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model name |
| `EMBEDDING_DIM` | int | `384` | Embedding dimension |

## Request Body Examples

### Code Recommendation
```json
{
  "content": "def add(a, b):\n    return a + b",
  "content_type": "code",
  "user_context": "Python intermediate",
  "trigger_lines": 5
}
```

### English Recommendation
```json
{
  "content": "I studied hard for the test and I passed it.",
  "content_type": "english",
  "user_context": "TOEFL prep",
  "trigger_lines": 1
}
```

### Add to RAG
```json
{
  "content": "Always use list comprehensions for better performance",
  "content_type": "code",
  "source_type": "tip",
  "metadata": {
    "language": "python",
    "category": "performance"
  }
}
```

## Response Examples

### SSE Stream Start
```
data: {"status": "started", "content_type": "code"}

```

### SSE Recommendation Chunk
```
data: {"chunk": "1. Code Quality: Consider adding docstring\n"}

```

### SSE Stream End
```
data: {"status": "completed"}

```

### Add to RAG Response
```json
{
  "success": true,
  "message": "Content added to knowledge base",
  "content_id": null
}
```

### Health Check Response
```json
{
  "status": "healthy",
  "service": "RecommendationAgent",
  "ready": true
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 503 Service Unavailable | Check `GEMINI_API_KEY` in `.env` |
| Connection refused to Milvus | Start Milvus: `docker-compose up -d milvus` |
| Content too short error | Increase `trigger_lines` parameter or provide longer content |
| SSE stream stops | Check browser timeout settings, Gemini rate limits |
| Collections not created | Check logs, verify Milvus connection |

## File Structure

```
Backend/
├── services/
│   └── recommendation_agent.py        # Main agent logic
├── api/v1/
│   ├── router.py                      # Route registration
│   └── endpoints/
│       └── recommendation.py           # SSE endpoints
├── schemas/
│   └── recommendation.py              # Request/response schemas
├── db/
│   └── vector.py                      # Milvus setup
├── core/
│   └── config.py                      # Configuration
├── main.py                            # App initialization
├── RECOMMENDATION_API.md              # Full API docs
├── RECOMMENDATION_SETUP_GUIDE.md      # Setup guide
└── IMPLEMENTATION_SUMMARY.md          # System summary
```

## Performance Tips

1. **Reduce max_output_tokens** for faster responses
2. **Adjust temperature** for consistency vs creativity
3. **Cache embeddings** for frequently analyzed content
4. **Use user_context** for better personalization
5. **Monitor Gemini rate limits** and implement backoff

## Features Checklist

- ✅ Real-time SSE streaming
- ✅ Google Gemini 2.0 Flash integration
- ✅ Milvus vector database setup
- ✅ 2 Collections (coding, english)
- ✅ Authentication & authorization
- ✅ Health check endpoints
- ✅ Error handling & validation
- ⏳ RAG retrieval implementation
- ⏳ Automatic triggers
- ⏳ User feedback system

## Next Steps

1. Get [Gemini API Key](https://aistudio.google.com/apikey)
2. Update `.env` with credentials
3. Start Milvus service
4. Run backend server
5. Test endpoints
6. Integrate with frontend
7. Deploy to production

## Resources

- [Full API Documentation](./RECOMMENDATION_API.md)
- [Setup & Testing Guide](./RECOMMENDATION_SETUP_GUIDE.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- [Gemini API Docs](https://ai.google.dev/docs)
- [Milvus Docs](https://milvus.io/docs)

---

**Need Help?**
Check the health endpoint and logs if something doesn't work!
