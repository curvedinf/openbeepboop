from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobBase(BaseModel):
    request_payload: Dict[str, Any]

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    priority: int = 0
    result_payload: Optional[Dict[str, Any]] = None
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None

class JobList(BaseModel):
    jobs: List[Job]

class InternalJobSubmit(BaseModel):
    id: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class InternalJobSubmitRequest(BaseModel):
    results: List[InternalJobSubmit]
