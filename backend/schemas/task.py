"""Pydantic schemas for task related operations."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskMetadata(BaseModel):
    """Metadata for a registered task."""

    name: str = Field(description="Name of the task")
    doc: str = Field(description="Documentation string of the task")
    signature: str = Field(description="Signature of the task function")
    config_class: str = Field(description="Name of the configuration class")
    config_schema: Dict[str, Any] = Field(
        description="JSON schema of the configuration class"
    )


class TaskListResponse(BaseModel):
    """Response model for the list_tasks method."""

    tasks: Dict[str, TaskMetadata] = Field(
        description="Dictionary of tasks with task name as key and metadata as value"
    )

    @classmethod
    def from_dict(cls, tasks_dict: Dict[str, Dict[str, Any]]) -> "TaskListResponse":
        """
        Create a TaskListResponse from the dictionary returned by list_tasks.

        Args:
            tasks_dict: Dictionary returned by list_tasks method

        Returns:
            TaskListResponse: Properly structured response object
        """
        return cls(
            tasks={
                name: TaskMetadata(
                    name=info["name"],
                    doc=info["doc"],
                    signature=info["signature"],
                    config_class=info["config_class"],
                    config_schema=info["config_schema"],
                )
                for name, info in tasks_dict.items()
            }
        )
