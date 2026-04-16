"""
Exercise Orchestrator: Main coordinator for the multi-agent content generation system

Responsibilities:
- Orchestrate execution of all agents
- Manage dependencies between agents
- Handle parallelization
- Aggregate results
- Quality assurance and validation
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging
from datetime import datetime
from ..base import CoordinatorAgent
from ..config import (
    ContentGenerationRequest,
    GeneratedContent,
    StudentProfile,
    WORKFLOW_CONFIG,
    AGENT_TIMEOUTS,
    QUALITY_THRESHOLDS,
)
from ..agents import (
    PersonaAgent,
    FlashcardCreatorAgent,
    MindmapCreatorAgent,
    QuizCreatorAgent,
    LessonCreatorAgent,
)

logger = logging.getLogger(__name__)


class ExerciseOrchestrator(CoordinatorAgent):
    """
    Main orchestrator for the multi-agent content generation workflow.
    
    Workflow:
    1. PersonaAgent analyzes student and creates personalized profile
    2. Based on persona output, parallel execution of:
       - FlashcardCreatorAgent
       - MindmapCreatorAgent
       - QuizCreatorAgent
       - LessonCreatorAgent
    3. Aggregate and validate all results
    4. Return comprehensive content bundle
    """
    
    def __init__(self):
        super().__init__(name="ExerciseOrchestrator", timeout=120)
        self._initialize_agents()
        self.execution_log: List[Dict[str, Any]] = []
    
    def _initialize_agents(self):
        """Initialize all workflow agents"""
        self.register_agent("persona", PersonaAgent())
        self.register_agent("flashcard_creator", FlashcardCreatorAgent())
        self.register_agent("mindmap_creator", MindmapCreatorAgent())
        self.register_agent("quiz_creator", QuizCreatorAgent())
        self.register_agent("lesson_creator", LessonCreatorAgent())
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the complete content generation workflow.
        
        Input:
            - request: ContentGenerationRequest object
            
        Output:
            - workflow_result: Comprehensive content bundle
            - execution_summary: Timing and quality metrics
            - generated_content: All generated content pieces
            - workflow_log: Execution log for debugging
        """
        request: ContentGenerationRequest = input_data.get("request")
        
        logger.info(f"[Orchestrator] Starting workflow for student: {request.student_profile.student_id}")
        
        try:
            # Step 1: Execute Persona Agent (dependency for others)
            logger.info("[Orchestrator] Phase 1: Executing PersonaAgent...")
            persona_result = await self._execute_persona_phase(request)
            
            if not persona_result["success"]:
                raise Exception(f"PersonaAgent failed: {persona_result.get('error')}")
            
            persona_output = persona_result["data"]
            self.execution_log.append(persona_result)
            
            # Step 2: Parallel execution of content creators
            logger.info("[Orchestrator] Phase 2: Parallel execution of content creation agents...")
            content_results = await self._execute_content_creation_phase(
                request=request,
                persona_output=persona_output
            )
            
            # Step 3: Aggregate and validate results
            logger.info("[Orchestrator] Phase 3: Aggregating and validating results...")
            aggregated_content = await self._aggregate_results(
                request=request,
                content_results=content_results,
                persona_output=persona_output
            )
            
            # Step 4: Quality assurance
            logger.info("[Orchestrator] Phase 4: Quality assurance...")
            qa_result = await self._quality_assurance(aggregated_content)
            
            # Final result
            workflow_result = {
                "success": True,
                "student_id": request.student_profile.student_id,
                "topic": request.topic,
                "generated_content": aggregated_content,
                "execution_summary": self._create_execution_summary(),
                "quality_metrics": qa_result,
                "workflow_log": self.execution_log,
                "completed_at": datetime.now().isoformat(),
            }
            
            logger.info(f"[Orchestrator] Workflow completed successfully")
            
            return workflow_result
            
        except Exception as e:
            logger.error(f"[Orchestrator] Workflow failed: {str(e)}")
            raise
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate orchestrator input"""
        if "request" not in input_data:
            raise ValueError("Missing required field: request")
        
        request = input_data["request"]
        if not isinstance(request, ContentGenerationRequest):
            raise ValueError("request must be a ContentGenerationRequest instance")
        
        return True
    
    async def _execute_persona_phase(self, request: ContentGenerationRequest) -> Dict[str, Any]:
        """Execute the PersonaAgent to analyze student"""
        persona_agent = self.get_agent("persona")
        
        persona_input = {
            "student_profile": request.student_profile,
            "topic": request.topic,
            "subtopics": request.subtopics,
            "learning_objectives": request.learning_objectives,
        }
        
        result = await persona_agent.run(persona_input)
        return result
    
    async def _execute_content_creation_phase(
        self,
        request: ContentGenerationRequest,
        persona_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute all content creation agents in parallel.
        Uses asyncio to run multiple agents concurrently.
        """
        # Prepare input data for each agent
        base_input = {
            "topic": request.topic,
            "subtopics": request.subtopics,
            "learning_objectives": request.learning_objectives,
            "difficulty": persona_output.get("recommended_difficulty"),
            "learning_style": request.student_profile.learning_style,
            "content_customization": persona_output.get("content_customization"),
        }
        
        # Create tasks for parallel execution (limit concurrency)
        max_parallel = WORKFLOW_CONFIG["max_parallel_agents"]
        tasks = []
        
        if "flashcard" in [ct.value for ct in request.content_types]:
            flashcard_input = {**base_input, "max_cards": 10}
            tasks.append(
                self._execute_agent_with_timeout(
                    "flashcard_creator",
                    flashcard_input
                )
            )
        
        if "mindmap" in [ct.value for ct in request.content_types]:
            mindmap_input = {**base_input, "max_depth": 3}
            tasks.append(
                self._execute_agent_with_timeout(
                    "mindmap_creator",
                    mindmap_input
                )
            )
        
        if "quiz" in [ct.value for ct in request.content_types]:
            quiz_input = {**base_input, "max_questions": 10}
            tasks.append(
                self._execute_agent_with_timeout(
                    "quiz_creator",
                    quiz_input
                )
            )
        
        if "lesson" in [ct.value for ct in request.content_types]:
            lesson_input = {**base_input, "include_examples": True, "include_case_studies": True}
            tasks.append(
                self._execute_agent_with_timeout(
                    "lesson_creator",
                    lesson_input
                )
            )
        
        # Execute tasks with concurrency limit
        results = {}
        for i in range(0, len(tasks), max_parallel):
            batch = tasks[i:i + max_parallel]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Agent execution error: {str(result)}")
                else:
                    agent_name = result.get("agent", "unknown")
                    results[agent_name] = result
                    self.execution_log.append(result)
        
        return results
    
    async def _execute_agent_with_timeout(self, agent_name: str,
                                         input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent with timeout handling"""
        agent = self.get_agent(agent_name)
        if not agent:
            return {
                "success": False,
                "agent": agent_name,
                "error": f"Agent not found: {agent_name}"
            }
        
        timeout = AGENT_TIMEOUTS.get(agent_name, 30)
        
        try:
            result = await asyncio.wait_for(
                agent.run(input_data),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"[{agent_name}] Execution timed out after {timeout}s")
            return {
                "success": False,
                "agent": agent_name,
                "error": f"Timeout after {timeout} seconds"
            }
    
    async def _aggregate_results(
        self,
        request: ContentGenerationRequest,
        content_results: Dict[str, Any],
        persona_output: Dict[str, Any]
    ) -> List[GeneratedContent]:
        """
        Aggregate all generated content into standardized format.
        """
        aggregated = []
        
        # Process each content type result
        if "FlashcardCreatorAgent" in content_results and content_results["FlashcardCreatorAgent"]["success"]:
            flashcard_data = content_results["FlashcardCreatorAgent"]["data"]
            content = GeneratedContent(
                content_type="flashcard",
                title=f"Flashcards: {request.topic}",
                content=str(flashcard_data["flashcards"]),  # Would be JSON in practice
                student_id=request.student_profile.student_id,
                topic=request.topic,
                difficulty_level=flashcard_data.get("difficulty_level"),
                estimated_time_minutes=10,
                quality_score=flashcard_data.get("quality_score", 0.0),
            )
            aggregated.append(content)
        
        if "MindmapCreatorAgent" in content_results and content_results["MindmapCreatorAgent"]["success"]:
            mindmap_data = content_results["MindmapCreatorAgent"]["data"]
            content = GeneratedContent(
                content_type="mindmap",
                title=f"Mind Map: {request.topic}",
                content=mindmap_data.get("json_format", ""),
                student_id=request.student_profile.student_id,
                topic=request.topic,
                difficulty_level=mindmap_data.get("difficulty"),
                estimated_time_minutes=15,
                quality_score=mindmap_data.get("quality_score", 0.0),
            )
            aggregated.append(content)
        
        if "QuizCreatorAgent" in content_results and content_results["QuizCreatorAgent"]["success"]:
            quiz_data = content_results["QuizCreatorAgent"]["data"]
            content = GeneratedContent(
                content_type="quiz",
                title=f"Quiz: {request.topic}",
                content=str(quiz_data["questions"]),  # Would be JSON in practice
                student_id=request.student_profile.student_id,
                topic=request.topic,
                difficulty_level=quiz_data.get("difficulty"),
                estimated_time_minutes=quiz_data.get("estimated_duration_minutes", 20),
                quality_score=quiz_data.get("quality_score", 0.0),
            )
            aggregated.append(content)
        
        if "LessonCreatorAgent" in content_results and content_results["LessonCreatorAgent"]["success"]:
            lesson_data = content_results["LessonCreatorAgent"]["data"]
            content = GeneratedContent(
                content_type="lesson",
                title=lesson_data["lesson"].get("title", f"Lesson: {request.topic}"),
                content=str(lesson_data["sections"]),  # Would be JSON in practice
                student_id=request.student_profile.student_id,
                topic=request.topic,
                difficulty_level=lesson_data.get("difficulty"),
                estimated_time_minutes=lesson_data.get("estimated_duration_minutes", 30),
                quality_score=lesson_data.get("quality_score", 0.0),
            )
            aggregated.append(content)
        
        return aggregated
    
    async def _quality_assurance(self, aggregated_content: List[GeneratedContent]) -> Dict[str, Any]:
        """
        Perform quality assurance on generated content.
        """
        qa_results = {
            "content_count": len(aggregated_content),
            "average_quality_score": 0.0,
            "content_quality_breakdown": {},
            "quality_issues": [],
            "passed_qa": True,
        }
        
        if not aggregated_content:
            qa_results["passed_qa"] = False
            qa_results["quality_issues"].append("No content generated")
            return qa_results
        
        # Calculate average quality score
        total_score = sum(c.quality_score for c in aggregated_content)
        qa_results["average_quality_score"] = total_score / len(aggregated_content)
        
        # Check each content piece
        min_score_threshold = QUALITY_THRESHOLDS["min_score"]
        
        for content in aggregated_content:
            qa_results["content_quality_breakdown"][content.content_type] = {
                "quality_score": content.quality_score,
                "passed": content.quality_score >= min_score_threshold,
            }
            
            if content.quality_score < min_score_threshold:
                qa_results["quality_issues"].append(
                    f"{content.content_type} quality score {content.quality_score} below threshold"
                )
                qa_results["passed_qa"] = False
        
        return qa_results
    
    def _create_execution_summary(self) -> Dict[str, Any]:
        """Create summary of workflow execution"""
        total_time = sum(
            log.get("execution_time_seconds", 0)
            for log in self.execution_log
        )
        
        return {
            "total_execution_time_seconds": total_time,
            "agents_executed": len(self.execution_log),
            "successful_executions": sum(
                1 for log in self.execution_log if log.get("success", False)
            ),
            "failed_executions": sum(
                1 for log in self.execution_log if not log.get("success", True)
            ),
            "timestamp": datetime.now().isoformat(),
        }
