from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from dashboard.policy_models import Policy, Trigger, PipelineAction, PolicyExecutionResult
from dashboard.policy_engine import engine
from dashboard.auth import get_current_user
from dashboard.scheduler import scheduler

router = APIRouter(prefix="/api/policies", tags=["policies"])

@router.get("", response_model=List[Policy])
async def list_policies(user: dict = Depends(get_current_user)):
    return engine.list_policies()

@router.post("", response_model=Policy)
async def create_policy(policy_data: Dict[str, Any], user: dict = Depends(get_current_user)):
    try:
        policy = Policy(**policy_data)
        engine.add_policy(policy)
        
        # If the policy has a schedule trigger, add it to the scheduler
        if policy.trigger.type == "schedule":
            scheduler.add_job(
                name=f"Policy: {policy.name}",
                task_type="policy",
                task_params={"policy_id": policy.policy_id},
                interval_seconds=None, # Use cron if provided
                cron=policy.trigger.cron
            )
            
        return policy
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{policy_id}", response_model=Policy)
async def get_policy(policy_id: str, user: dict = Depends(get_current_user)):
    policy = engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy

@router.put("/{policy_id}", response_model=Policy)
async def update_policy(policy_id: str, policy_data: Dict[str, Any], user: dict = Depends(get_current_user)):
    existing = engine.get_policy(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    try:
        updated = Policy(**{**existing.model_dump(), **policy_data, "policy_id": policy_id})
        engine.add_policy(updated)
        
        # Update scheduler if needed
        # (For simplicity, we just remove and re-add or find by name/params)
        # In a real system, we'd have a mapping from policy to job_id
        
        return updated
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{policy_id}")
async def delete_policy(policy_id: str, user: dict = Depends(get_current_user)):
    engine.delete_policy(policy_id)
    return {"status": "deleted"}

@router.post("/{policy_id}/execute", response_model=PolicyExecutionResult)
async def execute_policy(policy_id: str, user: dict = Depends(get_current_user)):
    try:
        return await engine.execute(policy_id, trigger_context={"triggered_by": user.get("email")})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{policy_id}/history", response_model=List[PolicyExecutionResult])
async def get_policy_history(policy_id: str, user: dict = Depends(get_current_user)):
    return engine.get_history(policy_id)
