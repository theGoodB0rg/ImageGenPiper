"""Asynchronous download manager and image persistence with SHA-256 deduplication."""

import base64
from datetime import datetime
import hashlib
import json
import os
import re
from typing import Any, Dict, Optional, Set, Tuple
import aiofiles


def sanitize_slug(prompt: str, max_length: int = 60) -> str:
    """Sanitize prompt into a filesystem-safe slug."""
    if not prompt:
        return "untitled"

    slug = prompt.lower()
    # Replace special punctuation with spaces
    slug = re.sub(r"[^\w\s-]", " ", slug)
    slug = slug.strip()
    # Replace consecutive spaces/underscores with hyphens
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug[:max_length] if slug else "untitled"


class DownloadManager:
    """Manages disk streaming of generated images, deduplication, and metadata sidecars."""

    def __init__(self, output_dir: str = "./outputs"):
        self.output_dir = os.path.abspath(output_dir)
        self._seen_hashes: Set[str] = set()
        self._hash_to_path: Dict[str, str] = {}

    async def save_image(
        self,
        job_id: str,
        prompt: str,
        image_index: int,
        mime_type: str,
        data_base64: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        """
        Decode Base64 image, check for duplicates via SHA-256, write to disk,
        and write companion .json metadata sidecar.

        :returns: (saved_file_path, is_duplicate)
        """
        image_bytes = base64.b64decode(data_base64)
        sha256_hash = hashlib.sha256(image_bytes).hexdigest()

        # Check deduplication
        if sha256_hash in self._seen_hashes:
            existing_path = self._hash_to_path.get(sha256_hash, "")
            return existing_path, True

        # Determine extension
        ext = "png"
        if "jpeg" in mime_type or "jpg" in mime_type:
            ext = "jpg"
        elif "webp" in mime_type:
            ext = "webp"

        # Organize by date
        date_str = datetime.now().strftime("%Y-%m-%d")
        dest_folder = os.path.join(self.output_dir, date_str)
        os.makedirs(dest_folder, exist_ok=True)

        slug = sanitize_slug(prompt, max_length=50)
        short_id = job_id.replace("-", "")[:8]
        filename = f"{slug}-{short_id}-{image_index}.{ext}"
        filepath = os.path.join(dest_folder, filename)

        # Handle filename collisions if different image shares slug and short id
        counter = 1
        while os.path.exists(filepath):
            filename = f"{slug}-{short_id}-{image_index}_{counter}.{ext}"
            filepath = os.path.join(dest_folder, filename)
            counter += 1

        # Write image bytes asynchronously
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(image_bytes)

        # Write companion metadata sidecar JSON
        meta_filepath = f"{os.path.splitext(filepath)[0]}.json"
        meta_payload = {
            "job_id": job_id,
            "prompt": prompt,
            "image_index": image_index,
            "mime_type": mime_type,
            "sha256": sha256_hash,
            "file_size_bytes": len(image_bytes),
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        async with aiofiles.open(meta_filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta_payload, indent=2))

        self._seen_hashes.add(sha256_hash)
        self._hash_to_path[sha256_hash] = filepath

        return filepath, False
