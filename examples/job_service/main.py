import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from orga.model import OrgaConfig
from orga.pipeline import OrgaPipeline

app = FastAPI(title="ORGA Job Service")

# In-memory store (for MVP)
job_store: dict[str, Any] = {}

class JobSubmitRequest(BaseModel):
    urls: list[str]
    config: dict[str, Any] | None = None

class JobResponse(BaseModel):
    id: str
    status: str
    submitted_at: datetime
    completed_at: datetime | None = None
    results: list[dict[str, Any]] = []
    errors: list[str] = []

# Global pipeline
pipeline = OrgaPipeline(OrgaConfig())

async def process_job(job_id: str, urls: list[str], custom_config: dict[str, Any] | None):
    job = job_store[job_id]
    job["status"] = "processing"
    
    # Use custom config if provided, else global default
    if custom_config:
        processor = OrgaPipeline(OrgaConfig(**custom_config))
    else:
        processor = pipeline

    results = []
    errors = []
    
    # Semaphore for job-level concurrency if needed, but Pipeline has global semaphore.
    # We rely on pipeline's fetcher semaphore for global rate limiting.
    # We can run these in parallel.
    
    async def _process_one(url):
        try:
            # Pass job_id as trace_id via context if we had a tracing system
            profile = await processor.run_from_url(url)
            # Serialize for storage
            return profile.model_dump()
        except Exception as e:
            import traceback
            print(f"ERROR processing {url}:")
            traceback.print_exc()
            # We don't want one failure to crash the whole job
            errors.append(f"Failed {url}: {e!s}")
            return None

    # Run all URLs concurrently
    # Note: OrgaPipeline.run_from_url also does internal concurrency for sub-pages.
    # HttpxFetcher's global semaphore will limit total active requests.
    tasks = [_process_one(u) for u in urls]
    task_results = await asyncio.gather(*tasks)
    
    for res in task_results:
        if res:
            results.append(res)
            
    job["results"] = results
    job["errors"] = errors
    job["status"] = "completed"
    job["completed_at"] = datetime.utcnow()

@app.post("/jobs", status_code=202)
async def submit_job(request: JobSubmitRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job_doc = {
        "id": job_id,
        "status": "pending",
        "submitted_at": datetime.utcnow(),
        "urls": request.urls,
        "results": [],
        "errors": []
    }
    job_store[job_id] = job_doc
    
    background_tasks.add_task(process_job, job_id, request.urls, request.config)
    
    return {"job_id": job_id, "status": "pending"}

@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_store[job_id]

@app.get("/health")
def health_check():
    return {"status": "ok", "jobs_count": len(job_store)}
