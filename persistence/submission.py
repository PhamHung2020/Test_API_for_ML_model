from typing import List
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship


class Submission(SQLModel, table=True):
    __tablename__ = "submission"
    id: int = Field(primary_key=True, default=None, nullable=False)
    name: str = Field(title='name')
    submitted_time: datetime = Field(title='submitted_time')
    status: int = Field(title='status')

    submission_files: List['SubmissionFile'] = Relationship(back_populates="submission")
