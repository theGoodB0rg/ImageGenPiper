"""Central orchestration engine linking Job Queue, Rate Limiter, Downloader, and WebSocket Bridge."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.downloader import DownloadManager
from core.job_queue import Job, JobQueue, JobStatus
from core.protocol import (
    AnyMessage,
    ErrorCode,
    GenerateRequest,
    GenerationError,
    GenerationStatus,
    ImageFound,
    StatusUpdate,
)
from core.rate_limiter import TokenBucketRateLimiter
from core.ws_server import WebSocketBridgeServer

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str, Optional[str]], None]


class Orchestrator:
    """Coordinates batch generation jobs across the WebSocket bridge."""

    def __init__(
        self,
        ws_host: str = "127.0.0.1",
        ws_port: int = 8765,
        output_dir: str = "./outputs",
        rate_limit_rpm: float = 6.0,
        burst_capacity: float = 2.0,
        jitter_range: Tuple[float, float] = (1.0, 3.0),
        concurrency: int = 1,
        max_retries: int = 3,
        timeout_ms: int = 120000,
        reset_chat_between_prompts: bool = True,
    ):
        self.ws_server = WebSocketBridgeServer(host=ws_host, port=ws_port)
        self.job_queue = JobQueue(max_retries=max_retries)
        self.rate_limiter = TokenBucketRateLimiter(
            rate_limit_rpm=rate_limit_rpm,
            burst_capacity=burst_capacity,
            jitter_range=jitter_range,
        )
        self.downloader = DownloadManager(output_dir=output_dir)
        self.concurrency = max(1, concurrency)
        self.timeout_ms = timeout_ms
        self.reset_chat_between_prompts = reset_chat_between_prompts

        self._active_futures: Dict[str, asyncio.Future] = {}
        self._status_callbacks: List[StatusCallback] = []
        self._is_running = False
        self._worker_tasks: List[asyncio.Task] = []

        self.ws_server.register_handler(self._on_ws_message)

    def on_status_update(self, callback: StatusCallback) -> None:
        """Register a callback for status updates: (job_id, status_name, message)."""
        self._status_callbacks.append(callback)

    def _notify_status(self, job_id: str, status: str, message: Optional[str] = None) -> None:
        for cb in self._status_callbacks:
            try:
                cb(job_id, status, message)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    async def start(self) -> None:
        """Start the orchestrator and WebSocket server."""
        if not self._is_running:
            await self.ws_server.start()
            self._is_running = True

    async def stop(self) -> None:
        """Stop workers and WebSocket server."""
        self._is_running = False
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
        await self.ws_server.stop()

    async def add_job(self, job: Job) -> None:
        """Enqueue a prompt job."""
        await self.job_queue.enqueue(job)

    async def run_batch(
        self,
        batch_id: str = "batch",
        timeout: Optional[float] = None,
        total_elapsed_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run the batch until all enqueued jobs are completed or permanently failed,
        and generate a single consolidated metadata.json manifest.
        """
        if not self._is_running:
            await self.start()

        # Wait for at least one extension client to connect
        while self.ws_server.connected_clients_count == 0:
            self._notify_status("system", "WAITING_FOR_EXTENSION", "Waiting for Chrome extension to connect...")
            await asyncio.sleep(0.5)

        workers = [
            asyncio.create_task(self._worker_loop(worker_idx))
            for worker_idx in range(self.concurrency)
        ]
        self._worker_tasks = workers

        try:
            if timeout:
                await asyncio.wait_for(self._wait_for_completion(), timeout=timeout)
            else:
                await self._wait_for_completion()
        finally:
            for w in workers:
                w.cancel()
            self._worker_tasks.clear()

        # Write unified batch manifest
        manifest_path = await self.downloader.write_batch_manifest(
            batch_id=batch_id,
            total_elapsed_s=total_elapsed_s,
            total_prompts=self.job_queue.total_count,
        )

        return {
            "completed": list(self.job_queue._completed.values()),
            "failed": list(self.job_queue._failed.values()),
            "manifest_path": manifest_path,
        }

    async def _wait_for_completion(self) -> None:
        """Poll until queue is fully drained and no running jobs remain."""
        while True:
            if self.job_queue.pending_count == 0 and self.job_queue.running_count == 0:
                break
            await asyncio.sleep(0.2)

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker task processing jobs from the queue."""
        while self._is_running:
            try:
                if self.job_queue.pending_count == 0 and self.job_queue.running_count == 0:
                    await asyncio.sleep(0.2)
                    continue

                job = await self.job_queue.dequeue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} dequeue error: {e}")
                await asyncio.sleep(0.5)
                continue

            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            self._active_futures[job.id] = fut

            try:
                # 1. Rate limiter check & jitter
                self._notify_status(job.id, "RATE_LIMIT_WAIT", "Applying rate limit and human jitter...")
                await self.rate_limiter.acquire()

                # 2. Dispatch GenerateRequest
                req = GenerateRequest(
                    id=job.id,
                    prompt=job.prompt,
                    sequence_index=job.sequence_index,
                    title=job.title,
                    reset_chat=self.reset_chat_between_prompts,
                    timeout_ms=job.timeout_ms or self.timeout_ms,
                    options=job.options,
                )

                self._notify_status(job.id, "DISPATCHING", f"Sending prompt #{job.sequence_index or 1} to Chrome...")
                sent = await self.ws_server.broadcast(req)
                if sent == 0:
                    raise RuntimeError("No connected extension clients available to process request.")

                # 3. Await completion future
                timeout_s = (job.timeout_ms or self.timeout_ms) / 1000.0 + 10.0
                await asyncio.wait_for(fut, timeout=timeout_s)

                # 4. Mark completed
                await self.job_queue.mark_completed(job)
                self._notify_status(job.id, "COMPLETED", f"Saved {len(job.result_paths)} image(s).")

            except asyncio.TimeoutError:
                err_msg = "Job timed out waiting for response from extension."
                self._notify_status(job.id, "ERROR", err_msg)
                re_enqueued = await self.job_queue.mark_failed(job, err_msg, retryable=True)
                if re_enqueued:
                    self._notify_status(job.id, "RETRYING", f"Retrying ({job.retry_count}/{job.max_retries})...")

            except Exception as e:
                err_msg = str(e)
                self._notify_status(job.id, "ERROR", err_msg)
                re_enqueued = await self.job_queue.mark_failed(job, err_msg, retryable=True)
                if re_enqueued:
                    self._notify_status(job.id, "RETRYING", f"Retrying ({job.retry_count}/{job.max_retries})...")

            finally:
                self._active_futures.pop(job.id, None)

    async def _on_ws_message(self, client_id: str, msg: AnyMessage) -> None:
        """Handle incoming WebSocket messages from the extension."""
        if isinstance(msg, StatusUpdate):
            self._notify_status(msg.id, msg.status.value, msg.message)

        elif isinstance(msg, ImageFound):
            job = self.job_queue.get_job(msg.id)
            prompt_text = job.prompt if job else "generated"
            seq_idx = job.sequence_index if job else None
            title_text = job.title if job else None

            # Save image to disk asynchronously with ordered naming
            saved_path, is_duplicate = await self.downloader.save_image(
                job_id=msg.id,
                prompt=prompt_text,
                image_index=msg.image_index,
                mime_type=msg.mime_type,
                data_base64=msg.data_base64,
                sequence_index=seq_idx,
                title=title_text,
                metadata=msg.metadata,
            )

            if job:
                job.result_paths.append(saved_path)

            self._notify_status(
                msg.id,
                "IMAGE_SAVED",
                f"Image #{msg.image_index} saved -> {saved_path}" + (" (duplicate)" if is_duplicate else "")
            )

            # Resolve future if it exists
            fut = self._active_futures.get(msg.id)
            if fut and not fut.done():
                fut.set_result(saved_path)

        elif isinstance(msg, GenerationError):
            err_msg = f"[{msg.error_code.value}] {msg.message}"
            self._notify_status(msg.id, "ERROR", err_msg)

            job = self.job_queue.get_job(msg.id)
            if job:
                await self.job_queue.mark_failed(job, err_msg, retryable=msg.retryable)

            fut = self._active_futures.get(msg.id)
            if fut and not fut.done():
                fut.set_exception(RuntimeError(err_msg))
