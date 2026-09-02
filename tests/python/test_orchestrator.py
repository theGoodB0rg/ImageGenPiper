import asyncio
import os
import shutil
import tempfile
import pytest
import websockets
from core.orchestrator import Orchestrator
from core.job_queue import Job, JobStatus
from core.protocol import (
    GenerateRequest,
    ImageFound,
    GenerationError,
    StatusUpdate,
    GenerationStatus,
    ErrorCode,
    parse_message,
    serialize_message,
)


@pytest.fixture
def temp_output_dir():
    d = tempfile.mkdtemp(prefix="igp_orch_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_orchestrator_single_job_success(temp_output_dir):
    orch = Orchestrator(
        ws_host="127.0.0.1",
        ws_port=8780,
        output_dir=temp_output_dir,
        rate_limit_rpm=600,
        jitter_range=(0.0, 0.0),
    )

    await orch.start()
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    async def mock_extension_client():
        async with websockets.connect("ws://127.0.0.1:8780") as ws:
            # Wait for GenerateRequest
            raw_msg = await ws.recv()
            msg = parse_message(raw_msg)
            assert isinstance(msg, GenerateRequest)

            # Send typing status
            await ws.send(serialize_message(StatusUpdate(
                id=msg.id,
                status=GenerationStatus.TYPING,
                message="Typing..."
            )))

            # Send ImageFound
            await ws.send(serialize_message(ImageFound(
                id=msg.id,
                image_index=1,
                mime_type="image/png",
                data_base64=b64_png,
                metadata={}
            )))

    client_task = asyncio.create_task(mock_extension_client())

    job = Job(id="job-orch-1", prompt="Orchestrator test prompt")
    await orch.add_job(job)

    # Process batch with 1 worker
    results = await orch.run_batch(timeout=5.0)

    await client_task
    await orch.stop()

    assert len(results["completed"]) == 1
    assert len(results["failed"]) == 0
    assert job.status == JobStatus.COMPLETED
    assert len(job.result_paths) == 1
    assert os.path.exists(job.result_paths[0])
