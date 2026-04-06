import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from dashboard.policy_models import Policy, Trigger, PipelineAction, PolicyExecutionResult
from dashboard.notify import send_message as send_telegram_message
from dashboard.global_state import broadcaster
from dashboard.connector_utils import registry, get_connector_instance, resolve_connector_config

logger = logging.getLogger(__name__)

POLICIES_FILE = Path.home() / ".ostwin" / "dashboard" / "policies.json"
HISTORY_FILE = Path.home() / ".ostwin" / "dashboard" / "policy_history.json"

class PolicyEngine:
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.history: List[PolicyExecutionResult] = []
        self._load_policies()
        self._load_history()

    def _load_policies(self):
        # ... existing ...
        if POLICIES_FILE.exists():
            try:
                data = json.loads(POLICIES_FILE.read_text())
                for policy_data in data:
                    # Handle ISO format dates if they are strings
                    if isinstance(policy_data.get('created_at'), str):
                        policy_data['created_at'] = datetime.fromisoformat(policy_data['created_at'])
                    if isinstance(policy_data.get('last_run_at'), str):
                        policy_data['last_run_at'] = datetime.fromisoformat(policy_data['last_run_at'])
                    policy = Policy(**policy_data)
                    self.policies[policy.policy_id] = policy
            except Exception as e:
                logger.error(f"Failed to load policies: {e}")

    def _save_policies(self):
        POLICIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [policy.model_dump(mode='json') for policy in self.policies.values()]
            POLICIES_FILE.write_text(json.dumps(data, indent=4))
        except Exception as e:
            logger.error(f"Failed to save policies: {e}")

    def _load_history(self):
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text())
                self.history = [PolicyExecutionResult(**d) for d in data]
            except Exception as e:
                logger.error(f"Failed to load policy history: {e}")

    def _save_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Keep only last 100 entries for now
            data = [h.model_dump(mode='json') for h in self.history[-100:]]
            HISTORY_FILE.write_text(json.dumps(data, indent=4))
        except Exception as e:
            logger.error(f"Failed to save policy history: {e}")

    def get_history(self, policy_id: Optional[str] = None) -> List[PolicyExecutionResult]:
        if policy_id:
            return [h for h in self.history if h.policy_id == policy_id]
        return self.history

    def add_policy(self, policy: Policy) -> str:
        self.policies[policy.policy_id] = policy
        self._save_policies()
        return policy.policy_id

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self.policies.get(policy_id)

    def list_policies(self) -> List[Policy]:
        return list(self.policies.values())

    def delete_policy(self, policy_id: str):
        if policy_id in self.policies:
            del self.policies[policy_id]
            self._save_policies()

    async def execute(self, policy_id: str, trigger_context: Optional[Dict[str, Any]] = None) -> PolicyExecutionResult:
        policy = self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        if not policy.enabled:
            logger.info(f"Policy {policy_id} is disabled, skipping execution")
            return PolicyExecutionResult(
                policy_id=policy_id,
                status="skipped",
                started_at=datetime.now(),
                finished_at=datetime.now(),
                output="Policy disabled"
            )

        started_at = datetime.now()
        logger.info(f"Executing policy: {policy.name} ({policy_id})")
        
        current_data = trigger_context or {}
        
        try:
            for action in policy.pipeline:
                current_data = await self._run_action(action, current_data)
            
            policy.last_run_at = datetime.now()
            self._save_policies()
            
            result = PolicyExecutionResult(
                policy_id=policy_id,
                status="success",
                output=current_data,
                started_at=started_at,
                finished_at=datetime.now()
            )
            self.history.append(result)
            self._save_history()
            return result
        except Exception as e:
            logger.exception(f"Error executing policy {policy_id}")
            result = PolicyExecutionResult(
                policy_id=policy_id,
                status="failure",
                error=str(e),
                started_at=started_at,
                finished_at=datetime.now()
            )
            self.history.append(result)
            self._save_history()
            return result

    async def _run_action(self, action: PipelineAction, data: Any) -> Any:
        logger.info(f"Running action: {action.action}")
        
        if action.action == "fetch":
            return await self._action_fetch(action, data)
        elif action.action == "filter":
            return await self._action_filter(action, data)
        elif action.action == "transform":
            return await self._action_transform(action, data)
        elif action.action == "store":
            return await self._action_store(action, data)
        elif action.action == "notify":
            return await self._action_notify(action, data)
        elif action.action == "forward":
            return await self._action_forward(action, data)
        elif action.action == "broadcast":
            return await self._action_broadcast(action, data)
        else:
            raise ValueError(f"Unknown action: {action.action}")

    async def _action_fetch(self, action: PipelineAction, data: Any) -> Any:
        instance_id = action.connector_instance_id
        if not instance_id:
            raise ValueError("fetch action requires connector_instance_id")
        
        instance = get_connector_instance(instance_id)
        if not instance:
            raise ValueError(f"Connector instance {instance_id} not found")
        
        if not registry:
            raise ValueError("Connector registry not available")
        
        connector_id = instance["connector_id"]
        connector_class = registry.get_connector(connector_id)
        if not connector_class:
            raise ValueError(f"Connector {connector_id} not found in registry")
        
        # Instantiate and resolve config
        resolved_config = await resolve_connector_config(instance["config"])
        connector = connector_class()
        
        cursor = action.params.get("cursor") or data.get("cursor")
        
        # Call list_documents (or list_items if that's the generic name)
        # Based on routes/connectors.py, it seems it should be list_documents
        result = await connector.list_documents(resolved_config, cursor=cursor)
        
        # Convert Pydantic models to dicts if needed
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result

    async def _action_filter(self, action: PipelineAction, data: Any) -> Any:
        params = action.params
        if not isinstance(data, dict) or "items" not in data:
            logger.warning("filter action expects a dict with 'items' key")
            return data
        
        items = data["items"]
        content_type = params.get("content_type")
        max_items = params.get("max_items")
        
        filtered_items = items
        if content_type:
            filtered_items = [i for i in filtered_items if i.get("content_type") == content_type]
        
        if max_items:
            filtered_items = filtered_items[:max_items]
            
        return {**data, "items": filtered_items}

    async def _action_transform(self, action: PipelineAction, data: Any) -> Any:
        skill_ref = action.skill_ref
        if not skill_ref:
            return data
        
        # Mock skill transformation for now
        # In a real scenario, this would call a skill agent or a skill function
        logger.info(f"Transforming data using skill: {skill_ref}")
        if isinstance(data, dict) and "items" in data:
            for item in data["items"]:
                if "content" in item:
                    item["content"] = f"[{skill_ref}] {item['content']}"
        return data

    async def _action_store(self, action: PipelineAction, data: Any) -> Any:
        # Mock storage
        format = action.params.get("format", "jsonl")
        logger.info(f"Storing data in format: {format}")
        # In real scenario, write to a file or database
        return data

    async def _action_notify(self, action: PipelineAction, data: Any) -> Any:
        template = action.params.get("template", "New data: {count} items")
        count = 0
        if isinstance(data, dict) and "items" in data:
            count = len(data["items"])
        elif isinstance(data, list):
            count = len(data)
            
        message = template.format(count=count)
        
        channel = action.channel or "telegram"
        if channel == "telegram":
            await send_telegram_message(message)
        else:
            logger.warning(f"Unsupported notification channel: {channel}")
            
        return data

    async def _action_forward(self, action: PipelineAction, data: Any) -> Any:
        target_role = action.target_role
        if not target_role:
            raise ValueError("forward action requires target_role")
        
        logger.info(f"Forwarding to role: {target_role}")
        # This will be integrated with role_activation in TASK-006
        return data

    async def trigger_by_role(self, role_id: str, context: Optional[Dict[str, Any]] = None):
        logger.info(f"Triggering policies for role: {role_id}")
        for policy in self.list_policies():
            if policy.enabled and policy.trigger.type == "role_activation" and policy.trigger.role_id == role_id:
                # Run in background to not block the caller
                asyncio.create_task(self.execute(policy.policy_id, trigger_context=context))

    async def _action_broadcast(self, action: PipelineAction, data: Any) -> Any:
        event_type = action.params.get("event_type", "policy_run")
        await broadcaster.broadcast(event_type, {"data": data})
        return data

# Singleton instance
engine = PolicyEngine()
