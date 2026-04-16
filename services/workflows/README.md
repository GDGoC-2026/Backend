# Content Generation Workflow System

Multi-agent system for generating personalized educational content based on student capabilities.

## Overview

This system uses a orchestrator-based architecture with specialized agents that work together to create comprehensive educational content:

### Agents

1. **PersonaAgent** - Analyzes student profile and creates learning recommendations
2. **FlashcardCreatorAgent** - Generates FSRS-optimized flashcards for spaced repetition
3. **MindmapCreatorAgent** - Creates visual mind maps showing concept relationships
4. **QuizCreatorAgent** - Generates adaptive quizzes for assessment
5. **LessonCreatorAgent** - Creates comprehensive lessons with examples and case studies
6. **ExerciseOrchestrator** - Coordinates all agents and manages the workflow

## Architecture

```
ExerciseOrchestrator (Main Coordinator)
├── Phase 1: PersonaAgent (Sequential)
│   └── Analyzes student → generates recommendations
├── Phase 2: Content Agents (Parallel)
│   ├── FlashcardCreatorAgent
│   ├── MindmapCreatorAgent
│   ├── QuizCreatorAgent
│   └── LessonCreatorAgent
├── Phase 3: Aggregation & Validation
│   └── Combine results → perform QA
└── Phase 4: Output
    └── Return comprehensive content bundle
```

## Directory Structure

```
workflows/
├── __init__.py
├── base.py                  # Base classes for agents
├── config.py                # Configuration and data classes
├── orchestrator/
│   ├── __init__.py
│   └── orchestrator.py      # Main orchestrator
├── agents/
│   ├── __init__.py
│   ├── persona.py
│   ├── flashcard_creator.py
│   ├── mindmap_creator.py
│   ├── quiz_creator.py
│   └── lesson_creator.py
└── utils/
    ├── __init__.py
    └── helpers.py           # Utility functions
```

## Quick Start

### Basic Usage

```python
from services.workflows import ExerciseOrchestrator
from services.workflows.config import (
    StudentProfile,
    ContentLevel,
    ContentType,
    ContentGenerationRequest,
)
from services.workflows.utils import create_student_profile, create_content_generation_request

# Step 1: Create student profile
student = create_student_profile(
    student_id="student_123",
    name="John Doe",
    subject="Mathematics",
    current_level="intermediate",
    learning_style="visual",
    knowledge_gaps=["Calculus", "Probability"],
    strengths=["Algebra", "Geometry"],
    learning_pace="normal",
)

# Step 2: Create content request
request = create_content_generation_request(
    student_profile=student,
    topic="Linear Equations",
    subtopics=["Slope-Intercept Form", "Point-Slope Form", "Standard Form"],
    learning_objectives=[
        "Understand different forms of linear equations",
        "Convert between equation forms",
        "Apply to real-world problems",
    ],
    content_types=["flashcard", "mindmap", "quiz", "lesson"],
    max_items=10,
)

# Step 3: Execute orchestrator
orchestrator = ExerciseOrchestrator()
result = await orchestrator.run({"request": request})

# Step 4: Access results
print(f"Total content generated: {len(result['generated_content'])}")
print(f"Average quality score: {result['quality_metrics']['average_quality_score']}")
```

### Advanced: Custom Agent Configuration

```python
from services.workflows.agents import FlashcardCreatorAgent

# Use individual agents if needed
flashcard_agent = FlashcardCreatorAgent()

input_data = {
    "topic": "Python Basics",
    "subtopics": ["Variables", "Data Types", "Functions"],
    "difficulty": ContentLevel.BEGINNER,
    "max_cards": 15,
    "learning_objectives": ["Understand Python fundamentals"],
}

result = await flashcard_agent.run(input_data)
```

## Configuration

Edit `config.py` to customize:

- **WORKFLOW_CONFIG**: Max parallel agents, timeouts, caching
- **AGENT_TIMEOUTS**: Individual agent execution timeouts
- **QUALITY_THRESHOLDS**: Quality score requirements

```python
WORKFLOW_CONFIG = {
    "max_parallel_agents": 3,       # Concurrency limit
    "request_timeout_seconds": 60,
    "retry_attempts": 3,
    "cache_enabled": True,
    "cache_ttl_minutes": 60,
}

AGENT_TIMEOUTS = {
    "persona": 10,
    "flashcard_creator": 20,
    "mindmap_creator": 25,
    "quiz_creator": 30,
    "lesson_creator": 40,
}

QUALITY_THRESHOLDS = {
    "min_score": 0.7,
    "retry_if_below": 0.6,
}
```

## Data Classes

### StudentProfile
```python
StudentProfile(
    student_id: str,
    name: str,
    subject: str,
    current_level: ContentLevel,  # beginner, intermediate, advanced
    learning_style: str,           # visual, auditory, kinesthetic, reading/writing
    knowledge_gaps: list[str],
    strengths: list[str],
    learning_pace: str,            # slow, normal, fast
    preferred_content_types: list[ContentType],
    daily_study_time_minutes: int,
)
```

### ContentGenerationRequest
```python
ContentGenerationRequest(
    student_profile: StudentProfile,
    topic: str,
    subtopics: list[str],
    learning_objectives: list[str],
    content_types: list[ContentType],
    difficulty_level: Optional[ContentLevel],
    max_items: int,
)
```

### GeneratedContent
```python
GeneratedContent(
    content_type: ContentType,
    title: str,
    content: str,           # JSON serialized
    student_id: str,
    topic: str,
    difficulty_level: ContentLevel,
    estimated_time_minutes: int,
    quality_score: float,   # 0.0 - 1.0
)
```

## API Integration

### Add to FastAPI Router

```python
from fastapi import APIRouter, Depends
from services.workflows import ExerciseOrchestrator

router = APIRouter(prefix="/api/v1/content", tags=["content_generation"])

@router.post("/generate")
async def generate_content(request: ContentGenerationRequest):
    orchestrator = ExerciseOrchestrator()
    result = await orchestrator.run({"request": request})
    return result

@router.get("/student/{student_id}/content")
async def get_student_content(student_id: str):
    # Retrieve previously generated content
    pass
```

## Workflow Execution Flow

### Phase 1: PersonaAgent Analysis
- Analyzes student capabilities and profile
- Recommends appropriate difficulty and content types
- Creates personalized learning path
- Outputs: difficulty, content_types, customization strategies

### Phase 2: Parallel Content Generation
All agents run in parallel (with concurrency limit):

**FlashcardCreatorAgent**
- Generates Q&A pairs
- Optimizes for learning style
- Adds memory cues and hints
- Initializes FSRS parameters
- Output: 10 flashcards with ~0.8 quality score

**MindmapCreatorAgent**
- Organizes concepts hierarchically
- Creates visual relationships
- Generates D3.js compatible JSON
- Output: Mind map with nodes and connections

**QuizCreatorAgent**
- Creates multiple choice, fill-blank, true/false
- Adaptive difficulty distribution
- Includes explanations
- Output: 10 questions with 0.75-0.85 quality

**LessonCreatorAgent**
- Writes structured lesson content
- Includes examples and case studies
- Adds learning resources
- Output: Multi-section lesson with quality score

### Phase 3: Aggregation
- Combines all content into unified structure
- Standardizes format across content types
- Validates completeness

### Phase 4: Quality Assurance
- Calculates average quality score
- Ensures all content meets thresholds
- Flags any quality issues
- Returns: QA results and metrics

## Quality Metrics

Each piece of generated content is scored 0.0-1.0 based on:

- **Flashcards**: Has question, answer, difficulty, hints, memory cue
- **Mind Maps**: Has nodes, connections, proper hierarchy
- **Quizzes**: Has complete questions with correct answers and explanations
- **Lessons**: Has structure, content, examples, resources

Overall workflow quality = Average of all content pieces

## Execution Logging

The orchestrator maintains a detailed execution log:

```python
result["workflow_log"] = [
    {
        "success": True,
        "agent": "PersonaAgent",
        "data": {...},
        "execution_time_seconds": 5.23,
        "timestamp": "2024-01-01T10:30:00Z",
    },
    # ... logs for each agent
]
```

## Error Handling

The system handles:
- Agent timeouts (returns error for that agent, continues with others)
- Missing required fields (raises ValueError)
- Quality threshold failures (reported in QA metrics)
- Partial failures (aggregates successful content)

## Extending the System

### Adding a New Agent

1. Create new file in `agents/` directory, inherit from `BaseAgent`
2. Implement `execute()` and `validate_input()` methods
3. Register in `ExerciseOrchestrator._initialize_agents()`
4. Add timeout to `AGENT_TIMEOUTS` in `config.py`

Example template:

```python
from base import BaseAgent

class NewAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="NewAgent", timeout=30)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation
        return {"result": "data"}
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        # Validation
        return True
```

## Performance Considerations

- **Parallel Execution**: Agents run concurrently per config
- **Caching**: Content can be cached based on student + topic
- **Timeouts**: Each agent has individual timeout
- **Max Concurrency**: Limited to prevent resource exhaustion
- **Async/Await**: Non-blocking execution

Typical workflow time: 45-60 seconds for all 4 content types

## Testing

See `test_workflows.py` for:
- Unit tests for individual agents
- Integration tests for orchestrator
- Mock LLM responses for testing
- Quality score validation tests
