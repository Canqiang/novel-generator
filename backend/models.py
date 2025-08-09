from enum import Enum
from datetime import datetime
from typing import Optional, Dict

from pydantic import BaseModel


class NovelGenre(str, Enum):
    URBAN_ROMANCE = "urban_romance"
    MYSTERY = "mystery"
    SCIFI = "scifi"
    WORKPLACE = "workplace"
    FANTASY = "fantasy"


class NovelRequest(BaseModel):
    theme: str
    genre: Optional[NovelGenre] = None
    style: Optional[str] = "知乎风格"
    word_count: Optional[int] = 30000
    chapter_count: Optional[int] = 12


class NovelStatus(str, Enum):
    PENDING = "pending"
    OUTLINING = "outlining"
    WRITING = "writing"
    POLISHING = "polishing"
    COMPLETED = "completed"
    FAILED = "failed"


class NovelTask(BaseModel):
    task_id: str
    status: NovelStatus
    progress: int  # 0-100
    current_stage: str
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict] = None
    error: Optional[str] = None
