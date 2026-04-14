"""
Task Manager — tracks investigator promises and enforces execution.
Every time the investigator says it will do something, a task is created.
The heartbeat checks for stalled/forgotten tasks and triggers execution.
"""

import time
import threading


class Task:
    """A single investigator task."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETE = 'complete'
    FAILED = 'failed'
    STALLED = 'stalled'

    def __init__(self, task_id, action_type, entity, description, extra=None):
        self.id = task_id
        self.action_type = action_type  # expand, trace_money, trace_timeline, gap, report, scan
        self.entity = entity
        self.description = description  # human-readable: "Trace money for Tim Cook"
        self.extra = extra or {}
        self.status = self.PENDING
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.stall_notified = False  # only notify once

    def start(self):
        self.status = self.RUNNING
        self.started_at = time.time()

    def complete(self, result=None):
        self.status = self.COMPLETE
        self.completed_at = time.time()
        self.result = result

    def fail(self, error=None):
        self.status = self.FAILED
        self.completed_at = time.time()
        self.error = error

    def mark_stalled(self):
        self.status = self.STALLED

    @property
    def elapsed(self):
        if self.started_at:
            end = self.completed_at or time.time()
            return round(end - self.started_at, 1)
        return 0

    @property
    def age(self):
        return round(time.time() - self.created_at, 1)

    def to_dict(self):
        return {
            'id': self.id,
            'action_type': self.action_type,
            'entity': self.entity,
            'description': self.description,
            'status': self.status,
            'elapsed': self.elapsed,
            'age': self.age,
            'result': self.result,
            'error': self.error,
        }


class TaskManager:
    """Manages the investigator's task queue."""

    STALL_THRESHOLD = 10  # seconds — if model responded but task wasn't executed
    MAX_HISTORY = 50

    def __init__(self):
        self._tasks = {}  # id → Task
        self._counter = 0
        self._lock = threading.Lock()

    def create_task(self, action_type, entity, description, extra=None):
        """Create a new task. Returns the task."""
        with self._lock:
            self._counter += 1
            task_id = f"task_{self._counter}"
            task = Task(task_id, action_type, entity, description, extra)
            self._tasks[task_id] = task
            # Trim old completed tasks
            self._trim_history()
            return task

    def start_task(self, task_id):
        """Mark a task as running."""
        task = self._tasks.get(task_id)
        if task:
            task.start()

    def complete_task(self, task_id, result=None):
        """Mark a task as complete."""
        task = self._tasks.get(task_id)
        if task:
            task.complete(result)

    def fail_task(self, task_id, error=None):
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.fail(error)

    def get_current_task(self):
        """Get the currently running task, if any."""
        for task in reversed(list(self._tasks.values())):
            if task.status == Task.RUNNING:
                return task
        return None

    def get_pending_tasks(self):
        """Get all pending (promised but not started) tasks."""
        return [t for t in self._tasks.values() if t.status == Task.PENDING]

    def get_stalled_tasks(self):
        """Get tasks that were promised but never executed."""
        stalled = []
        for task in self._tasks.values():
            if task.status == Task.PENDING and task.age > self.STALL_THRESHOLD:
                task.mark_stalled()
                stalled.append(task)
            elif task.status == Task.RUNNING and task.elapsed > 300:
                # Running for over 5 minutes — probably hung
                task.mark_stalled()
                stalled.append(task)
        return stalled

    def get_unfinished(self):
        """Get all unfinished tasks (pending, running, stalled)."""
        return [t for t in self._tasks.values()
                if t.status in (Task.PENDING, Task.RUNNING, Task.STALLED)]

    def find_task_by_entity(self, entity_name):
        """Find the most recent unfinished task for an entity."""
        entity_lower = entity_name.lower()
        for task in reversed(list(self._tasks.values())):
            if task.entity.lower() == entity_lower and task.status in (Task.PENDING, Task.RUNNING, Task.STALLED):
                return task
        return None

    def get_forgotten_task(self):
        """Get the most important forgotten/stalled task that needs execution.
        This is what the heartbeat uses to remind the investigator."""
        stalled = self.get_stalled_tasks()
        if stalled:
            # Return highest priority stalled task (oldest first)
            return stalled[0]

        pending = self.get_pending_tasks()
        if pending:
            # Check if any pending tasks are old enough to be "forgotten"
            old_pending = [t for t in pending if t.age > self.STALL_THRESHOLD]
            if old_pending:
                return old_pending[0]

        return None

    def clear_pending(self):
        """Clear all pending tasks (used when user says no/skip/cancel)."""
        with self._lock:
            for task in list(self._tasks.values()):
                if task.status == Task.PENDING:
                    task.status = Task.FAILED
                    task.error = 'Cancelled by user'

    def get_status_summary(self):
        """Get a summary for the heartbeat display."""
        current = self.get_current_task()
        pending = self.get_pending_tasks()
        stalled = self.get_stalled_tasks()

        if current:
            return {
                'active': True,
                'task': current.to_dict(),
                'message': f"{current.description} ({current.elapsed}s)",
                'pending_count': len(pending),
                'stalled_count': len(stalled),
            }

        if stalled:
            t = stalled[0]
            return {
                'active': False,
                'stalled': True,
                'task': t.to_dict(),
                'message': f"Stalled: {t.description} — promised {t.age}s ago but never executed",
                'pending_count': len(pending),
                'stalled_count': len(stalled),
            }

        if pending:
            return {
                'active': False,
                'pending': True,
                'task': pending[0].to_dict(),
                'message': f"Queued: {pending[0].description}",
                'pending_count': len(pending),
                'stalled_count': 0,
            }

        return {
            'active': False,
            'message': 'Idle',
            'pending_count': 0,
            'stalled_count': 0,
        }

    def _trim_history(self):
        """Remove old completed/failed tasks to prevent memory growth."""
        completed = [t for t in self._tasks.values()
                     if t.status in (Task.COMPLETE, Task.FAILED) and t.age > 300]
        if len(completed) > self.MAX_HISTORY:
            for task in completed[:len(completed) - self.MAX_HISTORY]:
                del self._tasks[task.id]


# Global task manager instance
TASK_MGR = TaskManager()
