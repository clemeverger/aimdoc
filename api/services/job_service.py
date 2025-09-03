import asyncio
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import subprocess
import shutil
from fastapi import WebSocket

from ..models import JobStatus, ScrapeRequest, JobStatusResponse, JobResults


class JobService:
    """Service for managing scrapy jobs"""
    
    def __init__(self):
        # In-memory job storage (in production, use a database)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_processes: Dict[str, subprocess.Popen] = {}
        
        # WebSocket connections for real-time updates
        self.websocket_connections: Dict[str, Set[WebSocket]] = {}
        
        # Ensure jobs directory exists
        project_root = Path(__file__).parent.parent.parent  # Go up to project root
        self.jobs_dir = project_root / "jobs"
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
        print(f"[{datetime.now()}] START_JOB: Starting job {job_id}")
        
        if job_id not in self.jobs:
            print(f"[{datetime.now()}] START_JOB: Job {job_id} not found")
            return False
        
        job = self.jobs[job_id]
        if job["status"] != JobStatus.PENDING:
            print(f"[{datetime.now()}] START_JOB: Job {job_id} status is {job['status']}, not PENDING")
            return False
        
        # Update job status
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.now()
        print(f"[{datetime.now()}] START_JOB: Job {job_id} status updated to RUNNING")
        
        # Start scrapy process asynchronously
        print(f"[{datetime.now()}] START_JOB: Creating asyncio task for _run_scrapy")
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
        print(f"[{datetime.now()}] RUN_SCRAPY: Starting _run_scrapy for job {job_id}")
        job = self.jobs[job_id]
        
        try:
            # Send initial update
            print(f"[{datetime.now()}] RUN_SCRAPY: Broadcasting initial update")
            await self.broadcast_job_update(job_id, {
                "type": "status_update",
                "status": "running",
                "message": "Starting scrape process...",
                "progress": job.get("progress", {})
            })
            
            # Change to job directory
            original_cwd = os.getcwd()
            print(f"[{datetime.now()}] RUN_SCRAPY: Original CWD: {original_cwd}")
            print(f"[{datetime.now()}] RUN_SCRAPY: Job dir: {job['job_dir']}")
            os.chdir(job["job_dir"])
            
            # Run scrapy command
            cmd = [
                "scrapy", "crawl", "aimdoc", 
                "-a", f"manifest={job['manifest_path']}",
                "-o", f"{job['build_dir']}/items.json"
            ]
            print(f"[{datetime.now()}] RUN_SCRAPY: Command to run: {' '.join(cmd)}")
            print(f"[{datetime.now()}] RUN_SCRAPY: Build dir: {job['build_dir']}")
            print(f"[{datetime.now()}] RUN_SCRAPY: Manifest path: {job['manifest_path']}")
            
            print(f"[{datetime.now()}] RUN_SCRAPY: Creating subprocess...")
            # Run Scrapy with logs visible by not capturing stdout/stderr
            process = subprocess.Popen(
                cmd,
                stdout=None,  # Let stdout go to console
                stderr=None,  # Let stderr go to console  
                text=True,
                cwd=original_cwd  # Run from original project root
            )
            
            print(f"[{datetime.now()}] RUN_SCRAPY: Process created with PID: {process.pid}")
            self.job_processes[job_id] = process
            
            # Monitor process asynchronously instead of blocking
            print(f"[{datetime.now()}] RUN_SCRAPY: Starting process monitoring...")
            stdout, stderr, return_code = await self._monitor_process(job_id, process)
            print(f"[{datetime.now()}] RUN_SCRAPY: Process finished with return code: {return_code}")
            
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
                
                # Send completion update
                await self.broadcast_job_update(job_id, {
                    "type": "status_update",
                    "status": "completed",
                    "message": f"Scraping completed! Created {file_count} files from {scraped_items} pages",
                    "progress": job["progress"],
                    "result_summary": job["result_summary"]
                })
            elif return_code == 0:
                # Scrapy completed successfully but found no pages
                job["status"] = JobStatus.FAILED
                job["error_message"] = f"No pages were scraped (Scrapy completed but found 0 items)"
                job["completed_at"] = datetime.now()
                
                await self.broadcast_job_update(job_id, {
                    "type": "status_update",
                    "status": "failed",
                    "message": "No pages were scraped",
                    "error": job["error_message"]
                })
            else:
                # Scrapy failed
                job["status"] = JobStatus.FAILED
                job["error_message"] = f"Scrapy failed with code {return_code}: {stderr}"
                job["completed_at"] = datetime.now()
                
                await self.broadcast_job_update(job_id, {
                    "type": "status_update",
                    "status": "failed",
                    "message": f"Scraping failed (code {return_code})",
                    "error": job["error_message"]
                })
        
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error_message"] = str(e)
            job["completed_at"] = datetime.now()
            
            await self.broadcast_job_update(job_id, {
                "type": "status_update",
                "status": "failed",
                "message": "An error occurred during scraping",
                "error": str(e)
            })
        
        finally:
            # Clean up process reference
            if job_id in self.job_processes:
                del self.job_processes[job_id]
            
            os.chdir(original_cwd)
    
    async def _monitor_process(self, job_id: str, process: subprocess.Popen, timeout: int = 600):
        """Monitor process asynchronously without blocking the API"""
        start_time = datetime.now()
        print(f"[{datetime.now()}] MONITOR: Starting monitoring for job {job_id}, PID {process.pid}")
        
        loop_count = 0
        while True:
            loop_count += 1
            if loop_count % 10 == 0:  # Log every 10 seconds
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"[{datetime.now()}] MONITOR: Job {job_id} still running, elapsed: {elapsed:.1f}s")
            
            # Check if process is still running
            return_code = process.poll()
            
            if return_code is not None:
                # Process completed
                print(f"[{datetime.now()}] MONITOR: Process completed with return code {return_code}")
                return "", "", return_code
            
            # Check for timeout (default 10 minutes)
            if (datetime.now() - start_time).total_seconds() > timeout:
                print(f"[{datetime.now()}] MONITOR: Job {job_id} timed out after {timeout} seconds, terminating")
                process.terminate()
                try:
                    # Give process 5 seconds to terminate gracefully
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    print(f"[{datetime.now()}] MONITOR: Force killing process {process.pid}")
                    process.kill()
                    process.wait()
                return "", "", -1
            
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
    
    async def add_websocket_connection(self, job_id: str, websocket: WebSocket):
        """Add a WebSocket connection for a job"""
        if job_id not in self.websocket_connections:
            self.websocket_connections[job_id] = set()
        self.websocket_connections[job_id].add(websocket)
    
    async def remove_websocket_connection(self, job_id: str, websocket: WebSocket):
        """Remove a WebSocket connection for a job"""
        if job_id in self.websocket_connections:
            self.websocket_connections[job_id].discard(websocket)
            if not self.websocket_connections[job_id]:
                del self.websocket_connections[job_id]
    
    async def broadcast_job_update(self, job_id: str, update: Dict[str, Any]):
        """Broadcast job update to all connected WebSocket clients"""
        if job_id in self.websocket_connections:
            disconnected = set()
            for websocket in self.websocket_connections[job_id].copy():
                try:
                    await websocket.send_json(update)
                except Exception:
                    disconnected.add(websocket)
            
            # Remove disconnected websockets
            for websocket in disconnected:
                self.websocket_connections[job_id].discard(websocket)
    
    def create_zip_download(self, job_id: str) -> Optional[str]:
        """Create a ZIP file of job results for download"""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        if job["status"] != JobStatus.COMPLETED:
            return None
        
        build_path = Path(job["build_dir"])
        if not build_path.exists():
            return None
        
        # Create ZIP file
        zip_path = build_path.parent / f"{job['request']['name']}-results.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in build_path.glob("**/*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(build_path)
                    zipf.write(file_path, arcname)
        
        return str(zip_path)


# Global job service instance
job_service = JobService()