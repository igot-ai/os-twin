import asyncio
import json
import os
from dashboard.scheduler import scheduler
from dashboard.policies import policy_engine

async def test_scheduler_and_policy():
    print("Testing Scheduler and Policy Engine...")
    
    # 1. Test Policy Engine Execution
    print("\n1. Testing Policy Engine Execution (Direct)")
    params = {
        "fetcher": "mock",
        "fetch_params": {"mock_data": "Hello from Mock!"},
        "processor": "summarize",
        "process_params": {},
        "reactor": "mock",
        "react_params": {}
    }
    await policy_engine.execute_workflow("test_workflow", params)
    print("Policy Engine execution finished.")

    # 2. Test Scheduler Job Addition
    print("\n2. Testing Scheduler Job Addition")
    job_id = scheduler.add_job(
        name="Test Interval Job",
        interval_seconds=2,
        task_type="test_workflow",
        task_params=params
    )
    print(f"Added job {job_id}")
    
    # Wait for a couple of cycles
    print("Waiting 5 seconds for scheduler to trigger...")
    # Since we call start_all() in tasks.py, we should manually start it here for testing if we don't start the whole app
    scheduler._start_job_task(scheduler.jobs[job_id])
    await asyncio.sleep(5)
    
    job = scheduler.jobs[job_id]
    print(f"Job last run: {job.last_run}")
    
    if job.last_run:
        print("✅ Scheduler triggered successfully")
    else:
        print("❌ Scheduler failed to trigger")

    # 3. Clean up
    scheduler.remove_job(job_id)
    print(f"Removed job {job_id}")

if __name__ == "__main__":
    # Ensure logs are visible
    import logging
    logging.basicConfig(level=logging.INFO)
    
    asyncio.run(test_scheduler_and_policy())
