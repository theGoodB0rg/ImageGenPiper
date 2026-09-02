"""Terminal User Interface components using Rich for ImageGenPiper."""

from datetime import datetime
import time
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from core.job_queue import Job

console = Console(safe_box=True)


def print_banner():
    """Render the ImageGenPiper banner."""
    banner_text = Text()
    banner_text.append("ImageGenPiper\n", style="bold cyan")
    banner_text.append("Programmatic Gemini Web Image Generation CLI\n", style="italic white")
    banner_text.append("Zero Bot-Fingerprinting | MV3 WebSocket Bridge | Anti-Fragile DOM", style="dim green")
    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


def print_status_table(
    jobs: List[Job],
    pending_count: int,
    running_count: int,
    completed_count: int,
    failed_count: int,
    latest_event: str = "",
):
    """Render current progress status table."""
    table = Table(title=f"Batch Progress ({datetime.now().strftime('%H:%M:%S')})", border_style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Description", style="dim")

    table.add_row("[PENDING]", str(pending_count), "In queue waiting for execution", style="yellow")
    table.add_row("[RUNNING]", str(running_count), "Currently generating on Gemini", style="cyan")
    table.add_row("[COMPLETED]", str(completed_count), "Successfully extracted and saved", style="green")
    table.add_row("[FAILED]", str(failed_count), "Failed after max retries", style="red")

    console.print(table)
    if latest_event:
        console.print(f"[dim italic]Latest: {latest_event}[/dim italic]\n")


def print_summary(
    completed: List[Job],
    failed: List[Job],
    output_dir: str,
    total_elapsed_s: Optional[float] = None,
):
    """Render completion summary with timing and throughput benchmarks."""
    console.print("\n")
    if failed:
        title = f"[yellow]Batch Finished with {len(failed)} Failure(s)[/yellow]"
    else:
        title = f"[bold green]Batch Generation Completed Successfully![/bold green]"

    summary_table = Table(title="Execution & Benchmark Summary", border_style="green")
    summary_table.add_column("Metric", style="bold white")
    summary_table.add_column("Value", style="bold yellow")

    total_images = sum(len(j.result_paths) for j in completed)
    total_prompts = len(completed) + len(failed)

    summary_table.add_row("Total Prompts Processed", str(total_prompts))
    summary_table.add_row("Successful Prompts", str(len(completed)))
    summary_table.add_row("Failed Prompts", str(len(failed)))
    summary_table.add_row("Images Downloaded", str(total_images))
    summary_table.add_row("Output Directory", output_dir)

    if total_elapsed_s is not None and total_elapsed_s > 0:
        mins = int(total_elapsed_s // 60)
        secs = total_elapsed_s % 60
        time_str = f"{mins}m {secs:.1f}s" if mins > 0 else f"{secs:.1f}s"
        summary_table.add_row("Total Elapsed Time", time_str)

        if total_images > 0:
            avg_per_img = total_elapsed_s / total_images
            ipm = (total_images / total_elapsed_s) * 60.0
            summary_table.add_row("Avg Time Per Image", f"{avg_per_img:.1f}s")
            summary_table.add_row("Throughput (IPM)", f"{ipm:.2f} images/min")

    console.print(Panel(summary_table, title=title, border_style="green"))

    if failed:
        err_table = Table(title="Failed Prompts", border_style="red")
        err_table.add_column("ID", style="dim")
        err_table.add_column("Prompt", style="white")
        err_table.add_column("Last Error", style="red")

        for f in failed:
            last_err = f.error_history[-1] if f.error_history else "Unknown error"
            err_table.add_row(f.id[:8], f.prompt[:40] + ("..." if len(f.prompt) > 40 else ""), last_err)
        console.print(err_table)
