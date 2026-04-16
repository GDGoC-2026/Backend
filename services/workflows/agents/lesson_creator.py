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
        
        # Create lesson structure
        lesson = await self._create_lesson_structure(
            topic=topic,
            difficulty=difficulty,
            learning_objectives=learning_objectives
        )
        
        # Create sections
        sections = await self._create_lesson_sections(
            topic=topic,
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            difficulty=difficulty,
            lesson_style=lesson_style
        )
        
        # Add examples if requested
        if include_examples:
            sections = await self._add_examples_to_sections(
                sections=sections,
                topic=topic,
                difficulty=difficulty
            )
        
        # Add case studies if requested
        if include_case_studies:
            sections = await self._add_case_studies(
                sections=sections,
                topic=topic,
                difficulty=difficulty
            )
        
        # Create resource list
        resources = await self._create_resource_list(topic, subtopics, difficulty)
        
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
    
    async def _create_lesson_structure(self, topic: str, difficulty: ContentLevel,
                                      learning_objectives: List[str]) -> Dict[str, Any]:
        """Create the lesson metadata and structure"""
        return {
            "title": f"Lesson: {topic}",
            "difficulty": difficulty,
            "learning_objectives": learning_objectives[:5],  # Top 5 objectives
            "prerequisites": await self._identify_prerequisites(topic, difficulty),
            "key_concepts": [],  # Will be filled by sections
            "estimated_required_knowledge": self._get_required_knowledge(difficulty),
        }
    
    async def _create_lesson_sections(self, topic: str, subtopics: List[str],
                                     learning_objectives: List[str],
                                     difficulty: ContentLevel,
                                     lesson_style: str) -> List[Dict[str, Any]]:
        """Create lesson sections"""
        sections = []
        
        # Introduction section
        sections.append({
            "id": 0,
            "type": "introduction",
            "title": f"Introduction to {topic}",
            "content": f"Welcome to learning about {topic}.",
            "importance": "Understand the context and relevance of this topic",
            "objectives": learning_objectives[:2],
        })
        
        # Main content sections from subtopics
        for i, subtopic in enumerate(subtopics, 1):
            section = {
                "id": i,
                "type": "main_content",
                "title": subtopic,
                "content": await self._generate_section_content(
                    subtopic=subtopic,
                    topic=topic,
                    difficulty=difficulty,
                    lesson_style=lesson_style
                ),
                "learning_outcomes": [
                    f"Understand key aspects of {subtopic}",
                    f"Apply {subtopic} concepts",
                    f"Analyze relationships in {subtopic}",
                ],
                "key_points": await self._extract_key_points(subtopic),
            }
            sections.append(section)
        
        # Summary section
        sections.append({
            "id": len(sections),
            "type": "summary",
            "title": f"{topic} Summary",
            "content": f"Key takeaways from {topic}",
            "review_questions": [
                f"What is the most important aspect of {subtopic}?"
                for subtopic in subtopics[:3]
            ],
        })
        
        return sections
    
    async def _generate_section_content(self, subtopic: str, topic: str,
                                       difficulty: ContentLevel,
                                       lesson_style: str) -> str:
        """
        Generate content for a section based on difficulty and style
        """
        if difficulty == ContentLevel.BEGINNER:
            return (
                f"**{subtopic}** is a fundamental concept in {topic}.\n\n"
                f"Here's what you need to know:\n"
                f"- Basic definition\n"
                f"- Why it matters\n"
                f"- Common examples"
            )
        elif difficulty == ContentLevel.INTERMEDIATE:
            return (
                f"**{subtopic}** is a key component of {topic}.\n\n"
                f"Deep dive:\n"
                f"- Detailed explanation with context\n"
                f"- Related concepts and connections\n"
                f"- Practical applications\n"
                f"- Relevant research and studies"
            )
        else:  # ADVANCED
            return (
                f"**{subtopic}** - Advanced exploration\n\n"
                f"Advanced content:\n"
                f"- Theoretical foundations\n"
                f"- Current research and debates\n"
                f"- Edge cases and exceptions\n"
                f"- Advanced applications and implications\n"
                f"- Connections to other advanced topics"
            )
    
    async def _extract_key_points(self, subtopic: str) -> List[str]:
        """Extract key discussion points from a subtopic"""
        return [
            f"Core principle of {subtopic}",
            f"How {subtopic} applies in practice",
            f"Common challenges with {subtopic}",
            f"Why {subtopic} matters",
        ]
    
    async def _add_examples_to_sections(self, sections: List[Dict],
                                       topic: str,
                                       difficulty: ContentLevel) -> List[Dict]:
        """Add real-world examples to sections"""
        for section in sections:
            if section["type"] == "main_content":
                section["examples"] = [
                    {
                        "title": f"Example 1: {section['title']}",
                        "description": f"A practical example of {section['title']} in {topic}",
                        "complexity": difficulty,
                    },
                    {
                        "title": f"Example 2: Advanced use case",
                        "description": f"How professionals use {section['title']}",
                        "complexity": difficulty,
                    },
                ]
        
        return sections
    
    async def _add_case_studies(self, sections: List[Dict], topic: str,
                               difficulty: ContentLevel) -> List[Dict]:
        """Add case studies to relevant sections"""
        case_studies = []
        
        for section in sections:
            if section["type"] == "main_content" and len(case_studies) < 2:
                case_studies.append({
                    "title": f"Case Study: {section['title']} in Action",
                    "scenario": f"Real-world scenario involving {section['title']}",
                    "challenge": "The problem or challenge presented",
                    "solution": "How people/organizations solved it",
                    "lessons_learned": "Key insights from this case",
                    "complexity": difficulty,
                })
                section["case_study"] = case_studies[-1]
        
        return sections
    
    async def _create_resource_list(self, topic: str, subtopics: List[str],
                                   difficulty: ContentLevel) -> List[str]:
        """Create list of supplementary learning resources"""
        resources = [
            f"Wikipedia: {topic}",
            f"Academic paper on {subtopics[0] if subtopics else topic}",
            "Video tutorial series",
            "Interactive online course",
        ]
        
        if difficulty == ContentLevel.ADVANCED:
            resources.extend([
                "Research journals and papers",
                "Expert interviews and podcasts",
                "Advanced textbooks",
            ])
        
        return resources
    
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
