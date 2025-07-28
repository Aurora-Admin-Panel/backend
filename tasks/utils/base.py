from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Callable, TYPE_CHECKING

from loguru import logger

from tasks.utils.exception import AuroraException

if TYPE_CHECKING:
    from .connection import AuroraConnection


class StateResult(Enum):
    SUCCESS = "success"
    CHANGED = "changed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class OperationResult:
    state: StateResult
    message: str = ""
    changed: bool = False
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.state in (
            StateResult.SUCCESS,
            StateResult.CHANGED,
            StateResult.SKIPPED,
        )

    @property
    def failed(self) -> bool:
        return self.state == StateResult.FAILED


@dataclass
class TaskResult:
    """Result of running multiple tasks"""

    success: bool
    changed: bool
    results: List[OperationResult] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        """Get summary of results"""
        summary = {
            "total": len(self.results),
            "success": 0,
            "changed": 0,
            "failed": 0,
            "skipped": 0,
        }

        for result in self.results:
            if result.state == StateResult.SUCCESS:
                summary["success"] += 1
            elif result.state == StateResult.CHANGED:
                summary["changed"] += 1
            elif result.state == StateResult.FAILED:
                summary["failed"] += 1
            elif result.state == StateResult.SKIPPED:
                summary["skipped"] += 1

        return summary


class SystemResource(ABC):
    def __init__(
        self, name: str, connection: "AuroraConnection", check_mode: bool = False
    ):
        self.name = name
        self.connection = connection
        self.check_mode = check_mode
        self._facts_cache = {}

    @abstractmethod
    def check_current_state(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def apply_changes(self) -> OperationResult:
        pass

    def ensure(self) -> OperationResult:
        try:
            current_state = self.check_current_state()

            if self.desired_state_matches(current_state):
                return OperationResult(
                    # TODO: Maybe SKIPPED?
                    state=StateResult.SKIPPED,
                    message=f"{self.__class__.__name__} '{self.name}' already in desired state",
                    changed=False,
                )

            if self.check_mode:
                return OperationResult(
                    state=StateResult.CHANGED,
                    message=f"{self.__class__.__name__} '{self.name}' would be in desired state",
                    changed=True,
                )
            return self.apply_changes()

        except AuroraException as e:
            logger.exception(
                f"AuroraException in {self.__class__.__name__} '{self.name}': {e}"
            )
            return OperationResult(
                state=StateResult.FAILED,
                message=f"AuroraException in {self.__class__.__name__} '{self.name}': {e}",
                stderr=str(e),
            )
        except Exception as e:
            logger.exception(f"Error ensuring {self.__class__.__name__} '{self.name}'")
            return OperationResult(
                state=StateResult.FAILED,
                message=f"Failed to ensure {self.__class__.__name__} '{self.name}'",
                stderr=str(e),
            )
