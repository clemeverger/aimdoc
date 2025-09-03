import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import shutil

from ..models import JobStatus, ScrapeRequest, JobStatusResponse, JobResults


class JobService:
    """Service for managing scrapy jobs"""
    
    def __init__(self):
        # In-memory job storage (in production, use a database)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_processes: Dict[str, subprocess.Popen] = {}
        
        # Ensure jobs directory exists
        self.jobs_dir = Path("jobs")
        self.jobs_dir.mkdir(exist_ok=True)
    
    def create_job(self, request: ScrapeRequest) -> str:
        """Create a new scrape job"""
        job_id = str(uuid.uuid4())
        
        # Create job directory
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # Create manifest file
        manifest_data = {
            "name": request.name,
            "url": str(request.url),
        }
        
        if request.output_mode:
            manifest_data["output"] = {"mode": request.output_mode}
        
        manifest_path = job_dir / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2)
        
        # Store job info
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "created_at": datetime.now(),
            "request": request.dict(),
            "manifest_path": str(manifest_path),
            "job_dir": str(job_dir),
            "build_dir": str(job_dir / "build"),
            "progress": {"pages_found": 0, "pages_scraped": 0, "files_created": 0}
        }
        
        return job_id
    
    async def start_job(self, job_id: str) -> bool:
        """Start a scrape job"""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        if job["status"] != JobStatus.PENDING:
            return False
        
        # Update job status
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.now()
        
        # Start scrapy process asynchronously
        asyncio.create_task(self._run_scrapy(job_id))
        
        return True
    
    def cleanup_finished_processes(self):
        """Clean up finished processes to prevent zombie processes"""
        finished_jobs = []
        for job_id, process in self.job_processes.items():
            if process.poll() is not None:
                finished_jobs.append(job_id)
        
        for job_id in finished_jobs:
            del self.job_processes[job_id]
    
    async def _run_scrapy(self, job_id: str):
        """Run scrapy in a subprocess"""
        job = self.jobs[job_id]
        
        try:
            # Change to job directory
            original_cwd = os.getcwd()
            os.chdir(job["job_dir"])
            
            # Run scrapy command
            cmd = [
                "scrapy", "crawl", "aimdoc", 
                "-a", f"manifest={job['manifest_path']}",
                "-o", f"{job['build_dir']}/items.json"
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=original_cwd  # Run from original project root
            )
            
            self.job_processes[job_id] = process
            
            # Monitor process asynchronously instead of blocking
            stdout, stderr, return_code = await self._monitor_process(job_id, process)
            
            # Update job status based on scraped content first, then return code
            build_path = Path(job["build_dir"])
            items_file = build_path / "items.json"
            
            scraped_items = 0
            if items_file.exists():
                try:
                    import json
                    with open(items_file, 'r', encoding='utf-8') as f:
                        items = json.load(f)
                        scraped_items = len(items) if isinstance(items, list) else 0
                except (json.JSONDecodeError, FileNotFoundError):
                    scraped_items = 0
            
            if scraped_items > 0:
                # Success: pages were scraped regardless of return code
                job["status"] = JobStatus.COMPLETED
                job["completed_at"] = datetime.now()
                
                # Count all files created
                if build_path.exists():
                    files = list(build_path.glob("**/*"))
                    file_count = len([f for f in files if f.is_file()])
                    total_size = sum(f.stat().st_size for f in files if f.is_file())
                else:
                    file_count = 0
                    total_size = 0
                
                job["result_summary"] = {
                    "files_created": file_count,
                    "pages_scraped": scraped_items,
                    "build_size": total_size,
                    "build_path": str(build_path)
                }
                job["progress"]["pages_scraped"] = scraped_items
                job["progress"]["files_created"] = file_count
            elif return_code == 0:
                # Scrapy completed successfully but found no pages
                job["status"] = JobStatus.FAILED
                job["error_message"] = f"No pages were scraped (Scrapy completed but found 0 items)"
                job["completed_at"] = datetime.now()
            else:
                # Scrapy failed
                job["status"] = JobStatus.FAILED
                job["error_message"] = f"Scrapy failed with code {return_code}: {stderr}"
                job["completed_at"] = datetime.now()
        
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error_message"] = str(e)
            job["completed_at"] = datetime.now()
        
        finally:
            # Clean up process reference
            if job_id in self.job_processes:
                del self.job_processes[job_id]
            
            os.chdir(original_cwd)
    
    async def _monitor_process(self, job_id: str, process: subprocess.Popen, timeout: int = 600):
        """Monitor process asynchronously without blocking the API"""
        start_time = datetime.now()
        
        while True:
            # Check if process is still running
            return_code = process.poll()
            
            if return_code is not None:
                # Process completed, collect output
                stdout, stderr = process.communicate()
                return stdout, stderr, return_code
            
            # Check for timeout (default 10 minutes)
            if (datetime.now() - start_time).total_seconds() > timeout:
                print(f"Job {job_id} timed out after {timeout} seconds, terminating")
                process.terminate()
                try:
                    # Give process 5 seconds to terminate gracefully
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    process.kill()
                    stdout, stderr = process.communicate()
                return stdout, stderr, -1
            
            # Sleep for 1 second before checking again (non-blocking)
            await asyncio.sleep(1)
    
    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get job status"""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        return JobStatusResponse(
            job_id=job_id,
            status=job["status"],
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            progress=job.get("progress"),
            error_message=job.get("error_message"),
            result_summary=job.get("result_summary")
        )
    
    def list_jobs(self, limit: Optional[int] = None) -> List[JobStatusResponse]:
        """List all jobs"""
        jobs = []
        for job_id in sorted(self.jobs.keys(), reverse=True):  # Most recent first
            jobs.append(self.get_job_status(job_id))
        
        if limit:
            jobs = jobs[:limit]
        
        return jobs
    
    def get_job_results(self, job_id: str) -> Optional[JobResults]:
        """Get job results"""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        if job["status"] != JobStatus.COMPLETED:
            return None
        
        build_path = Path(job["build_dir"])
        if not build_path.exists():
            return None
        
        # List all files in build directory
        files = []
        for file_path in build_path.glob("**/*"):
            if file_path.is_file():
                files.append(str(file_path.relative_to(build_path)))
        
        return JobResults(
            job_id=job_id,
            status=job["status"],
            files=files,
            build_path=str(build_path),
            metadata=job.get("result_summary", {})
        )
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its files"""
        if job_id not in self.jobs:
            return False
        
        # Kill process if running
        if job_id in self.job_processes:
            try:
                self.job_processes[job_id].terminate()
                del self.job_processes[job_id]
            except:
                pass
        
        # Remove job directory
        job_dir = Path(self.jobs[job_id]["job_dir"])
        if job_dir.exists():
            shutil.rmtree(job_dir)
        
        # Remove from memory
        del self.jobs[job_id]
        
        return True


# Global job service instance
job_service = JobService()