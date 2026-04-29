from typing import List
from pydantic import BaseModel, Field, field_validator


class Selection(BaseModel):
    startLine: int = Field(..., ge=0)
    endLine: int = Field(..., ge=0)
    selectedText: str = Field(..., min_length=1)

    @field_validator("endLine")
    @classmethod
    def validate_end_line(cls, value: int, info):
        start_line = info.data.get("startLine")
        if start_line is not None and value < start_line:
            raise ValueError("endLine must be greater than or equal to startLine")
        return value


class Context(BaseModel):
    before: str = ""
    after: str = ""


class GeneratePatchRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    selection: Selection
    context: Context = Field(default_factory=Context)
    naturalLanguageFeedback: str = Field(..., min_length=1)


class PatchCandidate(BaseModel):
    patchedText: str
    explanation: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class GeneratePatchResponse(BaseModel):
    patches: List[PatchCandidate]