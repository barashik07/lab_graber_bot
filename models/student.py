from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class CourseRef(BaseModel):
    name: str
    semester: str

class Student(BaseModel):
    id: int | None = None
    chat_id: int
    surname: str
    name: str
    patronymic: str | None
    group_code: str
    github: str
    courses: List[CourseRef] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None