from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Optional

from ..models import (
    ScrapeRequest, 
    JobResponse, 
    JobStatusResponse, 
    JobListResponse, 
    JobResults,
    JobStatus,
    ErrorResponse
)
from ..services.job_service import job_service

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/scrape", response_model=JobResponse)
async def create_scrape_job(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Create and start a new scrape job"""
    try:
        # Create job
        job_id = job_service.create_job(request)
        
        # Start job in background
        background_tasks.add_task(job_service.start_job, job_id)
        
        job_status = job_service.get_job_status(job_id)
        
        return JobResponse(
            job_id=job_id,
            status=job_status.status,
            created_at=job_status.created_at,
            message=f"Job {job_id} created and started successfully"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a specific job"""
    job_status = job_service.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return job_status


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: Optional[int] = 10):
    """List all jobs"""
    jobs = job_service.list_jobs(limit=limit)
    
    return JobListResponse(
        jobs=jobs,
        total=len(jobs)
    )


@router.get("/jobs/{job_id}/results", response_model=JobResults)
async def get_job_results(job_id: str):
    """Get the results of a completed job"""
    job_status = job_service.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job_status.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job {job_id} is not completed. Current status: {job_status.status}"
        )
    
    results = job_service.get_job_results(job_id)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Results for job {job_id} not found")
    
    return results


@router.get("/jobs/{job_id}/download/{file_path:path}")
async def download_job_file(job_id: str, file_path: str):
    """Download a specific file from job results"""
    job_status = job_service.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job_status.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job {job_id} is not completed"
        )
    
    results = job_service.get_job_results(job_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"Results for job {job_id} not found")
    
    # Construct full file path
    full_file_path = Path(results.build_path) / file_path
    
    if not full_file_path.exists():
        raise HTTPException(status_code=404, detail=f"File {file_path} not found")
    
    if not full_file_path.is_file():
        raise HTTPException(status_code=400, detail=f"{file_path} is not a file")
    
    # Security check: ensure file is within build directory
    try:
        full_file_path.resolve().relative_to(Path(results.build_path).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=str(full_file_path),
        filename=full_file_path.name,
        media_type='application/octet-stream'
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and all its files"""
    success = job_service.delete_job(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return {"message": f"Job {job_id} deleted successfully"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    job_status = job_service.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job_status.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel job {job_id}. Current status: {job_status.status}"
        )
    
    success = job_service.delete_job(job_id)  # This will also kill running processes
    
    if success:
        return {"message": f"Job {job_id} cancelled successfully"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job {job_id}")