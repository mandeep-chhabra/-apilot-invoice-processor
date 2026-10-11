"""
Audit Service

Records audit events for processing trail.
"""
from datetime import datetime
from typing import List

from apilot.models import AuditEvent, InvoiceRun


class AuditService:
    """Records and retrieves audit events."""

    @staticmethod
    def create_event(
        run_id: str,
        stage: str,
        status: str = "info",
        explanation: str = ""
    ) -> AuditEvent:
        """Create a new audit event."""
        return AuditEvent(
            run_id=run_id,
            stage=stage,
            status=status,
            timestamp=datetime.now(),
            explanation=explanation
        )

    @staticmethod
    def add_events(run: InvoiceRun, events: List[AuditEvent]) -> None:
        """Add events to an invoice run."""
        run.audit_events.extend(events)

    @staticmethod
    def get_timeline(run: InvoiceRun) -> List[dict]:
        """Get formatted timeline for UI."""
        timeline = []
        for event in run.audit_events:
            timeline.append({
                "stage": event.stage,
                "status": event.status,
                "timestamp": event.timestamp.strftime("%H:%M:%S"),
                "explanation": event.explanation
            })
        return timeline


def create_audit_event(
    run_id: str,
    stage: str,
    status: str = "info",
    explanation: str = ""
) -> AuditEvent:
    """Convenience function to create audit event."""
    return AuditService.create_event(run_id, stage, status, explanation)