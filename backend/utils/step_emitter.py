# backend/services/step_emitter.py

from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class StepEmitter:
    """
    Emits step-by-step reasoning events during enrichment.
    
    Frontend displays these as a live feed of what the
    system is doing — like Claude's thinking process.
    
    Each step has:
    - icon: emoji for visual scanning
    - message: what we're doing
    - detail: specific data found (URL, count, result)
    - status: running / done / failed
    """

    def __init__(self, lead_id: str, agent_name: str):
        self.lead_id    = lead_id
        self.agent_name = agent_name
        self.steps      = []

    def emit(
        self,
        message: str,
        detail: Optional[str] = None,
        icon: str = "🔍",
        status: str = "done",
    ) -> dict:
        """
        Emit a reasoning step.
        Stored in steps list + logged.
        Frontend polls for these.
        """
        step = {
            "agent":    self.agent_name,
            "icon":     icon,
            "message":  message,
            "detail":   detail,
            "status":   status,
            "lead_id":  self.lead_id,
        }
        self.steps.append(step)
        logger.info(f"[{self.agent_name}] {message} {detail or ''}")
        return step

    def get_steps(self) -> list:
        return self.steps