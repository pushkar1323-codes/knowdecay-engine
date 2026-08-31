"""
app/schemas/quiz.py
────────────────────
Pydantic schemas for quiz endpoints.
"""

import uuid

from pydantic import BaseModel, Field


class QuestionResponseCreate(BaseModel):
    question_number: int = Field(..., description="Question number")
    question_text: str | None = Field(default=None, description="Text of the question")
    question_type: str = Field(default="mcq", description="Type of question")
    is_correct: bool = Field(..., description="Whether the answer was correct")
    difficulty: float | None = Field(default=None, description="Difficulty of the question")
    response_time_seconds: float | None = Field(default=None, description="Time taken to respond")
    confidence_rating: float | None = Field(default=None, description="Confidence rating")
    bloom_level: str | None = Field(default=None, description="Bloom's taxonomy level")
    marks_possible: float = Field(default=1.0, description="Possible marks for the question")
    marks_earned: float = Field(default=0.0, description="Marks earned for the question")
    response_metadata: dict | None = Field(default=None, description="Additional metadata")


class QuestionResponseItem(BaseModel):
    id: uuid.UUID = Field(..., description="Response ID")
    question_number: int = Field(..., description="Question number")
    question_text: str | None = Field(default=None, description="Text of the question")
    question_type: str = Field(default="mcq", description="Type of question")
    is_correct: bool = Field(..., description="Whether the answer was correct")
    difficulty: float | None = Field(default=None, description="Difficulty of the question")
    response_time_seconds: float | None = Field(default=None, description="Time taken to respond")
    confidence_rating: float | None = Field(default=None, description="Confidence rating")
    bloom_level: str | None = Field(default=None, description="Bloom's taxonomy level")
    marks_possible: float = Field(default=1.0, description="Possible marks for the question")
    marks_earned: float = Field(default=0.0, description="Marks earned for the question")
    response_metadata: dict | None = Field(default=None, description="Additional metadata")

    model_config = {"from_attributes": True}


class QuizAttemptCreate(BaseModel):
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    score: float = Field(..., description="Score achieved")
    confidence: float = Field(default=0.5, description="Overall confidence level")
    attempt_number: int | None = Field(default=None, description="Attempt number")
    time_taken_seconds: int | None = Field(default=None, description="Time taken in seconds")
    total_marks: float | None = Field(default=None, description="Total marks available")
    earned_marks: float | None = Field(default=None, description="Marks earned")
    bloom_level: str | None = Field(default=None, description="Bloom's taxonomy level")
    question_count: int | None = Field(default=None, description="Number of questions")
    quiz_metadata: dict | None = Field(default=None, description="Additional quiz metadata")
    question_responses: list[QuestionResponseCreate] | None = Field(default=None, description="Responses to individual questions")


class QuizAttemptResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Attempt ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    score: float = Field(..., description="Score achieved")
    confidence: float = Field(..., description="Overall confidence level")
    attempt_number: int | None = Field(default=None, description="Attempt number")
    time_taken_seconds: int | None = Field(default=None, description="Time taken in seconds")
    total_marks: float | None = Field(default=None, description="Total marks available")
    earned_marks: float | None = Field(default=None, description="Marks earned")
    bloom_level: str | None = Field(default=None, description="Bloom's taxonomy level")
    question_count: int | None = Field(default=None, description="Number of questions")
    quiz_metadata: dict | None = Field(default=None, description="Additional quiz metadata")
    question_responses: list[QuestionResponseItem] = Field(..., description="Responses to individual questions")

    model_config = {"from_attributes": True}


class QuizAttemptListResponse(BaseModel):
    attempts: list[QuizAttemptResponse] = Field(..., description="List of attempts")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class QuizStatsResponse(BaseModel):
    total_attempts: int = Field(..., description="Total attempts")
    avg_score: float = Field(..., description="Average score")
    avg_confidence: float = Field(..., description="Average confidence")
    total_questions: int = Field(..., description="Total questions answered")
    correct_rate: float = Field(..., description="Rate of correct answers")
