"""
FastAPI Integration Guide for Content Generation Workflows

This file demonstrates how to integrate the multi-agent workflow system
with your existing FastAPI application.
"""

# Step 1: Add to your FastAPI router file (api/v1/router.py)

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from db.session import SessionLocal
from api.deps import get_db
from db.base import User

# Import the workflow components
from services.workflows import ExerciseOrchestrator
from services.workflows.config import (
    ContentGenerationRequest,
    StudentProfile,
    ContentLevel,
    ContentType,
)
from services.workflows.utils import (
    create_student_profile,
    create_content_generation_request,
    validate_workflow_input,
    get_content_statistics,
)

# Create router
content_router = APIRouter(prefix="/content", tags=["content_generation"])


# Endpoint 1: Generate content for a student
@content_router.post("/generate")
async def generate_educational_content(
    request: ContentGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate personalized educational content based on student profile.
    
    This endpoint triggers the multi-agent workflow system to create:
    - Flashcards (spaced repetition)
    - Mind maps (visual learning)
    - Quizzes (assessment)
    - Lessons (comprehensive learning)
    
    Request body:
    {
        "student_profile": {
            "student_id": "123",
            "name": "Alice",
            "subject": "Biology",
            "current_level": "intermediate",
            "learning_style": "visual",
            "knowledge_gaps": ["Cellular Respiration"],
            "strengths": ["Anatomy"],
            "learning_pace": "normal",
            "daily_study_time_minutes": 45
        },
        "topic": "Cell Biology",
        "subtopics": ["Mitochondria", "Respiration", "Energy"],
        "learning_objectives": ["Understand cells", "Learn respiration"],
        "content_types": ["flashcard", "mindmap", "quiz", "lesson"],
        "max_items": 10
    }
    """
    try:
        # Validate input
        validate_workflow_input(request)
        
        # Initialize orchestrator
        orchestrator = ExerciseOrchestrator()
        
        # Execute workflow
        workflow_result = await orchestrator.run({"request": request})
        
        if not workflow_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail="Workflow execution failed"
            )
        
        # Store generated content in database (optional)
        # await store_generated_content(db, current_user.id, workflow_result)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Content generated successfully",
                "data": workflow_result,
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")


# Endpoint 2: Get content statistics
@content_router.get("/stats/{student_id}")
async def get_content_stats(
    student_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get statistics about generated content for a student.
    """
    try:
        # Retrieve content from database
        # content = await db.query(GeneratedContent).filter(
        #     GeneratedContent.student_id == student_id
        # ).all()
        
        # For now, return empty stats
        stats = {
            "total_items": 0,
            "by_type": {},
            "average_quality": 0.0,
            "total_estimated_time": 0,
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "student_id": student_id,
                "statistics": stats,
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint 3: Quick generate with simplified input
@content_router.post("/quick-generate")
async def quick_generate(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """
    Quick content generation with defaults.
    
    Request body (simplified):
    {
        "student_id": "123",
        "name": "Alice",
        "subject": "Math",
        "level": "intermediate",
        "learning_style": "visual",
        "topic": "Quadratic Equations",
        "subtopics": ["Factoring", "Formula", "Graphing"],
        "objectives": ["Solve equations", "Graph parabolas"],
        "content_types": ["flashcard", "quiz"]
    }
    """
    try:
        # Create student profile from simplified input
        student = create_student_profile(
            student_id=body.get("student_id"),
            name=body.get("name"),
            subject=body.get("subject"),
            current_level=body.get("level", "intermediate"),
            learning_style=body.get("learning_style", "visual"),
            knowledge_gaps=body.get("knowledge_gaps", []),
            strengths=body.get("strengths", []),
            learning_pace=body.get("pace", "normal"),
        )
        
        # Create request
        request = create_content_generation_request(
            student_profile=student,
            topic=body.get("topic"),
            subtopics=body.get("subtopics", []),
            learning_objectives=body.get("objectives", []),
            content_types=body.get("content_types", ["flashcard", "quiz"]),
        )
        
        # Execute
        orchestrator = ExerciseOrchestrator()
        result = await orchestrator.run({"request": request})
        
        return JSONResponse(status_code=200, content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Add router to main FastAPI app (in main.py):
# from api.v1.router import content_router
# app.include_router(content_router, prefix="/api/v1")


# ============================================================================
# DATABASE MODEL FOR STORING GENERATED CONTENT (Optional)
# Add to models/learning.py or create models/content.py
# ============================================================================

from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from db.base import Base


class GeneratedContent(Base):
    """Model for storing generated educational content"""
    
    __tablename__ = "generated_content"
    
    id = Column(String, primary_key=True)
    student_id = Column(String, ForeignKey("user.id"), index=True)
    content_type = Column(String)  # flashcard, mindmap, quiz, lesson
    title = Column(String)
    topic = Column(String)
    content = Column(JSON)  # Serialized content
    difficulty_level = Column(String)
    estimated_time_minutes = Column(Float)
    quality_score = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    student = relationship("User", back_populates="generated_content")


# Add to User model in models/user.py:
#   generated_content = relationship("GeneratedContent", back_populates="student")


# ============================================================================
# CELERY TASK FOR ASYNC CONTENT GENERATION (Optional)
# Add to workers/content_tasks.py
# ============================================================================

from celery import shared_task
from services.workflows import ExerciseOrchestrator
import asyncio
import json


@shared_task(name="generate_content_async")
def generate_content_task(request_dict: dict):
    """
    Async task to generate content in the background using Celery.
    """
    try:
        from services.workflows.config import ContentGenerationRequest
        
        # Convert dict to request object
        request = ContentGenerationRequest(**request_dict)
        
        # Run async workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        orchestrator = ExerciseOrchestrator()
        result = loop.run_until_complete(orchestrator.run({"request": request}))
        
        loop.close()
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# Use in endpoint:
# from workers.content_tasks import generate_content_task
# 
# @content_router.post("/generate-async")
# async def generate_async(request: ContentGenerationRequest):
#     task = generate_content_task.delay(request.dict())
#     return {"task_id": task.id, "status": "processing"}


# ============================================================================
# WEBSOCKET ENDPOINT FOR REAL-TIME GENERATION UPDATES (Optional)
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect


@content_router.websocket("/ws/generate/{student_id}")
async def websocket_generate(websocket: WebSocket, student_id: str):
    """
    WebSocket endpoint for real-time content generation updates.
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive generation request
            data = await websocket.receive_json()
            
            # Extract request data
            topic = data.get("topic")
            subtopics = data.get("subtopics", [])
            content_types = data.get("content_types", ["flashcard"])
            
            # Create request
            from services.workflows.config import StudentProfile, ContentLevel
            
            student = StudentProfile(
                student_id=student_id,
                name="WebSocket User",
                subject=data.get("subject", ""),
                current_level=ContentLevel.INTERMEDIATE,
                learning_style="visual",
                knowledge_gaps=data.get("gaps", []),
                strengths=data.get("strengths", []),
                learning_pace="normal",
                preferred_content_types=[],
            )
            
            request = ContentGenerationRequest(
                student_profile=student,
                topic=topic,
                subtopics=subtopics,
                learning_objectives=data.get("objectives", []),
                content_types=content_types,
            )
            
            # Send progress update
            await websocket.send_json({"status": "starting", "phase": 1})
            
            # Execute workflow
            orchestrator = ExerciseOrchestrator()
            result = await orchestrator.run({"request": request})
            
            # Send final result
            await websocket.send_json({
                "status": "complete",
                "data": result
            })
            
    except WebSocketDisconnect:
        print(f"Client {student_id} disconnected")
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
        await websocket.close(code=1000)


# ============================================================================
# TESTING SCRIPT
# ============================================================================

async def test_workflow():
    """Test the workflow directly"""
    from services.workflows.utils import create_student_profile, create_content_generation_request
    
    # Create test data
    student = create_student_profile(
        student_id="test_001",
        name="Test Student",
        subject="Chemistry",
        current_level="intermediate",
        learning_style="visual",
        knowledge_gaps=["Organic Chemistry"],
        strengths=["Inorganic Chemistry"],
    )
    
    request = create_content_generation_request(
        student_profile=student,
        topic="Bonding",
        subtopics=["Ionic", "Covalent", "Metallic"],
        learning_objectives=["Understand bonding", "Predict structures"],
        content_types=["flashcard", "quiz"],
    )
    
    # Execute
    orchestrator = ExerciseOrchestrator()
    result = await orchestrator.run({"request": request})
    
    print(f"Success: {result['success']}")
    print(f"Content items: {len(result['generated_content'])}")
    print(f"Quality score: {result['quality_metrics']['average_quality_score']:.2f}")
    
    return result


# Run tests:
# if __name__ == "__main__":
#     import asyncio
#     result = asyncio.run(test_workflow())
