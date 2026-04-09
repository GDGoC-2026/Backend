from pydantic import BaseModel, Field
from typing import List, Literal, Union

class Quiz(BaseModel):
    type: Literal["mcq"] = "mcq"
    question: str = Field(..., description="The multiple choice question.")
    options: List[str] = Field(..., description="4 possible answers.")
    correct_answer: str = Field(..., description="The exact string of the correct option.")
    explanation: str = Field(..., description="Socratic explanation of why this is correct.")

class FillInBlankExercise(BaseModel):
    type: Literal["fill_in_blank"] = "fill_in_blank"
    text_before: str
    blank_answer: str
    text_after: str
    hint: str = Field(..., description="A short Socratic hint.")

class CodingTaskExercise(BaseModel):
    type: Literal["coding_task"] = "coding_task"
    language: str
    instructions: str
    starting_code: str
    solution_code: str
    test_cases: List[dict] = Field(..., description="List of dicts with 'input' and 'expected_output'")

class GeneratedLesson(BaseModel):
    module_name: str
    exercises: List[Union[Quiz, FillInBlankExercise, CodingTaskExercise]] = Field(
        ..., description="A mix of adaptive exercises."
    )