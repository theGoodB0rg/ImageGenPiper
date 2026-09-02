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

    # Scene extraction test
    slug2 = sanitize_slug("Detailed comic style. Scene: The Attrition and long march.")
    assert "the-attrition" in slug2


@pytest.mark.asyncio
async def test_download_manager_save_image_and_manifest(temp_output_dir):
    manager = DownloadManager(output_dir=temp_output_dir)
    
    # 1x1 transparent PNG base64
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    saved_path, is_duplicate = await manager.save_image(
        job_id="test-job-123",
        prompt="A single pixel graphic",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png,
        sequence_index=1,
        title="First Pixel",
        metadata={"width": 1, "height": 1}
    )

    assert os.path.exists(saved_path)
    assert not is_duplicate
    assert saved_path.endswith(".png")
    assert "01_first-pixel" in os.path.basename(saved_path)

    # Write unified manifest
    manifest_path = await manager.write_batch_manifest(
        batch_id="test_batch",
        total_elapsed_s=12.5,
        total_prompts=1
    )

    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["batch_id"] == "test_batch"
        assert manifest["total_images_saved"] == 1
        assert len(manifest["images"]) == 1
        assert manifest["images"][0]["index"] == 1
        assert manifest["images"][0]["title"] == "First Pixel"
        assert manifest["images"][0]["sha256"] is not None


@pytest.mark.asyncio
async def test_download_manager_deduplication(temp_output_dir):
    manager = DownloadManager(output_dir=temp_output_dir)
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    saved_path1, is_duplicate1 = await manager.save_image(
        job_id="job-1",
        prompt="Duplicate test",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png,
        sequence_index=1
    )
    assert not is_duplicate1

    # Second save with exact same image content
    saved_path2, is_duplicate2 = await manager.save_image(
        job_id="job-2",
        prompt="Duplicate test 2",
        image_index=1,
        mime_type="image/png",
        data_base64=b64_png,
        sequence_index=2
    )
    assert is_duplicate2
    assert saved_path2 == saved_path1
