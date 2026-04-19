"""
FlashcardCreatorAgent: Creates interactive flashcards for spaced repetition learning

Responsibilities:
- Generate question-answer pairs
- Optimize for FSRS (Free Spaced Repetition System)
- Create mnemonic aids and memory cues
"""

from typing import Any, Dict, List
import logging
from ..base import BaseAgent
from ..config import ContentLevel
from ..utils.grounding import (
    extract_focus_terms,
    extract_keywords,
    prioritize_phrase_matches,
    select_relevant_sentences,
    unique_preserve_order,
)

logger = logging.getLogger(__name__)


class FlashcardCreatorAgent(BaseAgent):
    """
    Creates flashcards optimized for spaced repetition learning (FSRS).
    """
    
    def __init__(self):
        super().__init__(name="FlashcardCreatorAgent", timeout=20)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate flashcards based on topic and student profile.
        
        Input:
            - topic: str
            - subtopics: list[str]
            - difficulty: ContentLevel
            - learning_objectives: list[str]
            - max_cards: int (default 10)
            - learning_style: str
            - content_customization: dict
            
        Output:
            - flashcards: list[dict] - each with question, answer, hints, memory_cue
            - fsrs_data: dict - initial FSRS parameters
            - quality_score: float
        """
        topic = input_data.get("topic", "")
        subtopics = input_data.get("subtopics", [])
        difficulty = input_data.get("difficulty", ContentLevel.INTERMEDIATE)
        learning_objectives = input_data.get("learning_objectives", [])
        max_cards = input_data.get("max_cards", 10)
        learning_style = input_data.get("learning_style", "visual")
        customization = input_data.get("content_customization", {})
        source_context = input_data.get("source_context", "")
        subtopics = unique_preserve_order(subtopics or [topic])
        
        # Generate flashcards
        flashcards = await self._generate_flashcards(
            topic=topic,
            subtopics=subtopics,
            difficulty=difficulty,
            max_cards=max_cards,
            learning_objectives=learning_objectives,
            source_context=source_context,
        )
        
        # Optimize for each learning style
        flashcards = await self._optimize_for_learning_style(
            flashcards=flashcards,
            learning_style=learning_style
        )
        
        # Add memory aids and hints
        flashcards = await self._enhance_with_mnemonics(
            flashcards=flashcards,
            customization=customization
        )
        
        # Calculate quality score
        quality_score = await self._calculate_quality_score(flashcards)
        
        # Initialize FSRS parameters
        fsrs_data = await self._initialize_fsrs_parameters()
        
        return {
            "flashcards": flashcards,
            "total_cards": len(flashcards),
            "fsrs_data": fsrs_data,
            "quality_score": quality_score,
            "difficulty_level": difficulty,
            "topic": topic,
        }
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input"""
        required_fields = ["topic", "subtopics", "difficulty"]
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        return True
    
    async def _generate_flashcards(self, topic: str, subtopics: List[str],
                                  difficulty: ContentLevel, max_cards: int,
                                  learning_objectives: List[str],
                                  source_context: str) -> List[Dict[str, Any]]:
        """
        Generate flashcard questions and answers.
        Strategy varies by difficulty level.
        """
        flashcards = []
        cards_per_subtopic = max(1, max_cards // len(subtopics)) if subtopics else max_cards
        seen_questions: set[str] = set()
        question_stems = [
            "What is the main idea behind {subtopic}?",
            "Why does {subtopic} matter in {topic}?",
            "How does the lesson describe {subtopic}?",
            "What practical takeaway should you remember about {subtopic}?",
        ]
        
        for subtopic in subtopics:
            source_support = select_relevant_sentences(
                source_context,
                extract_keywords(subtopic, topic, *learning_objectives),
                limit=max(4, cards_per_subtopic + 2),
            )
            source_support = prioritize_phrase_matches(
                source_support,
                subtopic,
                limit=max(2, cards_per_subtopic + 1),
            )
            for i in range(cards_per_subtopic):
                if len(flashcards) >= max_cards:
                    break
                
                reference_sentence = source_support[i % len(source_support)] if source_support else ""
                question = question_stems[i % len(question_stems)].format(subtopic=subtopic, topic=topic)
                if difficulty == ContentLevel.ADVANCED and i % 2 == 1:
                    question = f"Which nuance or trade-off in {subtopic} should an advanced learner remember?"
                elif difficulty == ContentLevel.BEGINNER and i % 2 == 0:
                    question = f"What should a beginner understand first about {subtopic}?"
                
                answer = await self._generate_answer(
                    subtopic=subtopic,
                    difficulty=difficulty,
                    reference_sentence=reference_sentence,
                    learning_objectives=learning_objectives,
                )

                signature = question.casefold()
                if signature in seen_questions:
                    continue
                seen_questions.add(signature)
                
                flashcards.append({
                    "id": len(flashcards) + 1,
                    "subtopic": subtopic,
                    "question": question,
                    "answer": answer,
                    "difficulty": difficulty,
                    "hints": [],  # Will be filled by enhance_with_mnemonics
                    "memory_cue": "",
                    "type": self._determine_card_type(question),
                })
        
        return flashcards[:max_cards]
    
    async def _generate_answer(self, subtopic: str,
                             difficulty: ContentLevel,
                             reference_sentence: str,
                             learning_objectives: List[str]) -> str:
        """Generate an appropriate answer"""
        if reference_sentence:
            base_answer = reference_sentence
        else:
            base_answer = learning_objectives[0] if learning_objectives else f"Key idea about {subtopic}"

        if difficulty == ContentLevel.BEGINNER:
            return f"Simple explanation: {base_answer}"
        elif difficulty == ContentLevel.INTERMEDIATE:
            return f"Detailed explanation: {base_answer}"
        else:
            return f"Advanced analysis: {base_answer} Consider the assumptions, trade-offs, and when it breaks down."
    
    def _determine_card_type(self, question: str) -> str:
        """Determine the type of flashcard"""
        if "what" in question.lower() or "define" in question.lower():
            return "definition"
        elif "example" in question.lower():
            return "example"
        elif "compare" in question.lower():
            return "comparison"
        elif "why" in question.lower():
            return "conceptual"
        else:
            return "application"
    
    async def _optimize_for_learning_style(self, flashcards: List[Dict],
                                          learning_style: str) -> List[Dict]:
        """
        Enhance flashcards for specific learning styles
        """
        for card in flashcards:
            if learning_style == "visual":
                card["suggested_visual"] = "Include diagram or image"
            elif learning_style == "auditory":
                card["pronunciation"] = f"How to pronounce: {card['question']}"
                card["related_sounds"] = "Include phonetic patterns"
            elif learning_style == "kinesthetic":
                card["action"] = "Try doing this: ..."
                card["interactive_element"] = "Include hands-on practice"
            elif learning_style == "reading/writing":
                card["detailed_explanation"] = card["answer"]
                card["related_reading"] = "Additional reading materials"
        
        return flashcards
    
    async def _enhance_with_mnemonics(self, flashcards: List[Dict],
                                     customization: Dict[str, Any]) -> List[Dict]:
        """
        Add memory aids and mnemonic devices
        """
        for card in flashcards:
            focus_terms = extract_focus_terms(card["answer"], [card["subtopic"]], limit=3)
            # Create hints
            hint_source = focus_terms or [card["subtopic"], "main idea", "evidence"]
            card["hints"] = [
                f"Hint 1: Focus on {hint_source[0]}",
                f"Hint 2: Connect it back to {card['subtopic']}",
                f"Hint 3: Recall the strongest evidence from the lesson",
            ]
            
            # Create memory cue
            mnemonics = self._generate_mnemonic(card["question"])
            card["memory_cue"] = mnemonics
            card["mnemonic_type"] = "acronym" if len(mnemonics) < 20 else "story"
        
        return flashcards
    
    def _generate_mnemonic(self, question: str) -> str:
        """Generate a mnemonic or memory cue"""
        # Simplified mnemonic generation
        words = question.split()
        if len(words) >= 2:
            return "".join([word[0].upper() for word in words[:3]])
        return "MEM"
    
    async def _calculate_quality_score(self, flashcards: List[Dict]) -> float:
        """
        Calculate quality score based on card characteristics
        Range: 0.0 to 1.0
        """
        if not flashcards:
            return 0.0
        
        score = 0.0
        checks = 0
        
        for card in flashcards:
            # Check if has question and answer
            if card.get("question") and card.get("answer"):
                score += 0.25
            # Check if has difficulty
            if card.get("difficulty"):
                score += 0.25
            # Check if has memory cue
            if card.get("memory_cue"):
                score += 0.25
            # Check if has hints
            if card.get("hints"):
                score += 0.25
        
        avg_score = score / (len(flashcards) * 4) if flashcards else 0.0
        return min(1.0, avg_score)
    
    async def _initialize_fsrs_parameters(self) -> Dict[str, Any]:
        """
        Initialize Free Spaced Repetition System (FSRS) parameters
        These will be used for review scheduling
        """
        return {
            "stability": 0.5,
            "difficulty": 0.5,
            "reps": 0,
            "lapses": 0,
            "last_review": None,
            "due_date": None,
            "interval": 1,  # days until next review
            "ease_factor": 2.5,
        }
