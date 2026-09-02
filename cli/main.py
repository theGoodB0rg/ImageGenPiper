"""Main Typer CLI entrypoint for ImageGenPiper."""

import asyncio
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
import typer
from rich.console import Console

from cli.config import Settings
from cli.ui import print_banner, print_summary, print_status_table
from core.job_queue import Job
from core.orchestrator import Orchestrator
from core.protocol import PingMessage, serialize_message
from core.ws_server import WebSocketBridgeServer

app = typer.Typer(
    name="imagegenpiper",
    help="Programmatic CLI for Gemini Web Image Generation via Browser Extension Bridge",
    add_completion=False,
)
console = Console(safe_box=True)


def parse_prompt_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse a prompt file supporting comment titles and sequential indexing.
    Example:
      # Image 1: The Attrition
      Detailed stickman... Scene: A harsh daytime death march...
    """
    items = []
    current_title = None
    sequence = 1

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line_clean = line.strip()
            if not line_clean:
                continue

            if line_clean.startswith("#"):
                comment_text = line_clean.lstrip("#").strip()
                title_match = re.search(r"(?:image\s*\d+\s*:\s*)?(.+)", comment_text, re.IGNORECASE)
                if title_match:
                    candidate = title_match.group(1).strip()
                    if not candidate.lower().startswith("style:") and not candidate.lower().startswith("the story:"):
                        current_title = candidate
                continue

            title = current_title
            if not title:
                scene_match = re.search(r"scene\s*:\s*([^.]+)", line_clean, re.IGNORECASE)
                if scene_match:
                    title = scene_match.group(1).strip()
                else:
                    title = f"Scene {sequence}"

            items.append({
                "sequence_index": sequence,
                "title": title,
                "prompt": line_clean,
            })
            sequence += 1
            current_title = None

    return items


@app.command()
def run(
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Single prompt to generate",
    ),
    prompts_file: Optional[str] = typer.Option(
        None,
        "--prompts-file",
        "-f",
        help="Path to file containing prompts (one per line)",
    ),
    output_dir: str = typer.Option(
        "./outputs",
        "--output-dir",
        "-o",
        help="Directory to save generated images",
    ),
    rate_limit: float = typer.Option(
        6.0,
        "--rate-limit",
        "-r",
        help="Max generation requests per minute (RPM)",
    ),
    concurrency: int = typer.Option(
        1,
        "--concurrency",
        "-c",
        help="Number of concurrent generation workers (default: 1)",
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        "-t",
        help="Timeout in seconds per prompt generation",
    ),
    new_chat_per_prompt: bool = typer.Option(
        False,
        "--new-chat-per-prompt",
        help="Reset to a new chat before each prompt (default: False, keeps persistent multi-turn thread)",
    ),
    port: int = typer.Option(
        8765,
        "--port",
        help="WebSocket bridge port",
    ),
):
    """Run batch image generation on Gemini via Chrome Extension bridge."""
    print_banner()

    if not prompt and not prompts_file:
        console.print("[bold red]Error:[/bold red] You must provide either --prompt or --prompts-file.")
        raise typer.Exit(code=1)

    prompt_items: List[Dict[str, Any]] = []

    if prompt:
        prompt_items.append({
            "sequence_index": 1,
            "title": "Single Generation",
            "prompt": prompt.strip(),
        })

    if prompts_file:
        if not os.path.exists(prompts_file):
            console.print(f"[bold red]Error:[/bold red] Prompts file not found: {prompts_file}")
            raise typer.Exit(code=1)
        prompt_items = parse_prompt_file(prompts_file)

    if not prompt_items:
        console.print("[bold red]Error:[/bold red] No valid prompts found to process.")
        raise typer.Exit(code=1)

    mode_desc = "Isolated Chats" if new_chat_per_prompt else "Single Multi-Turn Thread (Continuous Style & Memory)"
    console.print(f"[bold cyan]Enqueued {len(prompt_items)} prompt(s)[/bold cyan] in [bold green]{mode_desc}[/bold green] into: [bold yellow]{output_dir}[/bold yellow]\n")

    batch_name = os.path.splitext(os.path.basename(prompts_file))[0] if prompts_file else "single_prompt"

    asyncio.run(_execute_batch(
        batch_id=batch_name,
        prompt_items=prompt_items,
        output_dir=output_dir,
        rate_limit=rate_limit,
        concurrency=concurrency,
        timeout_s=timeout,
        new_chat_per_prompt=new_chat_per_prompt,
        port=port,
    ))


async def _execute_batch(
    batch_id: str,
    prompt_items: List[Dict[str, Any]],
    output_dir: str,
    rate_limit: float,
    concurrency: int,
    timeout_s: int,
    new_chat_per_prompt: bool,
    port: int,
):
    orchestrator = Orchestrator(
        ws_host="127.0.0.1",
        ws_port=port,
        output_dir=output_dir,
        rate_limit_rpm=rate_limit,
        concurrency=concurrency,
        timeout_ms=timeout_s * 1000,
        reset_chat_between_prompts=new_chat_per_prompt,
    )

    job_start_times = {}

    # Attach live status logger
    def on_status(job_id: str, status: str, message: Optional[str]):
        msg_str = f" - {message}" if message else ""
        color = "cyan"
        now = time.time()

        if status == "DISPATCHING":
            job_start_times[job_id] = now

        if status in ("IMAGE_SAVED", "COMPLETED"):
            color = "green"
            start_t = job_start_times.get(job_id)
            if start_t:
                elapsed = now - start_t
                msg_str += f" [dim](elapsed: {elapsed:.1f}s)[/dim]"
        elif status in ("ERROR", "FAILED"):
            color = "red"
        elif status == "WAITING_FOR_EXTENSION":
            color = "yellow"

        console.print(f"[{color}][{status}][/{color}] [dim]Job {job_id[:8]}:[/dim]{msg_str}")

    orchestrator.on_status_update(on_status)

    for item in prompt_items:
        job = Job(
            id=str(uuid.uuid4()),
            prompt=item["prompt"],
            sequence_index=item.get("sequence_index"),
            title=item.get("title"),
            timeout_ms=timeout_s * 1000,
        )
        await orchestrator.add_job(job)

    batch_start = time.time()
    try:
        await orchestrator.start()
        results = await orchestrator.run_batch(
            batch_id=batch_id,
            total_elapsed_s=0.0,
        )
        total_elapsed = time.time() - batch_start
        # Rewrite manifest with final exact elapsed time
        await orchestrator.downloader.write_batch_manifest(
            batch_id=batch_id,
            total_elapsed_s=total_elapsed,
            total_prompts=len(prompt_items),
        )
        print_summary(results["completed"], results["failed"], output_dir, total_elapsed_s=total_elapsed)
        console.print(f"[bold cyan]Unified Manifest generated:[/bold cyan] [underline]{results['manifest_path']}[/underline]\n")
    finally:
        await orchestrator.stop()


@app.command()
def test_bridge(
    port: int = typer.Option(
        8765,
        "--port",
        help="WebSocket port to listen on",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Seconds to wait for extension connection",
    ),
):
    """Test connection between local CLI and Chrome extension."""
    print_banner()
    console.print(f"[bold cyan]Starting WebSocket Bridge test on ws://127.0.0.1:{port}...[/bold cyan]")
    console.print("[dim]Make sure Chrome has the ImageGenPiper extension loaded and an active Gemini tab opened.[/dim]\n")

    asyncio.run(_run_bridge_test(port, timeout))


async def _run_bridge_test(port: int, timeout: int):
    server = WebSocketBridgeServer(host="127.0.0.1", port=port)
    await server.start()

    console.print("[*] Waiting for extension to connect...")
    connected = False
    for _ in range(timeout * 2):
        if server.connected_clients_count > 0:
            connected = True
            break
        await asyncio.sleep(0.5)

    if not connected:
        console.print("[bold red][FAIL] Bridge test timed out:[/bold red] No Chrome extension connected.")
        console.print("[yellow]Tips:[/yellow]\n1. Ensure extension is loaded in chrome://extensions/\n2. Verify gemini.google.com/app is open in Chrome.")
        await server.stop()
        raise typer.Exit(code=1)

    console.print(f"[bold green][OK] Chrome Extension connected successfully![/bold green] ({server.connected_clients_count} client(s) active)")
    await server.stop()


@app.command()
def version():
    """Display version information."""
    console.print("[bold cyan]ImageGenPiper[/bold cyan] version [bold green]0.1.0[/bold green]")


if __name__ == "__main__":
    app()
