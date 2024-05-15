from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import SQLModel, Field


class CodeSubmission(BaseModel):
    code: str


class SubmissionRead(SQLModel):
    id: Optional[int]
    name: Optional[str]
    submitted_time: Optional[datetime]
    status: Optional[int]


class SubmissionFileRead(SQLModel):
    id: int
    filename: str = Field(title='filename')
    machine_probability: Optional[float] = Field(title='machine_probability')
    evaluation_time: Optional[datetime] = Field(title='evaluation_time')
    file_size: int = Field(title='file_size')


class SubmissionDetailRead(SQLModel):
    id: int
    name: str = Field(title='name')
    submitted_time: datetime = Field(title='submitted_time')
    status: int = Field(title='status')
    submission_files: List[SubmissionFileRead] = []
