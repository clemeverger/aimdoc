from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeRequest(BaseModel):
    """Request model for starting a scrape job"""
    name: str = Field(..., description="Project name for the documentation")
    url: HttpUrl = Field(..., description="Base URL of the documentation site")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "react-docs",
                "url": "https://react.dev"
            }
        }


class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    message: str = Field(..., description="Status message")


class JobStatusResponse(BaseModel):
    """Response model for job status check"""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    request: Optional[Dict[str, Any]] = None


class JobListResponse(BaseModel):
    """Response model for listing jobs"""
    jobs: List[JobStatusResponse]
    total: int


class JobResults(BaseModel):
    """Response model for job results"""
    job_id: str
    status: JobStatus
    files: List[str] = Field(..., description="List of generated files")
    build_path: str = Field(..., description="Path to the build directory")
    metadata: Dict[str, Any] = Field(..., description="Build metadata")


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    job_id: Optional[str] = None