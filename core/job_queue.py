"""Asynchronous Job Queue with priority scheduling, backpressure, and exponential backoff retry."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import heapq
import time
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(order=True)
class PriorityItem:
    priority: int
    entry_time: float
    job: "Job" = field(compare=False)


@dataclass
class Job:
    id: str
    prompt: str
    sequence_index: Optional[int] = None
    title: Optional[str] = None
    priority: int = 0
    timeout_ms: int = 120000
    options: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    retry_count: int = 0
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    error_history: List[str] = field(default_factory=list)
    result_paths: List[str] = field(default_factory=list)


class JobQueue:
    """Thread-safe and async-compatible priority job queue."""

    def __init__(
        self,
        maxsize: int = 0,
        max_retries: int = 3,
        base_backoff_s: float = 2.0,
        max_backoff_s: float = 60.0,
    ):
        self.maxsize = maxsize
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s

        self._heap: List[PriorityItem] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        
        # Tracking dictionaries
        self._all_jobs: Dict[str, Job] = {}
        self._pending: Dict[str, Job] = {}
        self._running: Dict[str, Job] = {}
        self._completed: Dict[str, Job] = {}
        self._failed: Dict[str, Job] = {}

    @property
    def total_count(self) -> int:
        return len(self._all_jobs)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def failed_count(self) -> int:
        return len(self._failed)

    async def enqueue(self, job: Job) -> None:
        """Enqueue a new job with priority."""
        async with self._not_empty:
            self._all_jobs[job.id] = job
            self._pending[job.id] = job
            job.status = JobStatus.PENDING
            # Lower number = higher priority in heapq, so negate priority
            heapq.heappush(
                self._heap,
                PriorityItem(
                    priority=-job.priority,
                    entry_time=time.time(),
                    job=job,
                ),
            )
            self._not_empty.notify()

    async def dequeue(self) -> Job:
        """Dequeue highest priority job. Blocks until a job is available."""
        async with self._not_empty:
            while not self._heap:
                await self._not_empty.wait()

            item = heapq.heappop(self._heap)
            job = item.job
            self._pending.pop(job.id, None)
            self._running[job.id] = job
            job.status = JobStatus.RUNNING
            return job

    async def mark_completed(self, job: Job, result_paths: Optional[List[str]] = None) -> None:
        """Mark job as successfully completed."""
        async with self._lock:
            self._running.pop(job.id, None)
            self._completed[job.id] = job
            job.status = JobStatus.COMPLETED
            if result_paths:
                job.result_paths.extend(result_paths)

    async def mark_failed(
        self,
        job: Job,
        error_message: str,
        retryable: bool = True,
    ) -> bool:
        """
        Record a failure. If retryable and retry_count < max_retries, re-enqueues after backoff delay.
        Returns True if job was re-enqueued for retry, False if permanently failed.
        """
        job.error_history.append(error_message)

        async with self._not_empty:
            self._running.pop(job.id, None)

            if retryable and job.retry_count < self.max_retries:
                job.retry_count += 1
                job.status = JobStatus.PENDING
                self._pending[job.id] = job

                # Calculate exponential backoff
                delay = min(
                    self.base_backoff_s * (2 ** (job.retry_count - 1)),
                    self.max_backoff_s,
                )
                
                # Async background task to reinsert after backoff delay
                asyncio.create_task(self._delayed_reinsert(job, delay))
                return True
            else:
                job.status = JobStatus.FAILED
                self._failed[job.id] = job
                return False

    async def _delayed_reinsert(self, job: Job, delay_s: float) -> None:
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        async with self._not_empty:
            heapq.heappush(
                self._heap,
                PriorityItem(
                    priority=-job.priority,
                    entry_time=time.time(),
                    job=job,
                ),
            )
            self._not_empty.notify()

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._all_jobs.get(job_id)
