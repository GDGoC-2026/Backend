"""
QuizCreatorAgent: Creates interactive quizzes to assess understanding

Responsibilities:
- Generate multiple choice, fill-in-the-blank, and true/false questions
- Adaptive difficulty based on topic and student level
- Include explanations for correct and incorrect answers
"""

from typing import Any, Dict, List
import logging
from ..base import BaseAgent
from ..config import ContentLevel

logger = logging.getLogger(__name__)


class QuizCreatorAgent(BaseAgent):
    """
    Creates interactive quizzes to assess student understanding and reinforce learning.
    """
    
    def __init__(self):
        super().__init__(name="QuizCreatorAgent", timeout=30)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate quiz questions and structure.
        
        Input:
            - topic: str
            - subtopics: list[str]
            - learning_objectives: list[str]
            - difficulty: ContentLevel
            - max_questions: int (default 10)
            - question_types: list[str] (multiple_choice, fill_blank, true_false)
            
        Output:
            - quiz: dict - complete quiz structure
            - questions: list[dict] - all quiz questions
            - difficulty_distribution: dict
            - estimated_duration_minutes: int
            - quality_score: float
        """
        topic = input_data.get("topic", "")
        subtopics = input_data.get("subtopics", [])
        learning_objectives = input_data.get("learning_objectives", [])
        difficulty = input_data.get("difficulty", ContentLevel.INTERMEDIATE)
        max_questions = input_data.get("max_questions", 10)
        question_types = input_data.get("question_types", 
                                       ["multiple_choice", "fill_blank", "true_false"])
        
        # Generate questions
        questions = await self._generate_questions(
            topic=topic,
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            difficulty=difficulty,
            max_questions=max_questions,
            question_types=question_types
        )
        
        # Create quiz structure
        quiz_structure = await self._create_quiz_structure(
            topic=topic,
            questions=questions,
            difficulty=difficulty
        )
        
        # Calculate difficulty distribution
        difficulty_dist = await self._calculate_difficulty_distribution(questions)
        
        # Estimate duration
        duration = len(questions) * 2  # ~2 min per question average
        
        # Calculate quality
        quality_score = await self._calculate_quality_score(questions)
        
        return {
            "topic": topic,
            "quiz": quiz_structure,
            "questions": questions,
            "total_questions": len(questions),
            "question_types": list(set([q["type"] for q in questions])),
            "difficulty_distribution": difficulty_dist,
            "estimated_duration_minutes": duration,
            "quality_score": quality_score,
            "difficulty": difficulty,
        }
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input"""
        required_fields = ["topic", "subtopics", "difficulty"]
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        return True
    
    async def _generate_questions(self, topic: str, subtopics: List[str],
                                 learning_objectives: List[str],
                                 difficulty: ContentLevel,
                                 max_questions: int,
                                 question_types: List[str]) -> List[Dict[str, Any]]:
        """Generate questions across different types"""
        questions = []
        questions_per_type = max(1, max_questions // len(question_types))
        
        for qtype in question_types:
            for i in range(questions_per_type):
                if len(questions) >= max_questions:
                    break
                
                # Select subtopic
                subtopic = subtopics[i % len(subtopics)] if subtopics else topic
                
                if qtype == "multiple_choice":
                    question = await self._create_multiple_choice(
                        topic=topic,
                        subtopic=subtopic,
                        difficulty=difficulty
                    )
                elif qtype == "fill_blank":
                    question = await self._create_fill_blank(
                        topic=topic,
                        subtopic=subtopic,
                        difficulty=difficulty
                    )
                elif qtype == "true_false":
                    question = await self._create_true_false(
                        topic=topic,
                        subtopic=subtopic,
                        difficulty=difficulty
                    )
                else:
                    continue
                
                question["id"] = len(questions) + 1
                question["subtopic"] = subtopic
                questions.append(question)
        
        return questions[:max_questions]
    
    async def _create_multiple_choice(self, topic: str, subtopic: str,
                                     difficulty: ContentLevel) -> Dict[str, Any]:
        """Create a multiple choice question"""
        num_options = 4 if difficulty == ContentLevel.ADVANCED else 3
        
        return {
            "type": "multiple_choice",
            "question": f"Which of the following best describes {subtopic}?",
            "options": [
                f"Option A - Correct answer about {subtopic}",
                f"Option B - Common misconception",
                f"Option C - Related but incorrect",
            ] + (["Option D - Distractor"] if num_options == 4 else []),
            "correct_answer": 0,
            "explanation": f"The correct answer is A because...",
            "difficulty": difficulty,
            "learning_value": "Tests understanding and discrimination between concepts",
        }
    
    async def _create_fill_blank(self, topic: str, subtopic: str,
                                distance: ContentLevel) -> Dict[str, Any]:
        """Create a fill-in-the-blank question"""
        return {
            "type": "fill_blank",
            "question": f"The key concept in {subtopic} is _________.",
            "blank_index": 1,
            "correct_answers": ["fundamental principle", "core concept"],
            "explanation": f"The blank should be filled with a fundamental principle because...",
            "difficulty": distance,
            "learning_value": "Tests recall and vocabulary",
        }
    
    async def _create_true_false(self, topic: str, subtopic: str,
                                difficulty: ContentLevel) -> Dict[str, Any]:
        """Create a true/false question"""
        return {
            "type": "true_false",
            "question": f"{subtopic} is a fundamental concept in {topic}.",
            "correct_answer": True,
            "explanation": (
                f"This is TRUE because {subtopic} is indeed fundamental. "
                "Common misconception: students might think it's secondary."
            ),
            "difficulty": difficulty,
            "learning_value": "Tests conceptual understanding and common misconceptions",
        }
    
    async def _create_quiz_structure(self, topic: str, questions: List[Dict],
                                    difficulty: ContentLevel) -> Dict[str, Any]:
        """Create the overall quiz structure"""
        return {
            "title": f"{topic} Assessment Quiz",
            "description": f"Assess your understanding of {topic} ({difficulty})",
            "total_questions": len(questions),
            "passing_score": 70,  # 70% required to pass
            "estimated_time_minutes": len(questions) * 2,
            "question_order": "sequential",  # or "random"
            "show_feedback": True,
            "show_explanations": True,
            "allow_review": True,
        }
    
    async def _calculate_difficulty_distribution(self, questions: List[Dict]) -> Dict[str, int]:
        """Calculate how many questions at each difficulty level"""
        distribution = {
            ContentLevel.BEGINNER: 0,
            ContentLevel.INTERMEDIATE: 0,
            ContentLevel.ADVANCED: 0,
        }
        
        for question in questions:
            diff = question.get("difficulty", ContentLevel.INTERMEDIATE)
            if diff in distribution:
                distribution[diff] += 1
        
        return distribution
    
    async def _calculate_quality_score(self, questions: List[Dict]) -> float:
        """Calculate quiz quality"""
        if not questions:
            return 0.0
        
        score = 0.0
        
        for question in questions:
            # Check required fields
            quality_checks = [
                "question" in question and question["question"],
                "type" in question and question["type"],
                "difficulty" in question,
                "explanation" in question and question["explanation"],
            ]
            
            # Type-specific checks
            if question["type"] == "multiple_choice":
                quality_checks.extend([
                    "options" in question and len(question["options"]) >= 3,
                    "correct_answer" in question,
                ])
            elif question["type"] == "true_false":
                quality_checks.extend([
                    "correct_answer" in question,
                ])
            elif question["type"] == "fill_blank":
                quality_checks.extend([
                    "blank_index" in question,
                    "correct_answers" in question and isinstance(question["correct_answers"], list),
                ])
            
            score += sum(quality_checks) / len(quality_checks)
        
        avg_score = score / len(questions)
        return min(1.0, max(0.0, avg_score))
