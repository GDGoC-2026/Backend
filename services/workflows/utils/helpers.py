"""
Utility functions and helpers for the workflow system
"""

import json
from typing import Any, Dict, List
from ..config import StudentProfile, ContentGenerationRequest, ContentLevel, ContentType


def create_student_profile(
    student_id: str,
    name: str,
    subject: str,
    current_level: str,
    learning_style: str,
    knowledge_gaps: List[str],
    strengths: List[str],
    learning_pace: str = "normal",
    daily_study_time_minutes: int = 30,
    preferred_content_types: List[str] | None = None
) -> StudentProfile:
    """
    Helper function to create a StudentProfile object.
    
    Args:
        student_id: Unique student identifier
        name: Student name
        subject: Subject/domain area
        current_level: "beginner", "intermediate", or "advanced"
        learning_style: "visual", "auditory", "kinesthetic", or "reading/writing"
        knowledge_gaps: List of topics student needs to improve
        strengths: List of topics student excels in
        learning_pace: "slow", "normal", or "fast"
        daily_study_time_minutes: Daily available study time
        preferred_content_types: List of preferred content types
        
    Returns:
        StudentProfile object
    """
    content_types = []
    if preferred_content_types:
        content_types = [
            ContentType(ct) if isinstance(ct, str) else ct
            for ct in preferred_content_types
        ]
    
    return StudentProfile(
        student_id=student_id,
        name=name,
        subject=subject,
        current_level=ContentLevel(current_level),
        learning_style=learning_style,
        knowledge_gaps=knowledge_gaps,
        strengths=strengths,
        learning_pace=learning_pace,
        preferred_content_types=content_types,
        daily_study_time_minutes=daily_study_time_minutes,
    )


def create_content_generation_request(
    student_profile: StudentProfile,
    topic: str,
    subtopics: List[str],
    learning_objectives: List[str],
    content_types: List[str],
    difficulty_level: str | None = None,
    max_items: int = 10,
    quiz_question_types: List[str] | None = None,
) -> ContentGenerationRequest:
    """
    Helper function to create a ContentGenerationRequest object.
    
    Args:
        student_profile: StudentProfile object
        topic: Main learning topic
        subtopics: Specific subtopics to cover
        learning_objectives: Learning goals/objectives
        content_types: Types of content to generate ("flashcard", "mindmap", "quiz", "lesson")
        difficulty_level: Override difficulty (default: from persona analysis)
        max_items: Maximum items per content type
        quiz_question_types: Optional quiz question types (multiple_choice, fill_blank, true_false)
        
    Returns:
        ContentGenerationRequest object
    """
    parsed_content_types = [
        ContentType(ct) if isinstance(ct, str) else ct
        for ct in content_types
    ]
    
    difficulty = ContentLevel(difficulty_level) if difficulty_level else None
    
    return ContentGenerationRequest(
        student_profile=student_profile,
        topic=topic,
        subtopics=subtopics,
        learning_objectives=learning_objectives,
        content_types=parsed_content_types,
        difficulty_level=difficulty,
        max_items=max_items,
        quiz_question_types=quiz_question_types,
    )


def format_content_for_output(content: Dict[str, Any]) -> str:
    """
    Format generated content for display/storage.
    
    Args:
        content: Generated content dictionary
        
    Returns:
        JSON string formatted for output
    """
    return json.dumps(content, indent=2, default=str)


def validate_workflow_input(request: ContentGenerationRequest) -> bool:
    """
    Validate workflow request completeness and correctness.
    
    Args:
        request: ContentGenerationRequest to validate
        
    Returns:
        True if valid, raises ValueError otherwise
    """
    if not request.student_profile:
        raise ValueError("Student profile is required")
    
    if not request.topic:
        raise ValueError("Topic is required")
    
    if not request.subtopics:
        raise ValueError("At least one subtopic is required")
    
    if not request.learning_objectives:
        raise ValueError("At least one learning objective is required")
    
    if not request.content_types:
        raise ValueError("At least one content type must be requested")
    
    # Validate content types
    valid_types = {ct.value for ct in ContentType}
    for ct in request.content_types:
        if ct.value not in valid_types:
            raise ValueError(f"Invalid content type: {ct.value}")
    
    return True


def extract_content_by_type(generated_content: List[Dict], content_type: str) -> List[Dict]:
    """
    Extract specific content type from generated content list.
    
    Args:
        generated_content: List of GeneratedContent objects (as dicts)
        content_type: Type to filter by ("flashcard", "mindmap", "quiz", "lesson")
        
    Returns:
        List of content matching the type
    """
    return [c for c in generated_content if c.get("content_type") == content_type]


def calculate_average_quality_score(generated_content: List[Dict]) -> float:
    """
    Calculate average quality score across all generated content.
    
    Args:
        generated_content: List of GeneratedContent objects (as dicts)
        
    Returns:
        Average quality score (0.0 - 1.0)
    """
    if not generated_content:
        return 0.0
    
    total_score = sum(c.get("quality_score", 0.0) for c in generated_content)
    return total_score / len(generated_content)


def get_content_statistics(generated_content: List[Dict]) -> Dict[str, Any]:
    """
    Get statistics about the generated content.
    
    Args:
        generated_content: List of GeneratedContent objects (as dicts)
        
    Returns:
        Dictionary with statistics
    """
    if not generated_content:
        return {
            "total_items": 0,
            "by_type": {},
            "average_quality": 0.0,
            "total_estimated_time": 0,
        }
    
    stats = {
        "total_items": len(generated_content),
        "by_type": {},
        "average_quality": calculate_average_quality_score(generated_content),
        "total_estimated_time": sum(
            c.get("estimated_time_minutes", 0) for c in generated_content
        ),
        "difficulty_distribution": {},
    }
    
    # Count by type and difficulty
    for content in generated_content:
        ct = content.get("content_type", "unknown")
        if ct not in stats["by_type"]:
            stats["by_type"][ct] = 0
        stats["by_type"][ct] += 1
        
        diff = str(content.get("difficulty_level", "unknown"))
        if diff not in stats["difficulty_distribution"]:
            stats["difficulty_distribution"][diff] = 0
        stats["difficulty_distribution"][diff] += 1
    
    return stats
