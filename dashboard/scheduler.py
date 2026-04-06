import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Coroutine
from croniter import croniter

from dashboard.policy_engine import engine as policy_engine

logger = logging.getLogger(__name__)

SCHEDULES_FILE = Path.home() / ".ostwin" / "dashboard" / "schedules.json"

class Job:
    def __init__(
        self,
        job_id: str,
        name: str,
        task_type: str,
        task_params: Dict[str, Any],
        interval_seconds: Optional[int] = None,
        cron: Optional[str] = None,
        last_run: Optional[str] = None,
        enabled: bool = True
    ):
        self.job_id = job_id
        self.name = name
        self.interval_seconds = interval_seconds
        self.cron = cron
        self.task_type = task_type
        self.task_params = task_params
        self.last_run = last_run
        self.enabled = enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "cron": self.cron,
            "task_type": self.task_type,
            "task_params": self.task_params,
            "last_run": self.last_run,
            "enabled": self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            job_id=data["job_id"],
            name=data["name"],
            interval_seconds=data.get("interval_seconds"),
            cron=data.get("cron"),
            task_type=data["task_type"],
            task_params=data["task_params"],
            last_run=data.get("last_run"),
            enabled=data.get("enabled", True)
        )

class Scheduler:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._load_jobs()

    def _load_jobs(self):
        if SCHEDULES_FILE.exists():
            try:
                data = json.loads(SCHEDULES_FILE.read_text())
                for job_data in data:
                    job = Job.from_dict(job_data)
                    self.jobs[job.job_id] = job
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")

    def _save_jobs(self):
        SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [job.to_dict() for job in self.jobs.values()]
            SCHEDULES_FILE.write_text(json.dumps(data, indent=4))
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")

    def add_job(self, name: str, task_type: str, task_params: Dict[str, Any], interval_seconds: Optional[int] = None, cron: Optional[str] = None) -> str:
        job_id = str(uuid.uuid4())
        job = Job(job_id, name, task_type, task_params, interval_seconds=interval_seconds, cron=cron)
        self.jobs[job_id] = job
        self._save_jobs()
        if job.enabled:
            self._start_job_task(job)
        return job_id

    def remove_job(self, job_id: str):
        if job_id in self.jobs:
            self._stop_job_task(job_id)
            del self.jobs[job_id]
            self._save_jobs()

    def update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            job = self.jobs[job_id]
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            self._save_jobs()
            if job.enabled:
                self._start_job_task(job)
            else:
                self._stop_job_task(job_id)

    def start_all(self):
        for job in self.jobs.values():
            if job.enabled:
                self._start_job_task(job)

    def _start_job_task(self, job: Job):
        self._stop_job_task(job.job_id)
        task = asyncio.create_task(self._job_loop(job))
        self.running_tasks[job.job_id] = task

    def _stop_job_task(self, job_id: str):
        task = self.running_tasks.pop(job_id, None)
        if task:
            task.cancel()

    async def _job_loop(self, job: Job):
        logger.info(f"Starting job loop for {job.name} ({job.job_id})")
        while True:
            try:
                now = datetime.now()
                if job.cron:
                    it = croniter(job.cron, now)
                    next_run = it.get_next(datetime)
                    wait_seconds = (next_run - now).total_seconds()
                    if wait_seconds < 0:
                        wait_seconds = 0
                elif job.interval_seconds:
                    wait_seconds = job.interval_seconds
                else:
                    logger.error(f"Job {job.job_id} has neither cron nor interval_seconds")
                    break

                logger.debug(f"Job {job.name} sleeping for {wait_seconds}s")
                await asyncio.sleep(wait_seconds)
                
                if not job.enabled:
                    continue

                logger.info(f"Running job: {job.name} ({job.job_id})")
                await self._execute_job(job)
                
                job.last_run = datetime.now(timezone.utc).isoformat()
                self._save_jobs()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job loop {job.name}: {e}")
                await asyncio.sleep(60)

    async def _execute_job(self, job: Job):
        if job.task_type == "policy":
            policy_id = job.task_params.get("policy_id")
            if policy_id:
                try:
                    await policy_engine.execute(policy_id, trigger_context={"job_id": job.job_id})
                except Exception as e:
                    logger.error(f"Failed to execute policy {policy_id} for job {job.job_id}: {e}")
        else:
            # Fallback for old style jobs if any
            try:
                from dashboard.policies import PolicyEngine
                old_engine = PolicyEngine()
                await old_engine.execute_workflow(job.task_type, job.task_params)
            except Exception as e:
                logger.error(f"Failed to execute old style task {job.task_type}: {e}")

# Singleton instance
scheduler = Scheduler()
