"""
Data models for the Autonomous Multi-Agent & Execution Engine.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import uuid
import time


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:6]}")
    title: str
    agent_type: str = Field(description="Agent type to execute the task: 'research', 'code', 'file', 'communication', 'browser', or 'general'")
    description: str
    dependencies: List[str] = Field(default_factory=list, description="IDs of tasks that must complete before this task starts")
    input_params: Dict[str, Any] = Field(default_factory=dict, description="Input parameters, supports variable references like '${task_1.output}'")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    output: Optional[Any] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    goal: str
    tasks: List[AgentTask]
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    final_output: Optional[str] = None
    summary: Optional[str] = None

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_ready_tasks(self) -> List[AgentTask]:
        """Return all tasks whose dependencies have been completed and are pending."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready = []
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                if all(dep_id in completed_ids for dep_id in task.dependencies):
                    ready.append(task)
        return ready

    def is_finished(self) -> bool:
        return all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED] for t in self.tasks)
