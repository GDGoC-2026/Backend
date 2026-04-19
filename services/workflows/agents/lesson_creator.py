"""
LessonCreatorAgent: Creates comprehensive lessons and learning modules

Responsibilities:
- Write structured lesson content
- Include examples, case studies, and real-world applications
- Organize content with clear learning progression
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


class LessonCreatorAgent(BaseAgent):
    """
    Creates comprehensive lessons with structured content,
    examples, and progression suitable for different learning levels.
    """
    
    def __init__(self):
        super().__init__(name="LessonCreatorAgent", timeout=40)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive lesson content.
        
        Input:
            - topic: str
            - subtopics: list[str]
            - learning_objectives: list[str]
            - difficulty: ContentLevel
            - lesson_style: str (narrative, structured, mixed)
            - include_examples: bool
            - include_case_studies: bool
            
        Output:
            - lesson: dict - complete lesson structure
            - sections: list[dict] - lesson sections
            - learning_resources: list[str]
            - estimated_duration_minutes: int
            - quality_score: float
        """
        topic = input_data.get("topic", "")
        subtopics = input_data.get("subtopics", [])
        learning_objectives = input_data.get("learning_objectives", [])
        difficulty = input_data.get("difficulty", ContentLevel.INTERMEDIATE)
        lesson_style = input_data.get("lesson_style", "structured")
        include_examples = input_data.get("include_examples", True)
        include_case_studies = input_data.get("include_case_studies", True)
        prompt = input_data.get("prompt", "")
        source_context = input_data.get("source_context", "")
        source_materials = input_data.get("source_materials", [])
        subtopics = unique_preserve_order(subtopics or [topic])
        
        # Create lesson structure
        lesson = await self._create_lesson_structure(
            topic=topic,
            difficulty=difficulty,
            learning_objectives=learning_objectives,
            prompt=prompt,
            source_context=source_context,
            subtopics=subtopics,
        )
        
        # Create sections
        sections = await self._create_lesson_sections(
            topic=topic,
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            difficulty=difficulty,
            lesson_style=lesson_style,
            prompt=prompt,
            source_context=source_context,
        )
        
        # Add examples if requested
        if include_examples:
            sections = await self._add_examples_to_sections(
                sections=sections,
                topic=topic,
                difficulty=difficulty,
                source_context=source_context,
            )
        
        # Add case studies if requested
        if include_case_studies:
            sections = await self._add_case_studies(
                sections=sections,
                topic=topic,
                difficulty=difficulty,
                source_context=source_context,
            )
        
        # Create resource list
        resources = await self._create_resource_list(topic, subtopics, difficulty, source_materials)
        
        # Estimate duration
        duration = len(sections) * 20  # ~20 min per section
        
        # Calculate quality
        quality_score = await self._calculate_quality_score(sections)
        
        # Add sections to lesson
        lesson["sections"] = sections
        
        return {
            "lesson": lesson,
            "sections": sections,
            "total_sections": len(sections),
            "learning_resources": resources,
            "estimated_duration_minutes": duration,
            "lesson_style": lesson_style,
            "quality_score": quality_score,
            "difficulty": difficulty,
        }
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input"""
        required_fields = ["topic", "subtopics"]
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        return True
    
    async def _create_lesson_structure(
        self,
        topic: str,
        difficulty: ContentLevel,
        learning_objectives: List[str],
        prompt: str,
        source_context: str,
        subtopics: List[str],
    ) -> Dict[str, Any]:
        """Create the lesson metadata and structure"""
        key_concepts = unique_preserve_order(
            [*subtopics[:4], *extract_focus_terms(source_context or prompt or topic, subtopics, limit=6)]
        )[:6]

        return {
            "title": f"Lesson: {topic}",
            "difficulty": difficulty,
            "learning_objectives": learning_objectives[:5],  # Top 5 objectives
            "prerequisites": await self._identify_prerequisites(topic, difficulty),
            "key_concepts": key_concepts,
            "estimated_required_knowledge": self._get_required_knowledge(difficulty),
            "prompt_focus": prompt[:240] if prompt else None,
        }
    
    async def _create_lesson_sections(self, topic: str, subtopics: List[str],
                                     learning_objectives: List[str],
                                     difficulty: ContentLevel,
                                     lesson_style: str,
                                     prompt: str,
                                     source_context: str) -> List[Dict[str, Any]]:
        """Create lesson sections"""
        sections = []
        overview_sentences = select_relevant_sentences(
            source_context,
            extract_keywords(topic, *subtopics, *learning_objectives, prompt),
            limit=3,
        )
        
        # Introduction section
        sections.append({
            "id": 0,
            "type": "introduction",
            "title": f"Introduction to {topic}",
            "content": self._build_intro_content(topic, prompt, learning_objectives, overview_sentences),
            "importance": "Understand the context and relevance of this topic",
            "objectives": learning_objectives[:2],
            "source_support": overview_sentences,
        })
        
        # Main content sections from subtopics
        for i, subtopic in enumerate(subtopics, 1):
            source_support = prioritize_phrase_matches(
                select_relevant_sentences(
                    source_context,
                    extract_keywords(subtopic, topic, *learning_objectives),
                    limit=6,
                ),
                subtopic,
                limit=3,
            )
            section = {
                "id": i,
                "type": "main_content",
                "title": subtopic,
                "content": await self._generate_section_content(
                    subtopic=subtopic,
                    topic=topic,
                    difficulty=difficulty,
                    lesson_style=lesson_style,
                    learning_objectives=learning_objectives,
                    source_support=source_support,
                ),
                "learning_outcomes": [
                    f"Understand key aspects of {subtopic}",
                    f"Apply {subtopic} concepts",
                    f"Analyze relationships in {subtopic}",
                ],
                "key_points": await self._extract_key_points(subtopic, source_support, learning_objectives),
                "source_support": source_support,
            }
            sections.append(section)
        
        # Summary section
        sections.append({
            "id": len(sections),
            "type": "summary",
            "title": f"{topic} Summary",
            "content": self._build_summary_content(topic, subtopics, overview_sentences),
            "review_questions": [
                f"What is the most important aspect of {subtopic}?"
                for subtopic in subtopics[:3]
            ],
        })
        
        return sections
    
    def _build_intro_content(
        self,
        topic: str,
        prompt: str,
        learning_objectives: List[str],
        overview_sentences: List[str],
    ) -> str:
        intro_lines = [f"**{topic}** is the focus of this lesson."]

        if prompt:
            intro_lines.append(f"Prompt focus: {prompt.strip()}")

        if overview_sentences:
            intro_lines.append("Grounded context:")
            intro_lines.extend(f"- {sentence}" for sentence in overview_sentences)

        if learning_objectives:
            intro_lines.append("This lesson aims to help you:")
            intro_lines.extend(f"- {objective}" for objective in learning_objectives[:3])

        return "\n\n".join(
            [intro_lines[0], "\n".join(intro_lines[1:])] if len(intro_lines) > 1 else intro_lines
        )

    def _build_summary_content(
        self,
        topic: str,
        subtopics: List[str],
        overview_sentences: List[str],
    ) -> str:
        lines = [f"**Summary of {topic}**"]
        lines.append(f"Covered subtopics: {', '.join(subtopics[:5])}.")
        if overview_sentences:
            lines.append("Key grounded takeaways:")
            lines.extend(f"- {sentence}" for sentence in overview_sentences[:3])
        return "\n\n".join([lines[0], "\n".join(lines[1:])])

    async def _generate_section_content(self, subtopic: str, topic: str,
                                       difficulty: ContentLevel,
                                       lesson_style: str,
                                       learning_objectives: List[str],
                                       source_support: List[str]) -> str:
        """
        Generate content for a section based on difficulty and style
        """
        descriptor = {
            ContentLevel.BEGINNER: "Start with the core definition and purpose.",
            ContentLevel.INTERMEDIATE: "Connect the concept to surrounding systems and practice.",
            ContentLevel.ADVANCED: "Focus on nuanced behavior, trade-offs, and edge cases.",
        }[difficulty]

        lines = [f"**{subtopic}** in {topic}", descriptor]

        if source_support:
            lines.append("Grounded explanations:")
            lines.extend(f"- {sentence}" for sentence in source_support)
        else:
            lines.append("Focus points:")
            lines.extend(
                f"- {item}"
                for item in unique_preserve_order(
                    [
                        f"{subtopic} is a major part of {topic}.",
                        f"Use {subtopic} to achieve the lesson objective: {learning_objectives[0] if learning_objectives else f'understand {topic}'}",
                        f"Consider how {subtopic} changes in real scenarios.",
                    ]
                )
            )

        if lesson_style == "structured":
            lines.append("Study flow:")
            lines.extend(
                [
                    "- Definition or concept framing",
                    "- Why it matters in context",
                    "- Practical implication or trade-off",
                ]
            )

        return "\n\n".join([lines[0], "\n".join(lines[1:])])
    
    async def _extract_key_points(
        self,
        subtopic: str,
        source_support: List[str],
        learning_objectives: List[str],
    ) -> List[str]:
        """Extract key discussion points from a subtopic"""
        if source_support:
            return unique_preserve_order(
                [*source_support, *learning_objectives]
            )[:4]

        return unique_preserve_order(
            [
                f"Core principle of {subtopic}",
                f"How {subtopic} applies in practice",
                f"Common challenges with {subtopic}",
                f"Why {subtopic} matters",
            ]
        )[:4]
    
    async def _add_examples_to_sections(self, sections: List[Dict],
                                       topic: str,
                                       difficulty: ContentLevel,
                                       source_context: str) -> List[Dict]:
        """Add real-world examples to sections"""
        for section in sections:
            if section["type"] == "main_content":
                source_support = section.get("source_support") or select_relevant_sentences(
                    source_context,
                    extract_keywords(section["title"], topic),
                    limit=4,
                )
                source_support = prioritize_phrase_matches(source_support, section["title"], limit=2)
                section["examples"] = [
                    {
                        "title": f"Example 1: {section['title']}",
                        "description": (
                            source_support[0]
                            if source_support
                            else f"A practical example of {section['title']} in {topic}"
                        ),
                        "complexity": difficulty,
                    },
                    {
                        "title": f"Example 2: Advanced use case",
                        "description": (
                            source_support[1]
                            if len(source_support) > 1
                            else f"How professionals use {section['title']} when solving real problems in {topic}"
                        ),
                        "complexity": difficulty,
                    },
                ]
        
        return sections
    
    async def _add_case_studies(self, sections: List[Dict], topic: str,
                               difficulty: ContentLevel,
                               source_context: str) -> List[Dict]:
        """Add case studies to relevant sections"""
        case_studies = []
        
        for section in sections:
            if section["type"] == "main_content" and len(case_studies) < 2:
                source_support = section.get("source_support") or select_relevant_sentences(
                    source_context,
                    extract_keywords(section["title"], topic),
                    limit=4,
                )
                source_support = prioritize_phrase_matches(source_support, section["title"], limit=2)
                case_studies.append({
                    "title": f"Case Study: {section['title']} in Action",
                    "scenario": source_support[0] if source_support else f"Real-world scenario involving {section['title']}",
                    "challenge": f"Identify what makes {section['title']} difficult or high-impact in {topic}.",
                    "solution": source_support[1] if len(source_support) > 1 else f"Apply the main principle of {section['title']} step by step.",
                    "lessons_learned": f"Focus on the signals, constraints, and outcomes described for {section['title']}.",
                    "complexity": difficulty,
                })
                section["case_study"] = case_studies[-1]
        
        return sections
    
    async def _create_resource_list(self, topic: str, subtopics: List[str],
                                   difficulty: ContentLevel,
                                   source_materials: List[str]) -> List[str]:
        """Create list of supplementary learning resources"""
        resources = unique_preserve_order([
            f"Wikipedia: {topic}",
            f"Academic paper on {subtopics[0] if subtopics else topic}",
            "Video tutorial series",
            "Interactive online course",
        ])

        if source_materials:
            resources.insert(0, "Uploaded source document used as primary lesson reference")
        
        if difficulty == ContentLevel.ADVANCED:
            resources.extend([
                "Research journals and papers",
                "Expert interviews and podcasts",
                "Advanced textbooks",
            ])
        
        return unique_preserve_order(resources)
    
    async def _identify_prerequisites(self, topic: str,
                                     difficulty: ContentLevel) -> List[str]:
        """Identify prerequisite knowledge needed"""
        if difficulty == ContentLevel.BEGINNER:
            return ["Basic literacy", "General knowledge"]
        elif difficulty == ContentLevel.INTERMEDIATE:
            return ["Foundational concepts", "Basic understanding of related topics"]
        else:
            return ["Advanced understanding", "Domain expertise", "Mathematical background"]
    
    def _get_required_knowledge(self, difficulty: ContentLevel) -> str:
        """Get string describing required knowledge"""
        if difficulty == ContentLevel.BEGINNER:
            return "No prior knowledge required"
        elif difficulty == ContentLevel.INTERMEDIATE:
            return "Basic foundational knowledge recommended"
        else:
            return "Advanced prior knowledge required"
    
    async def _calculate_quality_score(self, sections: List[Dict]) -> float:
        """Calculate lesson quality based on completeness"""
        if not sections:
            return 0.0
        
        total_score = 0.0
        
        for section in sections:
            section_quality = 0.0
            checks = 0
            
            # Check for required fields
            required_fields = ["id", "type", "title", "content"]
            for field in required_fields:
                checks += 1
                if field in section and section[field]:
                    section_quality += 1
            
            # Check for examples
            if section.get("examples"):
                checks += 1
                section_quality += 1
            
            # Check for key points
            if section.get("key_points"):
                checks += 1
                section_quality += 1
            
            if checks > 0:
                total_score += section_quality / checks
        
        avg_score = total_score / len(sections)
        return min(1.0, max(0.0, avg_score))
