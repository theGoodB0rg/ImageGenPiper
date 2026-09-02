import asyncio
import pytest
from core.job_queue import Job, JobQueue, JobStatus


@pytest.mark.asyncio
async def test_job_queue_enqueue_and_dequeue():
    queue = JobQueue(max_retries=2)
    job1 = Job(id="job-1", prompt="Prompt 1", priority=1)
    job2 = Job(id="job-2", prompt="Prompt 2", priority=10)  # Higher priority

    await queue.enqueue(job1)
    await queue.enqueue(job2)

    assert queue.total_count == 2
    assert queue.pending_count == 2

    # High priority dequeued first
    dequeued1 = await queue.dequeue()
    assert dequeued1.id == "job-2"
    assert dequeued1.status == JobStatus.RUNNING

    dequeued2 = await queue.dequeue()
    assert dequeued2.id == "job-1"


@pytest.mark.asyncio
async def test_job_retry_exponential_backoff():
    queue = JobQueue(max_retries=2, base_backoff_s=0.01)
    job = Job(id="job-retry", prompt="Test retry")

    await queue.enqueue(job)
    item = await queue.dequeue()

    # First failure -> should be re-enqueued
    should_retry = await queue.mark_failed(item, "Temporary network glitch", retryable=True)
    assert should_retry is True
    assert item.retry_count == 1
    assert queue.pending_count == 1

    # Second failure -> should be re-enqueued
    item2 = await queue.dequeue()
    should_retry_2 = await queue.mark_failed(item2, "Timeout", retryable=True)
    assert should_retry_2 is True
    assert item2.retry_count == 2

    # Third failure -> exceeds max_retries
    item3 = await queue.dequeue()
    should_retry_3 = await queue.mark_failed(item3, "Persistent error", retryable=True)
    assert should_retry_3 is False
    assert item3.status == JobStatus.FAILED
    assert queue.failed_count == 1


@pytest.mark.asyncio
async def test_job_non_retryable_failure():
    queue = JobQueue(max_retries=3)
    job = Job(id="job-safety", prompt="Unsafe prompt")
    await queue.enqueue(job)

    item = await queue.dequeue()
    should_retry = await queue.mark_failed(item, "Safety blocked", retryable=False)
    assert should_retry is False
    assert item.status == JobStatus.FAILED
    assert queue.failed_count == 1


@pytest.mark.asyncio
async def test_job_mark_completed():
    queue = JobQueue()
    job = Job(id="job-comp", prompt="Complete me")
    await queue.enqueue(job)

    item = await queue.dequeue()
    await queue.mark_completed(item, result_paths=["output/img.png"])

    assert item.status == JobStatus.COMPLETED
    assert queue.completed_count == 1
    assert queue.pending_count == 0
