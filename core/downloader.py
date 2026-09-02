"""Asynchronous download manager, image persistence, and unified batch manifest generator."""

import asyncio
import base64
from datetime import datetime
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import aiofiles


def sanitize_slug(text: str, max_length: int = 50) -> str:
    """Sanitize text into a clean, filesystem-safe slug."""
    if not text:
        return "untitled"

    slug = text.lower()
    # If text contains "Scene:", extract the actual scene description
    scene_match = re.search(r"scene\s*:\s*([^.]+)", slug)
    if scene_match:
        slug = scene_match.group(1).strip()

    # Remove special punctuation
    slug = re.sub(r"[^\w\s-]", " ", slug)
    slug = slug.strip()
    # Replace whitespace with hyphens
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug[:max_length] if slug else "untitled"


class DownloadManager:
    """Manages disk streaming of generated images, deduplication, and unified batch manifest generation."""

    def __init__(self, output_dir: str = "./outputs"):
        self.output_dir = os.path.abspath(output_dir)
        self._seen_hashes: Set[str] = set()
        self._hash_to_path: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.saved_records: List[Dict[str, Any]] = []

    async def save_image(
        self,
        job_id: str,
        prompt: str,
        image_index: int,
        mime_type: str,
        data_base64: str,
        sequence_index: Optional[int] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        """
        Decode Base64 image, check for duplicates via SHA-256 atomically, write to disk
        with predictable ordered filenames ({index:02d}_{title_slug}_{short_id}.{ext}).

        :returns: (saved_file_path, is_duplicate)
        """
        image_bytes = base64.b64decode(data_base64)
        sha256_hash = hashlib.sha256(image_bytes).hexdigest()

        async with self._lock:
            # Check deduplication atomically
            if sha256_hash in self._seen_hashes:
                existing_path = self._hash_to_path.get(sha256_hash, "")
                return existing_path, True

            # Determine file extension
            ext = "png"
            if "jpeg" in mime_type or "jpg" in mime_type:
                ext = "jpg"
            elif "webp" in mime_type:
                ext = "webp"

            # Organize by date
            date_str = datetime.now().strftime("%Y-%m-%d")
            dest_folder = os.path.join(self.output_dir, date_str)
            os.makedirs(dest_folder, exist_ok=True)

            # Build clean title slug
            slug = sanitize_slug(title if title else prompt, max_length=40)
            short_id = job_id.replace("-", "")[:8]

            # Format with sequential order prefix
            if sequence_index is not None:
                prefix = f"{sequence_index:02d}"
                if image_index > 1:
                    filename = f"{prefix}_{slug}_{short_id}_{image_index}.{ext}"
                else:
                    filename = f"{prefix}_{slug}_{short_id}.{ext}"
            else:
                filename = f"{slug}_{short_id}_{image_index}.{ext}"

            filepath = os.path.join(dest_folder, filename)

            # Handle collisions if necessary
            counter = 1
            while os.path.exists(filepath):
                base_name, f_ext = os.path.splitext(filename)
                filepath = os.path.join(dest_folder, f"{base_name}_{counter}{f_ext}")
                counter += 1

            # Reserve hash immediately in seen set before async I/O
            self._seen_hashes.add(sha256_hash)
            self._hash_to_path[sha256_hash] = filepath

        # Write image bytes asynchronously
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(image_bytes)

        record = {
            "index": sequence_index or len(self.saved_records) + 1,
            "title": title or slug,
            "filename": os.path.basename(filepath),
            "path": filepath,
            "prompt": prompt,
            "job_id": job_id,
            "image_index": image_index,
            "mime_type": mime_type,
            "file_size_bytes": len(image_bytes),
            "sha256": sha256_hash,
            "dimensions": {
                "width": (metadata or {}).get("width"),
                "height": (metadata or {}).get("height"),
            },
            "timestamp": datetime.now().isoformat(),
        }

        async with self._lock:
            self.saved_records.append(record)

        return filepath, False

    async def write_batch_manifest(
        self,
        batch_id: str,
        total_elapsed_s: Optional[float] = None,
        total_prompts: Optional[int] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write a single consolidated metadata.json manifest for the batch."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        dest_folder = os.path.join(self.output_dir, date_str)
        os.makedirs(dest_folder, exist_ok=True)
        manifest_path = os.path.join(dest_folder, "metadata.json")

        async with self._lock:
            # Deduplicate records by sha256 in manifest
            unique_records = []
            seen_in_manifest = set()
            for r in self.saved_records:
                h = r.get("sha256")
                if h not in seen_in_manifest:
                    seen_in_manifest.add(h)
                    unique_records.append(r)

            # Sort saved records by sequential index
            sorted_records = sorted(unique_records, key=lambda r: r.get("index", 0))

        benchmark_data = {}
        if total_elapsed_s is not None and total_elapsed_s > 0:
            benchmark_data["total_elapsed_seconds"] = round(total_elapsed_s, 2)
            if sorted_records:
                benchmark_data["avg_seconds_per_image"] = round(total_elapsed_s / len(sorted_records), 2)
                benchmark_data["throughput_ipm"] = round((len(sorted_records) / total_elapsed_s) * 60.0, 2)

        manifest_payload = {
            "batch_id": batch_id,
            "generated_at": datetime.now().isoformat(),
            "total_prompts": total_prompts or len(sorted_records),
            "total_images_saved": len(sorted_records),
            "benchmark": benchmark_data,
            "custom_metadata": custom_metadata or {},
            "images": sorted_records,
        }

        async with aiofiles.open(manifest_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(manifest_payload, indent=2))

        return manifest_path
