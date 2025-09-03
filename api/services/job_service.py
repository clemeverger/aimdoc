import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
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
            "output": {"mode": "bundle"}  # Always use bundle mode
        }
        
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
            "progress": {"pages_found": 0, "pages_scraped": 0, "files_created": 0}
        }
        
        return job_id
    
    async def start_job(self, job_id: str) -> bool:
        """Start a scrape job"""
        print(f"[{datetime.now()}] START_JOB: Starting job {job_id}")
        
        # Clean up old jobs before starting new one
        self.cleanup_old_jobs()
        
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
    
    def cleanup_old_jobs(self):
        """Clean up jobs older than 24 hours to prevent memory leaks"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        old_jobs = []
        
        for job_id, job_data in self.jobs.items():
            job_created = job_data.get("created_at")
            if job_created and job_created < cutoff_time:
                old_jobs.append(job_id)
        
        for job_id in old_jobs:
            print(f"[{datetime.now()}] CLEANUP: Removing old job {job_id}")
            self.delete_job(job_id)
    
    async def _run_scrapy(self, job_id: str):
        """Run scrapy in a subprocess"""
        print(f"[{datetime.now()}] RUN_SCRAPY: Starting _run_scrapy for job {job_id}")
        job = self.jobs[job_id]
        
        try:
            # Send initial update - discovering phase
            print(f"[{datetime.now()}] RUN_SCRAPY: Broadcasting initial update")
            await self.broadcast_job_update(job_id, {
                "type": "status_update",
                "status": "running",
                "phase": "discovering",
                "message": "Discovering sitemap and pages...",
                "progress": job.get("progress", {})
            })
            
            # Get paths
            original_cwd = os.getcwd()
            job_dir = job["job_dir"]
            print(f"[{datetime.now()}] RUN_SCRAPY: Original CWD: {original_cwd}")
            print(f"[{datetime.now()}] RUN_SCRAPY: Job dir: {job_dir}")
            
            # No need to change directory since we pass job_dir explicitly to the spider
            
            # Run scrapy command with reduced logging
            cmd = [
                "scrapy", "crawl", "aimdoc", 
                "-a", f"manifest={job['manifest_path']}",
                "-a", f"job_dir={job_dir}",
                "-L", "WARNING"  # Only show WARNING and ERROR logs
            ]
            print(f"[{datetime.now()}] RUN_SCRAPY: Command to run: {' '.join(cmd)}")
            print(f"[{datetime.now()}] RUN_SCRAPY: Job dir: {job['job_dir']}")
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
            
            # Update job status based on scraped content from summary file
            job_path = Path(job["job_dir"])
            summary_file = job_path / "scraping_summary.json"
            
            scraped_items = 0
            failed_pages = 0
            discovered_pages = 0
            
            # Get info from summary file (main source now that items.json is removed)
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                        scraped_items = summary.get("pages_scraped", 0)
                        failed_pages = summary.get("pages_failed", 0)
                        discovered_pages = summary.get("pages_discovered", 0)
                        print(f"[{datetime.now()}] RUN_SCRAPY: Summary - Discovered: {discovered_pages}, Scraped: {scraped_items}, Failed: {failed_pages}")
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"[{datetime.now()}] RUN_SCRAPY: Failed to read summary: {e}")
            else:
                print(f"[{datetime.now()}] RUN_SCRAPY: No scraping summary found")
            
            if scraped_items > 0:
                # Success: pages were scraped regardless of return code
                job["status"] = JobStatus.COMPLETED
                job["completed_at"] = datetime.now()
                
                # Count all files created
                if job_path.exists():
                    # The actual content is in a docs subdirectory named after the project
                    project_name = job["request"].get("name", "default-project")
                    content_path = job_path / "docs" / project_name
                    
                    # Check for new structure first
                    if content_path.exists():
                        files = list(content_path.glob("**/*"))
                        file_count = len([f for f in files if f.is_file()])
                        total_size = sum(f.stat().st_size for f in files if f.is_file())
                    else:
                        # Fallback to old structure for compatibility
                        legacy_path = job_path / project_name
                        if legacy_path.exists():
                            files = list(legacy_path.glob("**/*"))
                            file_count = len([f for f in files if f.is_file()])
                            total_size = sum(f.stat().st_size for f in files if f.is_file())
                        else:
                            file_count = 0
                            total_size = 0
                else:
                    file_count = 0
                    total_size = 0
                
                job["result_summary"] = {
                    "files_created": file_count,
                    "pages_scraped": scraped_items,
                    "pages_failed": failed_pages,
                    "pages_discovered": discovered_pages,
                    "build_size": total_size,
                    "build_path": str(job_path)
                }
                job["progress"]["pages_scraped"] = scraped_items
                job["progress"]["files_created"] = file_count
                
                # Create completion message with failure info if relevant
                if failed_pages > 0:
                    message = f"Scraping completed with some issues! Created {file_count} files from {scraped_items} pages ({failed_pages} pages failed)"
                else:
                    message = f"Scraping completed successfully! Created {file_count} files from {scraped_items} pages"
                
                # Send completion update
                await self.broadcast_job_update(job_id, {
                    "type": "status_update",
                    "status": "completed",
                    "phase": "completed",
                    "message": message,
                    "progress": job["progress"],
                    "result_summary": job["result_summary"]
                })
            elif return_code == 0:
                # Scrapy completed successfully but found no pages
                # Try to get more detailed error information from scraping summary
                detailed_error = await self._get_detailed_error_message(job_dir)
                
                job["status"] = JobStatus.FAILED
                job["error_message"] = detailed_error
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
    
    async def _monitor_process(self, job_id: str, process: subprocess.Popen, timeout: int = 1800):
        """Monitor process asynchronously without blocking the API"""
        start_time = datetime.now()
        print(f"[{datetime.now()}] MONITOR: Starting monitoring for job {job_id}, PID {process.pid}")
        
        job = self.jobs[job_id]
        progress_file = os.path.join(job["job_dir"], "progress.json")
        last_item_count = 0
        last_update_time = start_time
        current_phase = "discovering"
        sitemap_discovery_complete = False
        
        loop_count = 0
        while True:
            loop_count += 1
            current_time = datetime.now()
            
            # Check if process is still running
            return_code = process.poll()
            
            if return_code is not None:
                # Process completed
                print(f"[{datetime.now()}] MONITOR: Process completed with return code {return_code}")
                return "", "", return_code
            
            # Check progress every second for responsive WebSocket updates
            try:
                current_item_count = 0
                current_files_count = 0
                
                # Check for progress file from spider and detect phase transitions
                print(f"[{datetime.now()}] MONITOR: Checking for progress file: {progress_file}, exists: {os.path.exists(progress_file)}")
                if os.path.exists(progress_file):
                        try:
                            with open(progress_file, 'r', encoding='utf-8') as f:
                                progress_data = json.load(f)
                                print(f"[{datetime.now()}] MONITOR: Progress data: {progress_data}")
                                # Check if sitemap discovery is complete
                                if not sitemap_discovery_complete and progress_data.get("sitemap_processed", False):
                                    sitemap_discovery_complete = True
                                    current_phase = "scraping"
                                    job["progress"]["pages_found"] = progress_data.get("pages_found", 0)
                                    
                                    # Send phase transition update
                                    await self.broadcast_job_update(job_id, {
                                        "type": "status_update",
                                        "status": "running",
                                        "phase": "scraping",
                                        "message": f"Starting to scrape {job['progress']['pages_found']} pages...",
                                        "progress": job["progress"]
                                    })
                                    print(f"[{datetime.now()}] MONITOR: Phase transition to scraping - {job['progress']['pages_found']} pages found")
                                
                                # Update progress data from spider
                                if progress_data.get("pages_found", 0) > 0:
                                    job["progress"]["pages_found"] = progress_data["pages_found"]
                                
                                # Use spider's progress tracking for pages_scraped and files_created
                                if "pages_scraped" in progress_data:
                                    job["progress"]["pages_scraped"] = progress_data["pages_scraped"]
                                if "files_created" in progress_data:
                                    job["progress"]["files_created"] = progress_data["files_created"]
                        except Exception as e:
                            print(f"[{datetime.now()}] MONITOR: Error reading progress file: {e}")
                
                # Count files created in real-time
                current_files_count = 0
                project_name = job["request"].get("name", "default-project")
                docs_path = Path(job["job_dir"]) / "docs" / project_name
                
                print(f"[{datetime.now()}] MONITOR: Looking for files in: {docs_path}, exists: {docs_path.exists()}")
                
                if docs_path.exists():
                    try:
                        files = list(docs_path.glob("**/*"))
                        file_files = [f for f in files if f.is_file()]
                        current_files_count = len(file_files)
                        print(f"[{datetime.now()}] MONITOR: Found {current_files_count} files in {docs_path}")
                    except Exception as e:
                        print(f"[{datetime.now()}] MONITOR: Error counting files: {e}")
                
                # Detect converting phase when files start being created
                if current_phase == "scraping" and current_files_count > 0 and job["progress"].get("files_created", 0) == 0:
                    current_phase = "converting"
                    await self.broadcast_job_update(job_id, {
                        "type": "status_update",
                        "status": "running",
                        "phase": "converting",
                        "message": "Converting pages to markdown...",
                        "progress": job["progress"]
                    })
                    print(f"[{datetime.now()}] MONITOR: Phase transition to converting")
                
                # Send update if progress changed or more frequently during scraping
                time_since_last_update = (current_time - last_update_time).total_seconds()
                
                # Use fallback counts only if progress.json data is not available
                current_pages_scraped = job["progress"].get("pages_scraped", current_item_count)
                current_files_created = job["progress"].get("files_created", current_files_count)
                
                files_changed = current_files_created != job["progress"].get("files_created", 0)
                # More frequent updates during scraping phase, less frequent otherwise
                update_threshold = 1 if current_phase == "scraping" else 5
                if current_pages_scraped != last_item_count or files_changed or time_since_last_update >= update_threshold:
                    # Only update with fallback data if progress.json doesn't have the data
                    if "pages_scraped" not in job["progress"] or job["progress"]["pages_scraped"] == 0:
                        job["progress"]["pages_scraped"] = current_item_count
                    if "files_created" not in job["progress"] or job["progress"]["files_created"] == 0:
                        job["progress"]["files_created"] = current_files_count
                    
                    # Create phase-appropriate message
                    if current_phase == "discovering":
                        message = "Discovering sitemap and pages..."
                    elif current_phase == "scraping":
                        message = f"Scraping pages... {job['progress'].get('pages_scraped', 0)}/{job['progress'].get('pages_found', 0)} completed"
                    elif current_phase == "converting":
                        message = f"Converting to markdown... {job['progress'].get('files_created', 0)} files created"
                    else:
                        message = f"Processing... {job['progress'].get('pages_scraped', 0)} pages scraped, {job['progress'].get('files_created', 0)} files created"
                    
                    # Send WebSocket update
                    await self.broadcast_job_update(job_id, {
                        "type": "status_update",
                        "status": "running",
                        "phase": current_phase,
                        "message": message,
                        "progress": job["progress"]
                    })
                    
                    last_item_count = job["progress"].get("pages_scraped", current_item_count)
                    last_update_time = current_time
                    print(f"[{datetime.now()}] MONITOR: Progress update [{current_phase}] - {job['progress'].get('pages_scraped', 0)} pages scraped, {job['progress'].get('pages_found', 0)} pages found, {job['progress'].get('files_created', 0)} files created")
                
            except Exception as e:
                print(f"[{datetime.now()}] MONITOR: Error reading progress: {e}")
            
            # Log every 30 seconds to reduce noise
            if loop_count % 30 == 0:
                elapsed = (current_time - start_time).total_seconds()
                pages_scraped = job["progress"].get("pages_scraped", last_item_count)
                print(f"[{datetime.now()}] MONITOR: Job {job_id} still running, elapsed: {elapsed:.1f}s, {pages_scraped} pages scraped")
            
            # Check for timeout (30 minutes instead of 60 to prevent Render shutdown)
            if (current_time - start_time).total_seconds() > timeout:
                print(f"[{datetime.now()}] MONITOR: Job {job_id} timed out after {timeout} seconds (30 min), terminating")
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
            
            # Sleep for 1 second, but check progress every 5 iterations (5 seconds)
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
            result_summary=job.get("result_summary"),
            request=job.get("request")
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
        
        job_path = Path(job["job_dir"])
        if not job_path.exists():
            return None
        
        # The actual content is in a docs subdirectory inside the job directory
        project_name = job["request"].get("name", "default-project")
        content_path = job_path / "docs" / project_name
        
        # Check if the content path exists
        if not content_path.exists():
            return None

        # List all files in the docs directory
        files = []
        try:
            for file_path in content_path.glob("**/*"):
                if file_path.is_file():
                    files.append(str(file_path.relative_to(content_path)))
        except Exception:
            # Handle any file system errors gracefully
            pass
        
        return JobResults(
            job_id=job_id,
            status=job["status"],
            files=files,
            build_path=str(content_path),
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
    

    
    async def _get_detailed_error_message(self, job_dir: Path) -> str:
        """Get detailed error message from scraping summary if available"""
        try:
            summary_file = job_dir / "scraping_summary.json"
            if summary_file.exists():
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                
                discovery_errors = summary.get('discovery_errors', [])
                pages_discovered = summary.get('pages_discovered', 0)
                pages_failed = summary.get('pages_failed', 0)
                
                if discovery_errors:
                    # Site has no sitemap or sitemap discovery failed
                    sitemap_errors = [e for e in discovery_errors if 'sitemap' in e.get('url', '').lower()]
                    robots_errors = [e for e in discovery_errors if 'robots.txt' in e.get('url', '').lower()]
                    
                    if sitemap_errors or robots_errors:
                        error_msg = "No sitemap found for this website. "
                        if robots_errors:
                            error_msg += "robots.txt was not accessible, "
                        if sitemap_errors:
                            error_msg += f"tried {len(sitemap_errors)} sitemap URL(s) but none were found. "
                        
                        error_msg += "This website might not have a sitemap, or it might be located at a non-standard path. "
                        error_msg += "Try using a website that has a sitemap.xml file, or contact the site owner to add one."
                        return error_msg
                
                if pages_discovered == 0:
                    return "No pages were discovered. The website might not have a sitemap or the sitemap might be empty."
                elif pages_failed > 0:
                    return f"Discovered {pages_discovered} pages but all {pages_failed} failed to scrape. Check the website's accessibility and structure."
                else:
                    return "No pages were scraped despite successful discovery. This might be due to content filtering or parsing issues."
            
        except Exception as e:
            print(f"Error reading scraping summary: {e}")
        
        # Fallback generic message
        return "No pages were scraped (Scrapy completed but found 0 items). The website might not have a sitemap or the content might not be accessible."


# Global job service instance
job_service = JobService()