from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship

from persistence.submission import Submission


class SubmissionFile(SQLModel, table=True):
    __tablename__ = "submission_file"
    id: int = Field(primary_key=True, default=None, nullable=False)
    filename: str = Field(title='filename')
    path: str = Field(title='path')
    machine_probability: Optional[float] = Field(title='machine_probability')
    evaluation_time: Optional[datetime] = Field(title='evaluation_time')
    file_size: int = Field(title='file_size')
    submission_id: int = Field(title='submission_id', foreign_key='submission.id')

    submission: Optional[Submission] = Relationship(back_populates="submission_files")
