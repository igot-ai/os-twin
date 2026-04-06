import asyncio
import pytest
import os
from dashboard.scheduler import scheduler
from dashboard.policies import policy_engine

@pytest.mark.asyncio
async def test_policy_engine_direct():
    params = {
        "fetcher": "mock",
        "fetch_params": {"mock_data": "Hello from Mock!"},
        "processor": "summarize",
        "process_params": {},
        "reactor": "mock",
        "react_params": {}
    }
    await policy_engine.execute_workflow("test_workflow", params)

@pytest.mark.asyncio
async def test_scheduler_job_lifecycle():
    params = {
        "fetcher": "mock",
        "fetch_params": {"mock_data": "Hello from Mock!"},
        "processor": "summarize",
        "process_params": {},
        "reactor": "mock",
        "react_params": {}
    }
    
    job_id = scheduler.add_job(
        name="Test Interval Job",
        interval_seconds=1,
        task_type="test_workflow",
        task_params=params
    )
    assert job_id in scheduler.jobs
    
    # Manually start the job loop for testing
    task = asyncio.create_task(scheduler._job_loop(scheduler.jobs[job_id]))
    await asyncio.sleep(1.5)
    
    job = scheduler.jobs[job_id]
    assert job.last_run is not None
    
    task.cancel()
    scheduler.remove_job(job_id)
    assert job_id not in scheduler.jobs

@pytest.mark.asyncio
async def test_scheduler_persistence():
    # Job should be saved to disk
    from pathlib import Path
    import json
    schedules_file = Path.home() / ".ostwin" / "dashboard" / "schedules.json"
    assert schedules_file.exists()
    
    data = json.loads(schedules_file.read_text())
    assert isinstance(data, list)
