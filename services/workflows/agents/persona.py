"""
PersonaAgent: Analyzes student profile and adapts content recommendations

Responsibilities:
- Analyze student learning style, pace, and knowledge gaps
- Recommend content types and difficulty levels
- Create personalized learning pathways
"""

from typing import Any, Dict
import logging
from ..base import BaseAgent
from ..config import StudentProfile, ContentLevel, ContentType

logger = logging.getLogger(__name__)


class PersonaAgent(BaseAgent):
    """
    Persona Agent analyzes student capabilities and creates personalized learning profiles.
    This agent is executed first to understand the student context.
    """
    
    def __init__(self):
        super().__init__(name="PersonaAgent", timeout=10)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze student profile and provide recommendations.
        
        Input:
            - student_profile: StudentProfile object
            - topic: str - learning topic
            - subtopics: list[str] - specific subtopics
            - learning_objectives: list[str] - what student should learn
            
        Output:
            - recommended_difficulty: ContentLevel
            - recommended_content_types: list[ContentType]
            - learning_path: list[dict] - step-by-step learning sequence
            - content_customization: dict - specific customizations
            - engagement_strategies: list[str] - strategies to keep student engaged
        """
        student_profile: StudentProfile = input_data.get("student_profile")
        topic = input_data.get("topic", "")
        subtopics = input_data.get("subtopics", [])
        learning_objectives = input_data.get("learning_objectives", [])
        
        # Determine recommended difficulty
        recommended_difficulty = await self._determine_difficulty(
            current_level=student_profile.current_level,
            knowledge_gaps=student_profile.knowledge_gaps,
            subtopics=subtopics
        )
        
        # Recommend content types based on learning style
        recommended_types = await self._recommend_content_types(
            learning_style=student_profile.learning_style,
            preferred_types=student_profile.preferred_content_types,
            topic=topic
        )
        
        # Create learning path
        learning_path = await self._create_learning_path(
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            difficulty=recommended_difficulty,
            pace=student_profile.learning_pace
        )
        
        # Generate customization strategies
        customizations = await self._generate_customizations(
            learning_style=student_profile.learning_style,
            knowledge_gaps=student_profile.knowledge_gaps,
            strengths=student_profile.strengths,
            pace=student_profile.learning_pace
        )
        
        # Engagement strategies
        engagement = await self._engagement_strategies(
            learning_pace=student_profile.learning_pace,
            daily_study_time=student_profile.daily_study_time_minutes
        )
        
        return {
            "student_id": student_profile.student_id,
            "topic": topic,
            "recommended_difficulty": recommended_difficulty,
            "recommended_content_types": recommended_types,
            "learning_path": learning_path,
            "content_customization": customizations,
            "engagement_strategies": engagement,
            "analysis_timestamp": "2024-01-01T00:00:00Z",
        }
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input has required fields"""
        required_fields = ["student_profile", "topic", "subtopics", "learning_objectives"]
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        
        if not isinstance(input_data["student_profile"], StudentProfile):
            raise ValueError("student_profile must be a StudentProfile instance")
        
        return True
    
    async def _determine_difficulty(self, current_level: ContentLevel, 
                                   knowledge_gaps: list[str],
                                   subtopics: list[str]) -> ContentLevel:
        """
        Determine recommended difficulty level based on gaps in subtopics
        """
        # If student has gaps in topics, recommend lower difficulty
        gap_count = len(knowledge_gaps)
        
        if current_level == ContentLevel.BEGINNER:
            # Check if gaps are critical for subtopics
            if gap_count > 2:
                return ContentLevel.BEGINNER
            return ContentLevel.INTERMEDIATE
        elif current_level == ContentLevel.INTERMEDIATE:
            if gap_count > 0:
                return ContentLevel.INTERMEDIATE
            return ContentLevel.ADVANCED
        else:  # ADVANCED
            return ContentLevel.ADVANCED
    
    async def _recommend_content_types(self, learning_style: str,
                                      preferred_types: list[ContentType],
                                      topic: str) -> list[ContentType]:
        """
        Recommend content types based on learning style
        """
        style_mapping = {
            "visual": [ContentType.MINDMAP, ContentType.FLASHCARD, ContentType.LESSON],
            "auditory": [ContentType.LESSON, ContentType.QUIZ, ContentType.QUIZ],
            "kinesthetic": [ContentType.QUIZ, ContentType.FLASHCARD, ContentType.LESSON],
            "reading/writing": [ContentType.LESSON, ContentType.FLASHCARD, ContentType.QUIZ],
        }
        
        recommended = style_mapping.get(learning_style, list(ContentType))
        
        # Prioritize preferred types
        result = list(set(recommended + preferred_types))[:3]
        
        return result
    
    async def _create_learning_path(self, subtopics: list[str],
                                   learning_objectives: list[str],
                                   difficulty: ContentLevel,
                                   pace: str) -> list[Dict[str, Any]]:
        """
        Create a structured learning path with milestones
        """
        path = []
        
        for i, subtopic in enumerate(subtopics, 1):
            path.append({
                "step": i,
                "subtopic": subtopic,
                "difficulty": difficulty,
                "estimated_duration_minutes": 15 if pace == "fast" else (30 if pace == "normal" else 45),
                "objectives": [obj for obj in learning_objectives if subtopic.lower() in obj.lower()][:2],
            })
        
        return path
    
    async def _generate_customizations(self, learning_style: str,
                                       knowledge_gaps: list[str],
                                       strengths: list[str],
                                       pace: str) -> Dict[str, Any]:
        """
        Generate content customization strategies
        """
        return {
            "learning_style": learning_style,
            "focus_on_gaps": knowledge_gaps[:3],  # Top 3 knowledge gaps to focus on
            "leverage_strengths": strengths[:2],  # Use strengths as motivation
            "content_pace": pace,
            "additional_resources": "provide explanations" if knowledge_gaps else "challenge content",
            "example_types": "real-world" if pace == "slow" else "theoretical",
        }
    
    async def _engagement_strategies(self, learning_pace: str, 
                                    daily_study_time: int) -> list[str]:
        """
        Generate engagement strategies based on pace and available time
        """
        strategies = []
        
        if learning_pace == "slow":
            strategies.extend([
                "Break content into smaller chunks (5-10 min each)",
                "Provide step-by-step examples",
                "Include more practice opportunities",
            ])
        elif learning_pace == "fast":
            strategies.extend([
                "Challenge content with advanced problems",
                "Link to related advanced topics",
                "Provide extension materials",
            ])
        else:  # normal
            strategies.extend([
                "Balance theory and practice",
                "Include one complex example",
                "Provide optional deep-dive resources",
            ])
        
        if daily_study_time < 20:
            strategies.append("Prioritize key concepts")
        elif daily_study_time > 60:
            strategies.append("Include comprehensive practice sets")
        
        return strategies
