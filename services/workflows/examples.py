"""
Example usage and integration patterns for the content generation workflow
"""

import asyncio
from config import (
    StudentProfile,
    ContentLevel,
    ContentType,
    ContentGenerationRequest,
)
from orchestrator.orchestrator import ExerciseOrchestrator
from utils.helpers import (
    create_student_profile,
    create_content_generation_request,
    format_content_for_output,
    get_content_statistics,
)


async def example_basic_workflow():
    """
    Basic example: Generate all content types for a student
    """
    print("=" * 60)
    print("EXAMPLE 1: Basic Content Generation")
    print("=" * 60)
    
    # Create student profile
    student = create_student_profile(
        student_id="student_001",
        name="Alice Johnson",
        subject="Biology",
        current_level="intermediate",
        learning_style="visual",
        knowledge_gaps=["Cellular Respiration", "Photosynthesis"],
        strengths=["Anatomy", "Ecology"],
        learning_pace="normal",
        daily_study_time_minutes=45,
        preferred_content_types=["flashcard", "mindmap", "quiz"],
    )
    
    # Create content request
    request = create_content_generation_request(
        student_profile=student,
        topic="Cellular Respiration",
        subtopics=[
            "Glycolysis",
            "Citric Acid Cycle",
            "Electron Transport Chain",
            "ATP Production",
        ],
        learning_objectives=[
            "Understand the stages of cellular respiration",
            "Calculate ATP yield from glucose",
            "Compare aerobic and anaerobic respiration",
            "Identify the role of mitochondria",
        ],
        content_types=["flashcard", "mindmap", "quiz", "lesson"],
        max_items=10,
    )
    
    # Execute orchestrator
    orchestrator = ExerciseOrchestrator()
    
    try:
        result = await orchestrator.run({"request": request})
        
        print(f"\n✓ Workflow completed successfully")
        print(f"Student: {student.name}")
        print(f"Topic: {request.topic}")
        print(f"Content generated: {len(result['generated_content'])} items")
        
        # Get statistics
        stats = get_content_statistics([
            {
                "content_type": c.content_type,
                "estimated_time_minutes": c.estimated_time_minutes,
                "quality_score": c.quality_score,
                "difficulty_level": c.difficulty_level,
            }
            for c in result["generated_content"]
        ])
        
        print(f"\nContent Statistics:")
        print(f"  Total items: {stats['total_items']}")
        print(f"  Total estimated time: {stats['total_estimated_time']} minutes")
        print(f"  Average quality score: {stats['average_quality']:.2f}")
        print(f"  By type: {stats['by_type']}")
        
        # Quality metrics
        qa = result['quality_metrics']
        print(f"\nQuality Assurance:")
        print(f"  Passed QA: {'✓' if qa['passed_qa'] else '✗'}")
        print(f"  Issues: {qa['quality_issues'] if qa['quality_issues'] else 'None'}")
        
        # Execution summary
        exec_summary = result['execution_summary']
        print(f"\nExecution Summary:")
        print(f"  Total time: {exec_summary['total_execution_time_seconds']:.2f}s")
        print(f"  Agents: {exec_summary['agents_executed']}")
        print(f"  Successful: {exec_summary['successful_executions']}")
        
    except Exception as e:
        print(f"\n✗ Workflow failed: {str(e)}")


async def example_beginner_level():
    """
    Example: Tailor content for beginner student
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Beginner Level Content")
    print("=" * 60)
    
    student = create_student_profile(
        student_id="student_002",
        name="Bob Smith",
        subject="Mathematics",
        current_level="beginner",
        learning_style="reading/writing",
        knowledge_gaps=["Fractions", "Decimals", "Percentages"],
        strengths=["Addition", "Subtraction"],
        learning_pace="slow",
        daily_study_time_minutes=20,
    )
    
    request = create_content_generation_request(
        student_profile=student,
        topic="Introduction to Fractions",
        subtopics=[
            "What are fractions",
            "Equivalent fractions",
            "Comparing fractions",
            "Adding fractions",
        ],
        learning_objectives=[
            "Understand the concept of fractions",
            "Identify equivalent fractions",
            "Compare and order fractions",
        ],
        content_types=["flashcard", "quiz", "lesson"],
        difficulty_level="beginner",
    )
    
    orchestrator = ExerciseOrchestrator()
    result = await orchestrator.run({"request": request})
    
    print(f"\nStudent: {student.name} (Beginner)")
    print(f"Learning pace: {student.learning_pace}")
    print(f"Content generated: {len(result['generated_content'])} items")
    print(f"Average quality: {result['quality_metrics']['average_quality_score']:.2f}")


async def example_advanced_level():
    """
    Example: Comprehensive content for advanced student
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Advanced Level Content")
    print("=" * 60)
    
    student = create_student_profile(
        student_id="student_003",
        name="Carol White",
        subject="Computer Science",
        current_level="advanced",
        learning_style="visual",
        knowledge_gaps=["Machine Learning Applications"],
        strengths=["Algorithms", "Data Structures", "Python Programming"],
        learning_pace="fast",
        daily_study_time_minutes=120,
    )
    
    request = create_content_generation_request(
        student_profile=student,
        topic="Advanced Machine Learning",
        subtopics=[
            "Neural Networks Architecture",
            "Backpropagation Algorithm",
            "Convolutional Neural Networks",
            "Transformer Models",
            "Model Optimization Techniques",
        ],
        learning_objectives=[
            "Understand deep learning fundamentals",
            "Implement neural networks from scratch",
            "Optimize model performance",
            "Apply to real-world problems",
            "Explore cutting-edge research",
        ],
        content_types=["mindmap", "quiz", "lesson"],
        difficulty_level="advanced",
        max_items=15,
    )
    
    orchestrator = ExerciseOrchestrator()
    result = await orchestrator.run({"request": request})
    
    print(f"\nStudent: {student.name} (Advanced)")
    print(f"Learning pace: {student.learning_pace}")
    print(f"Content generated: {len(result['generated_content'])} items")
    print(f"Topics covered: {len(request.subtopics)}")


async def example_mixed_learning_styles():
    """
    Example: Showcase how different learning styles affect content
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Different Learning Styles")
    print("=" * 60)
    
    learning_styles = ["visual", "auditory", "kinesthetic", "reading/writing"]
    students = []
    
    for i, style in enumerate(learning_styles):
        student = create_student_profile(
            student_id=f"student_004_{i}",
            name=f"Student {style.capitalize()}",
            subject="History",
            current_level="intermediate",
            learning_style=style,
            knowledge_gaps=["20th Century Wars"],
            strengths=["Ancient History"],
            learning_pace="normal",
        )
        students.append(student)
    
    topic = "World War II"
    
    for student in students:
        print(f"\nProcessing {student.learning_style} learner...")
        
        request = create_content_generation_request(
            student_profile=student,
            topic=topic,
            subtopics=[
                "Causes of WWII",
                "Major battles",
                "Home front",
                "End of war",
            ],
            learning_objectives=[
                "Understand WWII timeline",
                "Identify key events",
                "Analyze impacts",
            ],
            content_types=["flashcard", "mindmap"],
        )
        
        orchestrator = ExerciseOrchestrator()
        result = await orchestrator.run({"request": request})
        
        print(f"  ✓ Generated {len(result['generated_content'])} items")
        print(f"  Quality: {result['quality_metrics']['average_quality_score']:.2f}")


async def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║ Content Generation Workflow - Usage Examples " + " " * 9 + "║")
    print("╚" + "=" * 58 + "╝")
    
    await example_basic_workflow()
    await example_beginner_level()
    await example_advanced_level()
    await example_mixed_learning_styles()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Run examples
    # Note: In actual usage, this would be integrated with FastAPI
    # asyncio.run(main())
    
    print("To run examples, use:")
    print("  python -m asyncio")
    print("  >>> import examples")
    print("  >>> await examples.main()")
