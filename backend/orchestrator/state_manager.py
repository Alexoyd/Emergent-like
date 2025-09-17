import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from enum import Enum

logger = logging.getLogger(__name__)

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class StateManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def create_run(self, run_data: Dict[str, Any]) -> str:
        """Create a new run record"""
        try:
            run_data["created_at"] = datetime.now(timezone.utc)
            run_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await self.db.runs.insert_one(run_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating run: {e}")
            raise
    
    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID"""
        try:
            return await self.db.runs.find_one({"id": run_id})
        except Exception as e:
            logger.error(f"Error getting run {run_id}: {e}")
            return None
    
    async def update_run_status(self, run_id: str, status: RunStatus) -> bool:
        """Update run status"""
        try:
            result = await self.db.runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating run status: {e}")
            return False
    
    async def update_current_step(self, run_id: str, step_number: int) -> bool:
        """Update current step number"""
        try:
            result = await self.db.runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        "current_step": step_number,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating current step: {e}")
            return False
    
    async def add_cost(self, run_id: str, cost_eur: float) -> bool:
        """Add cost to run total"""
        try:
            result = await self.db.runs.update_one(
                {"id": run_id},
                {
                    "$inc": {"cost_used_eur": cost_eur},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error adding cost: {e}")
            return False
    
    async def add_log(self, run_id: str, log_entry: Dict[str, Any]) -> bool:
        """Add log entry to run"""
        try:
            log_entry["timestamp"] = datetime.now(timezone.utc)
            
            result = await self.db.runs.update_one(
                {"id": run_id},
                {
                    "$push": {"logs": log_entry},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error adding log: {e}")
            return False
    
    async def create_step(self, step_data: Dict[str, Any]) -> str:
        """Create a new step record"""
        try:
            step_data["created_at"] = datetime.now(timezone.utc)
            step_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await self.db.steps.insert_one(step_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating step: {e}")
            raise
    
    async def update_step_status(self, step_id: str, status: StepStatus) -> bool:
        """Update step status"""
        try:
            result = await self.db.steps.update_one(
                {"id": step_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating step status: {e}")
            return False
    
    async def update_step_result(self, step_id: str, result_data: Dict[str, Any]) -> bool:
        """Update step with execution results"""
        try:
            result_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await self.db.steps.update_one(
                {"id": step_id},
                {"$set": result_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating step result: {e}")
            return False
    
    async def get_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get step by ID"""
        try:
            return await self.db.steps.find_one({"id": step_id})
        except Exception as e:
            logger.error(f"Error getting step {step_id}: {e}")
            return None
    
    async def get_run_steps(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all steps for a run"""
        try:
            steps = await self.db.steps.find({"run_id": run_id}).sort("step_number", 1).to_list(length=None)
            return steps
        except Exception as e:
            logger.error(f"Error getting run steps: {e}")
            return []
    
    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running run"""
        try:
            # Update run status
            run_result = await self.db.runs.update_one(
                {"id": run_id, "status": {"$in": ["pending", "running"]}},
                {
                    "$set": {
                        "status": RunStatus.CANCELLED,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Cancel any pending/running steps
            step_result = await self.db.steps.update_many(
                {"run_id": run_id, "status": {"$in": ["pending", "running"]}},
                {
                    "$set": {
                        "status": StepStatus.FAILED,
                        "error": "Run cancelled",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            return run_result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error cancelling run: {e}")
            return False
    
    async def retry_step(self, run_id: str, step_number: int) -> bool:
        """Mark step for retry"""
        try:
            result = await self.db.steps.update_one(
                {"run_id": run_id, "step_number": step_number},
                {
                    "$set": {
                        "status": StepStatus.RETRYING,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$inc": {"retries": 1}
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error retrying step: {e}")
            return False
    
    async def get_daily_cost(self, date: Optional[datetime] = None) -> Dict[str, float]:
        """Get daily cost statistics"""
        try:
            if not date:
                date = datetime.now(timezone.utc)
            
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Aggregate daily costs
            pipeline = [
                {
                    "$match": {
                        "created_at": {
                            "$gte": start_of_day,
                            "$lte": end_of_day
                        }
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_cost": {"$sum": "$cost_used_eur"},
                        "run_count": {"$sum": 1},
                        "avg_cost": {"$avg": "$cost_used_eur"}
                    }
                }
            ]
            
            result = await self.db.runs.aggregate(pipeline).to_list(length=1)
            
            if result:
                return {
                    "total_cost": result[0].get("total_cost", 0.0),
                    "run_count": result[0].get("run_count", 0),
                    "avg_cost": result[0].get("avg_cost", 0.0)
                }
            else:
                return {"total_cost": 0.0, "run_count": 0, "avg_cost": 0.0}
                
        except Exception as e:
            logger.error(f"Error getting daily cost: {e}")
            return {"total_cost": 0.0, "run_count": 0, "avg_cost": 0.0}
    
    async def get_run_statistics(self) -> Dict[str, Any]:
        """Get overall run statistics"""
        try:
            # Get status counts
            status_pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            status_stats = await self.db.runs.aggregate(status_pipeline).to_list(length=None)
            
            # Get cost statistics
            cost_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_cost": {"$sum": "$cost_used_eur"},
                        "avg_cost": {"$avg": "$cost_used_eur"},
                        "max_cost": {"$max": "$cost_used_eur"},
                        "run_count": {"$sum": 1}
                    }
                }
            ]
            cost_stats = await self.db.runs.aggregate(cost_pipeline).to_list(length=1)
            
            # Get step statistics
            step_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_steps": {"$sum": 1},
                        "avg_retries": {"$avg": "$retries"},
                        "success_rate": {
                            "$avg": {
                                "$cond": [
                                    {"$eq": ["$status", "completed"]},
                                    1,
                                    0
                                ]
                            }
                        }
                    }
                }
            ]
            step_stats = await self.db.steps.aggregate(step_pipeline).to_list(length=1)
            
            return {
                "status_distribution": {stat["_id"]: stat["count"] for stat in status_stats},
                "cost_stats": cost_stats[0] if cost_stats else {},
                "step_stats": step_stats[0] if step_stats else {}
            }
            
        except Exception as e:
            logger.error(f"Error getting run statistics: {e}")
            return {}
    
    async def cleanup_old_runs(self, days_old: int = 30) -> int:
        """Clean up old completed runs"""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timezone.timedelta(days=days_old)
            
            # Delete old completed runs
            run_result = await self.db.runs.delete_many({
                "status": {"$in": ["completed", "failed", "cancelled"]},
                "created_at": {"$lt": cutoff_date}
            })
            
            # Delete associated steps
            step_result = await self.db.steps.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            logger.info(f"Cleaned up {run_result.deleted_count} old runs and {step_result.deleted_count} steps")
            return run_result.deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old runs: {e}")
            return 0