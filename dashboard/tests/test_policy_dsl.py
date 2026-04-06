import pytest
import asyncio
from datetime import datetime
from dashboard.policy_models import Policy, Trigger, PipelineAction
from dashboard.policy_engine import PolicyEngine
from dashboard.scheduler import Scheduler
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.fixture
def engine():
    return PolicyEngine()

@pytest.fixture
def scheduler():
    return Scheduler()

@pytest.mark.asyncio
async def test_policy_execution_flow(engine):
    # Mock connector registry and instance
    with patch("dashboard.policy_engine.get_connector_instance") as mock_get_instance, \
         patch("dashboard.policy_engine.registry") as mock_registry, \
         patch("dashboard.policy_engine.resolve_connector_config") as mock_resolve:
        
        mock_get_instance.return_value = {
            "id": "conn-123",
            "connector_id": "notion",
            "config": {"token": "secret"}
        }
        
        mock_connector = MagicMock()
        mock_connector.list_documents = AsyncMock(return_value={"items": [{"id": "doc1", "content": "hello"}]})
        
        mock_connector_class = MagicMock(return_value=mock_connector)
        mock_registry.get_connector.return_value = mock_connector_class
        mock_resolve.return_value = {"token": "secret"}
        
        policy = Policy(
            name="Test Policy",
            trigger=Trigger(type="manual"),
            pipeline=[
                PipelineAction(action="fetch", connector_instance_id="conn-123"),
                PipelineAction(action="filter", params={"max_items": 1}),
                PipelineAction(action="notify", params={"template": "Got {count} items"})
            ]
        )
        
        engine.add_policy(policy)
        result = await engine.execute(policy.policy_id)
        
        assert result.status == "success"
        assert len(result.output["items"]) == 1
        assert result.output["items"][0]["content"] == "hello"

@pytest.mark.asyncio
async def test_scheduler_cron(scheduler):
    with patch("dashboard.scheduler.croniter") as mock_croniter:
        mock_it = MagicMock()
        mock_it.get_next.return_value = datetime.now()
        mock_croniter.return_value = mock_it
        
        job_id = scheduler.add_job(
            name="Cron Job",
            task_type="policy",
            task_params={"policy_id": "pol-123"},
            cron="*/1 * * * *"
        )
        
        assert job_id in scheduler.jobs
        assert scheduler.jobs[job_id].cron == "*/1 * * * *"
        scheduler.remove_job(job_id)

@pytest.mark.asyncio
async def test_role_activation_trigger(engine):
    policy = Policy(
        name="Role Policy",
        trigger=Trigger(type="role_activation", role_id="researcher"),
        pipeline=[
            PipelineAction(action="broadcast", params={"event_type": "role_hit"})
        ]
    )
    engine.add_policy(policy)
    
    with patch("dashboard.policy_engine.PolicyEngine.execute", new_callable=AsyncMock) as mock_execute:
        await engine.trigger_by_role("researcher")
        # Since it's in background task, we might need a small sleep
        await asyncio.sleep(0.1)
        mock_execute.assert_called()
