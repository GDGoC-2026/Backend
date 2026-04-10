import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.schemas.recommendation import (
    RecommendationRequest,
    AddToRAGRequest,
    AddToRAGResponse,
)
from Backend.services.recommendation_agent import RecommendationAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize recommendation agent
try:
    recommendation_agent = RecommendationAgent()
except ValueError as e:
    logger.warning(f"RecommendationAgent initialization failed: {e}")
    recommendation_agent = None


@router.post("/stream")
async def stream_recommendations(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Stream real-time AI recommendations for user's code or English text.
    
    Uses Server-Sent Events (SSE) to stream recommendations as they're generated.
    
    Args:
        request: RecommendationRequest containing content and type
        current_user: Authenticated user
        
    Returns:
        StreamingResponse with SSE recommendations
        
    Example:
        POST /api/v1/recommendations/stream
        {
            "content": "def hello(name):\\n    print(f'Hello {name}')",
            "content_type": "code",
            "user_context": "Python beginner"
        }
    """
    
    if not recommendation_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation service not available. GEMINI_API_KEY not configured."
        )
    
    # Validate content type
    if request.content_type not in ["code", "english"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_type must be 'code' or 'english'"
        )
    
    # Check if content meets minimum length requirement
    lines = len(request.content.split('\n'))
    if lines < request.trigger_lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content must be at least {request.trigger_lines} lines. Current: {lines} lines"
        )
    
    async def generate_sse():
        """Generate SSE formatted response"""
        try:
            yield "data: {\"status\": \"started\", \"content_type\": \"" + request.content_type + "\"}\n\n"
            
            # Stream recommendations from agent
            async for chunk in recommendation_agent.generate_recommendations(
                content=request.content,
                content_type=request.content_type,
                user_context=request.user_context or "",
                top_k=3
            ):
                # SSE format: data: {json}\n\n
                yield f"data: {{\"chunk\": {repr(chunk)}}}\n\n"
            
            yield "data: {\"status\": \"completed\"}\n\n"
            
        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}")
            yield f"data: {{\"error\": {repr(str(e))}}}\n\n"
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/add-to-rag")
async def add_content_to_rag(
    request: AddToRAGRequest,
    current_user: User = Depends(get_current_user)
) -> AddToRAGResponse:
    """
    Add user's content to RAG knowledge base for future recommendations.
    
    This helps build a personalized knowledge base that improves recommendations over time.
    
    Args:
        request: Content to add to RAG
        current_user: Authenticated user
        
    Returns:
        AddToRAGResponse with success status
        
    Example:
        POST /api/v1/recommendations/add-to-rag
        {
            "content": "Function to process CSV files efficiently",
            "content_type": "code",
            "source_type": "user_note"
        }
    """
    
    if not recommendation_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not available"
        )
    
    if request.content_type not in ["code", "english"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_type must be 'code' or 'english'"
        )
    
    try:
        success = await recommendation_agent.add_to_rag(
            content=request.content,
            content_type=request.content_type,
            user_id=current_user.id,
            metadata=request.metadata,
            source_type=request.source_type
        )
        
        return AddToRAGResponse(
            success=success,
            message="Content added to knowledge base" if success else "Failed to add content",
            content_id=None  # TODO: Return actual content ID from Milvus
        )
        
    except Exception as e:
        logger.error(f"Error adding to RAG: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health")
async def recommendation_health():
    """Check if recommendation service is available"""
    return {
        "status": "healthy" if recommendation_agent else "unavailable",
        "service": "RecommendationAgent",
        "ready": recommendation_agent is not None
    }
