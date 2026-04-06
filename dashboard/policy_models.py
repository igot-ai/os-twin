from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class Trigger(BaseModel):
    type: str # role_activation | schedule | manual | webhook
    role_id: Optional[str] = None
    cron: Optional[str] = None
    connector_instance_id: Optional[str] = None

class PipelineAction(BaseModel):
    action: str # fetch | filter | transform | store | notify | forward | broadcast
    connector_instance_id: Optional[str] = None
    skill_ref: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    # Extra fields for specific actions if needed
    channel: Optional[str] = None
    target_role: Optional[str] = None

class Policy(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    trigger: Trigger
    pipeline: List[PipelineAction]
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_run_at: Optional[datetime] = None

class PolicyExecutionResult(BaseModel):
    policy_id: str
    status: str # success | failure
    output: Any = None
    error: Optional[str] = None
    started_at: datetime
    finished_at: datetime
