"""Main Typer CLI entrypoint for ImageGenPiper."""

import asyncio
import os
import sys
import uuid
from typing import Optional
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

    prompts = []
    if prompt:
        prompts.append(prompt.strip())

    if prompts_file:
        if not os.path.exists(prompts_file):
            console.print(f"[bold red]Error:[/bold red] Prompts file not found: {prompts_file}")
            raise typer.Exit(code=1)
        with open(prompts_file, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = line.strip()
                if line_clean and not line_clean.startswith("#"):
                    prompts.append(line_clean)

    if not prompts:
        console.print("[bold red]Error:[/bold red] No valid prompts found to process.")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Enqueued {len(prompts)} prompt(s)[/bold cyan] to generate into: [bold yellow]{output_dir}[/bold yellow]\n")

    asyncio.run(_execute_batch(
        prompts=prompts,
        output_dir=output_dir,
        rate_limit=rate_limit,
        concurrency=concurrency,
        timeout_s=timeout,
        port=port,
    ))


async def _execute_batch(
    prompts: list[str],
    output_dir: str,
    rate_limit: float,
    concurrency: int,
    timeout_s: int,
    port: int,
):
    orchestrator = Orchestrator(
        ws_host="127.0.0.1",
        ws_port=port,
        output_dir=output_dir,
        rate_limit_rpm=rate_limit,
        concurrency=concurrency,
        timeout_ms=timeout_s * 1000,
    )

    # Attach live status logger
    def on_status(job_id: str, status: str, message: Optional[str]):
        msg_str = f" - {message}" if message else ""
        color = "cyan"
        if status in ("IMAGE_SAVED", "COMPLETED"):
            color = "green"
        elif status in ("ERROR", "FAILED"):
            color = "red"
        elif status == "WAITING_FOR_EXTENSION":
            color = "yellow"
        console.print(f"[{color}][{status}][/{color}] [dim]Job {job_id[:8]}:[/dim]{msg_str}")

    orchestrator.on_status_update(on_status)

    for p in prompts:
        job = Job(
            id=str(uuid.uuid4()),
            prompt=p,
            timeout_ms=timeout_s * 1000,
        )
        await orchestrator.add_job(job)

    try:
        await orchestrator.start()
        results = await orchestrator.run_batch()
        print_summary(results["completed"], results["failed"], output_dir)
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
