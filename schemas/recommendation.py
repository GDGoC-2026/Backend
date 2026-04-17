from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class RecommendationRequest(BaseModel):
    """Request for generating recommendations"""
    content: str = Field(..., description="Code snippet or English text to analyze")
    content_type: str = Field(..., description="Type of content: 'code' or 'english'")
    user_context: Optional[str] = Field(
        None, 
        description="User's skill level, goals, or additional context"
    )
    trigger_lines: int = Field(
        default=10,
        description="Minimum lines to trigger recommendation"
    )


class RecommendationChunk(BaseModel):
    """A chunk of streamed recommendation"""
    chunk: str = Field(..., description="Text content of this chunk")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RecommendationStreamResponse(BaseModel):
    """Response object for streaming recommendations"""
    status: str = Field("streaming", description="Status of the stream")
    content_type: str
    message: Optional[str] = None


class AddToRAGRequest(BaseModel):
    """Request to add content to RAG knowledge base"""
    content: str = Field(..., description="Content to add")
    content_type: str = Field(..., description="'code' or 'english'")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    source_type: str = Field(
        default="user_note",
        description="Source type: 'user_note', 'tip', 'resource', etc."
    )


class AddToRAGResponse(BaseModel):
    """Response from adding to RAG"""
    success: bool
    message: str
    content_id: Optional[int] = None


class RecommendationTrigger(BaseModel):
    """Trigger configuration for recommendations"""
    user_id: int
    content_type: str
    trigger_lines: int = 10
    is_active: bool = True


class RecommendationConfig(BaseModel):
    """Configuration for recommendation system"""
    recommendation_threshold: float = Field(default=0.5)
    recommendation_trigger_lines: int = Field(default=10)
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dim: int = Field(default=384)
