import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dashboard.scheduler import scheduler
from dashboard.policies import policy_engine

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

class JobRequest(BaseModel):
    name: str
    interval_seconds: int
    task_type: str
    task_params: Dict[str, Any] = Field(default_factory=dict)

class JobResponse(BaseModel):
    job_id: str
    name: str
    interval_seconds: int
    task_type: str
    task_params: Dict[str, Any]
    last_run: Optional[str] = None
    enabled: bool

@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs():
    return [job.to_dict() for job in scheduler.jobs.values()]

@router.post("/jobs", response_model=JobResponse)
async def create_job(req: JobRequest):
    job_id = scheduler.add_job(
        name=req.name,
        interval_seconds=req.interval_seconds,
        task_type=req.task_type,
        task_params=req.task_params
    )
    return scheduler.jobs[job_id].to_dict()

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    if job_id not in scheduler.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    scheduler.remove_job(job_id)
    return {"status": "success"}

@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str, background_tasks: BackgroundTasks):
    if job_id not in scheduler.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = scheduler.jobs[job_id]
    background_tasks.add_task(scheduler.execute_task, job)
    return {"status": "triggered"}

@router.get("/policy/fetchers")
async def list_fetchers():
    return list(policy_engine.registered_fetchers.keys())

@router.get("/policy/processors")
async def list_processors():
    return list(policy_engine.registered_processors.keys())

@router.get("/policy/reactors")
async def list_reactors():
    return list(policy_engine.registered_reactors.keys())
