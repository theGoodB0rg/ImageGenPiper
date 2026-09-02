import base64
import json
import os
import shutil
import tempfile
import pytest
from core.downloader import DownloadManager, sanitize_slug


@pytest.fixture
def temp_output_dir():
    dir_path = tempfile.mkdtemp(prefix="igp_test_downloads_")
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


def test_sanitize_slug():
    slug = sanitize_slug("A futuristic cyberpunk city (8k render) --ar 16:9")
    assert slug == "a-futuristic-cyberpunk-city-8k-render-ar-16-9"
    assert len(sanitize_slug("a" * 100, max_length=20)) == 20


@pytest.mark.asyncio
async def test_download_manager_save_image(temp_output_dir):
    manager = DownloadManager(output_dir=temp_output_dir)
    
    # 1x1 transparent PNG base64
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    saved_path, is_duplicate = await manager.save_image(
        job_id="test-job-123",
        prompt="A single pixel graphic",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png,
        metadata={"width": 1, "height": 1}
    )

    assert os.path.exists(saved_path)
    assert not is_duplicate
    assert saved_path.endswith(".png")

    # Verify sidecar metadata JSON file was written
    meta_path = f"{os.path.splitext(saved_path)[0]}.json"
    assert os.path.exists(meta_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        assert meta["job_id"] == "test-job-123"
        assert meta["prompt"] == "A single pixel graphic"
        assert meta["sha256"] is not None


@pytest.mark.asyncio
async def test_download_manager_deduplication(temp_output_dir):
    manager = DownloadManager(output_dir=temp_output_dir)
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    saved_path1, is_duplicate1 = await manager.save_image(
        job_id="job-1",
        prompt="Duplicate test",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png
    )
    assert not is_duplicate1

    # Second save with exact same image content
    saved_path2, is_duplicate2 = await manager.save_image(
        job_id="job-2",
        prompt="Duplicate test 2",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png
    )
    assert is_duplicate2
    assert saved_path2 == saved_path1
