from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import jobs

# Create FastAPI app
app = FastAPI(
    title="Aimdoc API",
    description="API for AI-friendly documentation scraping",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Aimdoc API",
        "version": "1.0.0",
        "description": "API for AI-friendly documentation scraping",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "POST /api/v1/scrape": "Create and start a new scrape job",
            "GET /api/v1/jobs": "List all jobs",
            "GET /api/v1/jobs/{job_id}": "Get job status",
            "GET /api/v1/jobs/{job_id}/results": "Get job results",
            "GET /api/v1/jobs/{job_id}/download/{file_path}": "Download job file",
            "DELETE /api/v1/jobs/{job_id}": "Delete job",
            "POST /api/v1/jobs/{job_id}/cancel": "Cancel running job"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)