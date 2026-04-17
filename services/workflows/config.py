"""
Workflow configuration and constants
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ContentLevel(str, Enum):
    """Student proficiency levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ContentType(str, Enum):
    """Types of educational content"""
    FLASHCARD = "flashcard"
    MINDMAP = "mindmap"
    QUIZ = "quiz"
    LESSON = "lesson"
    CODING_TASK = "coding_task"


@dataclass
class StudentProfile:
    """Student capability profile"""
    student_id: str
    name: str
    subject: str
    current_level: ContentLevel
    learning_style: str  # visual, auditory, kinesthetic, reading/writing
    knowledge_gaps: list[str]
    strengths: list[str]
    learning_pace: str  # slow, normal, fast
    preferred_content_types: list[ContentType]
    daily_study_time_minutes: int = 30
    
    
@dataclass
class ContentGenerationRequest:
    """Request to generate educational content"""
    student_profile: StudentProfile
    topic: str
    subtopics: list[str]
    learning_objectives: list[str]
    content_types: list[ContentType]
    difficulty_level: Optional[ContentLevel] = None
    max_items: int = 10
    quiz_question_types: Optional[list[str]] = None


@dataclass
class GeneratedContent:
    """Generated content metadata"""
    content_type: ContentType
    title: str
    content: str  # JSON serialized content
    student_id: str
    topic: str
    difficulty_level: ContentLevel
    estimated_time_minutes: int
    quality_score: float  # 0.0 - 1.0


# Workflow configuration
WORKFLOW_CONFIG = {
    "max_parallel_agents": 3,
    "request_timeout_seconds": 60,
    "retry_attempts": 3,
    "cache_enabled": True,
    "cache_ttl_minutes": 60,
}

# Agent-specific timeouts
AGENT_TIMEOUTS = {
    "persona": 10,
    "flashcard_creator": 20,
    "mindmap_creator": 25,
    "quiz_creator": 30,
    "lesson_creator": 40,
    "coding_task_creator": 35,
}

# Content quality thresholds
QUALITY_THRESHOLDS = {
    "min_score": 0.7,
    "retry_if_below": 0.6,
}
