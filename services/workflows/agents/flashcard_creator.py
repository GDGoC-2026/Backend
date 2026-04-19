"""
FlashcardCreatorAgent: Creates interactive flashcards for spaced repetition learning

Responsibilities:
- Generate question-answer pairs
- Optimize for FSRS (Free Spaced Repetition System)
- Create mnemonic aids and memory cues
"""

from typing import Any, Dict, List
import re
import logging
from ..base import BaseAgent
from ..config import ContentLevel
from ..utils.grounding import (
    extract_focus_terms,
    extract_keywords,
    normalize_text,
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
        flashcards: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()

        question_templates = [
            "definition",
            "importance",
            "application",
            "comparison",
            "misconception",
            "recall",
            "tradeoff",
        ]

        sentence_bank = {
            subtopic: prioritize_phrase_matches(
                select_relevant_sentences(
                    source_context,
                    extract_keywords(subtopic, topic, *learning_objectives),
                    limit=max(8, min(22, max_cards * 2)),
                ),
                subtopic,
                limit=max(6, min(18, max_cards * 2)),
            )
            for subtopic in subtopics
        }

        all_reference_sentences = unique_preserve_order(
            sentence
            for sentences in sentence_bank.values()
            for sentence in sentences
        )

        attempts = 0
        max_attempts = max(12, max_cards * len(question_templates) * 3)

        while len(flashcards) < max_cards and attempts < max_attempts:
            subtopic = subtopics[attempts % len(subtopics)] if subtopics else topic
            template_name = question_templates[(attempts // max(1, len(subtopics))) % len(question_templates)]

            references = sentence_bank.get(subtopic) or all_reference_sentences
            reference_sentence = (
                references[(attempts // max(1, len(question_templates))) % len(references)]
                if references
                else ""
            )

            question = self._compose_question(
                template_name=template_name,
                subtopic=subtopic,
                topic=topic,
                difficulty=difficulty,
            )

            answer = await self._generate_answer(
                subtopic=subtopic,
                topic=topic,
                difficulty=difficulty,
                reference_sentence=reference_sentence,
                learning_objectives=learning_objectives,
                template_name=template_name,
            )

            strict_signature = f"{normalize_text(question).casefold()}::{normalize_text(answer).casefold()}"
            if strict_signature in seen_signatures:
                attempts += 1
                continue

            if self._is_near_duplicate_card(question, answer, flashcards):
                attempts += 1
                continue

            seen_signatures.add(strict_signature)

            flashcards.append(
                {
                    "id": len(flashcards) + 1,
                    "subtopic": subtopic,
                    "question": question,
                    "answer": answer,
                    "difficulty": difficulty,
                    "hints": [],
                    "memory_cue": "",
                    "type": self._determine_card_type(question),
                    "template": template_name,
                }
            )

            attempts += 1

        return flashcards[:max_cards]
    
    def _compose_question(
        self,
        *,
        template_name: str,
        subtopic: str,
        topic: str,
        difficulty: ContentLevel,
    ) -> str:
        templates = {
            "definition": f"How would you define {subtopic} in the context of {topic}?",
            "importance": f"Why is {subtopic} important when learning {topic}?",
            "application": f"How can {subtopic} be applied in a practical {topic} scenario?",
            "comparison": f"How is {subtopic} different from related ideas in {topic}?",
            "misconception": f"What is a common misconception about {subtopic}?",
            "recall": f"Which key fact about {subtopic} should you remember for {topic}?",
            "tradeoff": f"What trade-off should you consider when using {subtopic}?",
        }

        question = templates.get(template_name, templates["definition"])

        if difficulty == ContentLevel.BEGINNER and template_name in {"tradeoff", "comparison"}:
            question = f"What should a beginner understand first about {subtopic}?"
        elif difficulty == ContentLevel.ADVANCED and template_name in {"definition", "recall"}:
            question = f"Which nuanced detail of {subtopic} is most important for advanced study?"

        return question

    async def _generate_answer(self, subtopic: str,
                             topic: str,
                             difficulty: ContentLevel,
                             reference_sentence: str,
                             learning_objectives: List[str],
                             template_name: str) -> str:
        """Generate an appropriate answer"""
        base_answer = reference_sentence or (
            learning_objectives[0] if learning_objectives else f"Key idea about {subtopic}"
        )
        base_answer = normalize_text(base_answer)

        focus_terms = extract_focus_terms(
            base_answer,
            [subtopic, topic, *learning_objectives],
            limit=4,
        )
        support_term = focus_terms[0] if focus_terms else subtopic
        contrast_term = focus_terms[1] if len(focus_terms) > 1 else "nearby concepts"

        if template_name == "misconception":
            detail = f"A frequent mistake is to oversimplify {subtopic}; instead, connect it to {support_term}."
        elif template_name == "comparison":
            detail = f"Compare {subtopic} against {contrast_term} to spot when each approach fits best."
        elif template_name == "tradeoff":
            detail = f"Weigh the benefit of {support_term} against potential limitations in real use."
        elif template_name == "application":
            detail = f"Apply {subtopic} by mapping the concept to a concrete task and checking outcomes."
        else:
            detail = f"Anchor your understanding on {support_term} and revisit supporting evidence."

        if difficulty == ContentLevel.BEGINNER:
            return f"Simple explanation: {base_answer} {detail}"
        if difficulty == ContentLevel.INTERMEDIATE:
            return f"Detailed explanation: {base_answer} {detail}"
        return (
            f"Advanced analysis: {base_answer} {detail} "
            "Also consider assumptions, edge cases, and failure modes."
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9]{3,}", text or "")
        }

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _is_near_duplicate_card(
        self,
        question: str,
        answer: str,
        existing_cards: List[Dict[str, Any]],
    ) -> bool:
        question_tokens = self._tokenize(question)
        answer_tokens = self._tokenize(answer)

        for card in existing_cards:
            existing_question_tokens = self._tokenize(str(card.get("question", "")))
            existing_answer_tokens = self._tokenize(str(card.get("answer", "")))

            question_similarity = self._jaccard(question_tokens, existing_question_tokens)
            answer_similarity = self._jaccard(answer_tokens, existing_answer_tokens)

            if question_similarity >= 0.8:
                return True
            if question_similarity >= 0.62 and answer_similarity >= 0.75:
                return True

        return False
    
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
