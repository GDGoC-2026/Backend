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
from ..utils.grounding import (
    extract_focus_terms,
    extract_keywords,
    prioritize_phrase_matches,
    replace_first_case_insensitive,
    select_relevant_sentences,
    unique_preserve_order,
)

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
        source_context = input_data.get("source_context", "")
        subtopics = unique_preserve_order(subtopics or [topic])
        
        # Generate questions
        questions = await self._generate_questions(
            topic=topic,
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            difficulty=difficulty,
            max_questions=max_questions,
            question_types=question_types,
            source_context=source_context,
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
                                 question_types: List[str],
                                 source_context: str) -> List[Dict[str, Any]]:
        """Generate questions across different types"""
        questions: List[Dict[str, Any]] = []
        normalized_types = unique_preserve_order(question_types) or [
            "multiple_choice",
            "fill_blank",
            "true_false",
        ]
        subtopics = unique_preserve_order(subtopics or [topic])
        seen_signatures: set[str] = set()
        attempts = 0
        max_attempts = max_questions * max(4, len(normalized_types) * 2)

        sentence_bank = {
            subtopic: prioritize_phrase_matches(
                select_relevant_sentences(
                    source_context,
                    extract_keywords(subtopic, topic, *learning_objectives),
                    limit=max(6, max_questions + 2),
                ),
                subtopic,
                limit=max(4, max_questions),
            )
            for subtopic in subtopics
        }

        all_sentences = unique_preserve_order(
            sentence for sentences in sentence_bank.values() for sentence in sentences
        )

        while len(questions) < max_questions and attempts < max_attempts:
            qtype = normalized_types[attempts % len(normalized_types)]
            subtopic = subtopics[attempts % len(subtopics)] if subtopics else topic
            reference_pool = sentence_bank.get(subtopic) or all_sentences
            reference_sentence = (
                reference_pool[(attempts // max(1, len(normalized_types))) % len(reference_pool)]
                if reference_pool
                else ""
            )

            if qtype == "multiple_choice":
                question = await self._create_multiple_choice(
                    topic=topic,
                    subtopic=subtopic,
                    difficulty=difficulty,
                    reference_sentence=reference_sentence,
                    distractor_pool=all_sentences,
                )
            elif qtype == "fill_blank":
                question = await self._create_fill_blank(
                    topic=topic,
                    subtopic=subtopic,
                    difficulty=difficulty,
                    reference_sentence=reference_sentence,
                )
            elif qtype == "true_false":
                question = await self._create_true_false(
                    topic=topic,
                    subtopic=subtopic,
                    difficulty=difficulty,
                    reference_sentence=reference_sentence,
                    alternate_subtopics=subtopics,
                    attempt_index=attempts,
                )
            else:
                attempts += 1
                continue

            signature = f"{question['type']}::{question['question']}".casefold()
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                question["id"] = len(questions) + 1
                question["subtopic"] = subtopic
                questions.append(question)

            attempts += 1
        
        return questions[:max_questions]
    
    async def _create_multiple_choice(self, topic: str, subtopic: str,
                                     difficulty: ContentLevel,
                                     reference_sentence: str,
                                     distractor_pool: List[str]) -> Dict[str, Any]:
        """Create a multiple choice question"""
        num_options = 4 if difficulty == ContentLevel.ADVANCED else 3
        correct_option = (
            reference_sentence
            if reference_sentence
            else f"{subtopic} is a meaningful part of {topic}."
        )
        distractors = [
            sentence
            for sentence in distractor_pool
            if sentence != correct_option and subtopic.casefold() not in sentence.casefold()
        ][: max(0, num_options - 1)]

        generic_distractors = [
            f"{subtopic} has no practical impact in {topic}.",
            f"{subtopic} should always be ignored when studying {topic}.",
            f"{subtopic} only matters in unrelated domains.",
        ]

        options = unique_preserve_order([correct_option, *distractors, *generic_distractors])[:num_options]

        return {
            "type": "multiple_choice",
            "question": f"Which statement best matches the lesson's explanation of {subtopic}?",
            "options": options,
            "correct_answer": 0,
            "explanation": f"The correct answer is grounded in the lesson context for {subtopic}.",
            "difficulty": difficulty,
            "learning_value": "Tests understanding and discrimination between concepts",
        }
    
    async def _create_fill_blank(self, topic: str, subtopic: str,
                                difficulty: ContentLevel,
                                reference_sentence: str) -> Dict[str, Any]:
        """Create a fill-in-the-blank question"""
        focus_terms = extract_focus_terms(reference_sentence, [subtopic, topic], limit=3)
        answer_term = next(
            (
                term
                for term in focus_terms
                if len(term) > 3 and term.casefold() not in {topic.casefold()}
            ),
            subtopic,
        )
        question_text = (
            replace_first_case_insensitive(reference_sentence, answer_term, "___________")
            if reference_sentence and answer_term.casefold() in reference_sentence.casefold()
            else f"In this lesson, {subtopic} is closely connected to ___________."
        )

        return {
            "type": "fill_blank",
            "question": question_text,
            "blank_index": 1,
            "correct_answers": [answer_term],
            "explanation": f"The missing term comes directly from the lesson's description of {subtopic}.",
            "difficulty": difficulty,
            "learning_value": "Tests recall and vocabulary",
        }
    
    async def _create_true_false(self, topic: str, subtopic: str,
                                difficulty: ContentLevel,
                                reference_sentence: str,
                                alternate_subtopics: List[str],
                                attempt_index: int) -> Dict[str, Any]:
        """Create a true/false question"""
        is_true = attempt_index % 2 == 0 or not reference_sentence
        statement = reference_sentence or f"{subtopic} is an important concept in {topic}."

        if not is_true:
            replacement = next(
                (
                    alternate
                    for alternate in alternate_subtopics
                    if alternate.casefold() != subtopic.casefold()
                ),
                "",
            )
            if replacement and subtopic.casefold() in statement.casefold():
                statement = replace_first_case_insensitive(statement, subtopic, replacement)
            else:
                statement = f"The lesson says {subtopic} has no effect on {topic}."

        return {
            "type": "true_false",
            "question": statement,
            "correct_answer": is_true,
            "explanation": (
                "Judge whether the statement matches the grounded lesson context."
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
                "question" in question and bool(question["question"]),
                "type" in question and bool(question["type"]),
                "difficulty" in question,
                "explanation" in question and bool(question["explanation"]),
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
