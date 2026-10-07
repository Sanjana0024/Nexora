from datetime import datetime, timezone
from uuid import uuid4


class WorkflowRun:

    def __init__(self, workflow_name: str):

        self.run_id = str(uuid4())

        self.workflow_name = workflow_name

        self.status = "RUNNING"

        self.started_at = datetime.now(timezone.utc)

        self.completed_at = None

        self.node_results = []

    def mark_success(self):

        self.status = "SUCCESS"

        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self):

        self.status = "FAILED"

        self.completed_at = datetime.now(timezone.utc)