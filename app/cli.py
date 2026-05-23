"""
cli.py — Rich terminal CLI for the extractor.
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from app.extractor import extract
from app.logger import get_logger
from app.utils import pretty_json, read_file

console = Console()
logger = get_logger("cli")


def _print_result(result_json: str, elapsed: float, retries: int, repair: bool, model: str) -> None:
    syntax = Syntax(result_json, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="[bold green]Extraction Result[/bold green]", expand=True))

    table = Table(title="Run Metadata", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=24)
    table.add_column("Value")
    table.add_row("Model Used", model)
    table.add_row("Processing Time", f"{elapsed:.3f}s")
    table.add_row("Retries", str(retries))
    table.add_row("Repair Applied", "[yellow]Yes[/yellow]" if repair else "[green]No[/green]")
    console.print(table)


async def _run_extraction(text: str) -> None:
    with console.status("[bold yellow]Extracting structured data…[/bold yellow]"):
        try:
            result = await extract(text)
        except RuntimeError as exc:
            # AuthenticationError surfaces as RuntimeError with helpful message
            console.print(f"\n[bold red]Configuration Error:[/bold red] {exc}")
            console.print(
                "\n[bold yellow]How to fix:[/bold yellow]\n"
                "  1. Go to [link=https://openrouter.ai/keys]https://openrouter.ai/keys[/link]\n"
                "  2. Create a free API key\n"
                "  3. Open your [bold].env[/bold] file and set:\n"
                "     [green]OPENROUTER_API_KEY=sk-or-v1-your-key-here[/green]\n"
                "  4. Make sure you are checking [bold]Activity[/bold] → [bold]Logs[/bold] "
                "in the correct [bold]Workspace[/bold] on OpenRouter"
            )
            sys.exit(1)
        except Exception as exc:
            console.print(f"[bold red]Extraction failed:[/bold red] {exc}")
            logger.error("CLI extraction failed: %s", exc, exc_info=True)
            sys.exit(1)

    ticket_json = pretty_json(result.ticket.model_dump())
    _print_result(
        ticket_json,
        elapsed=result.metadata.processing_time_seconds,
        retries=result.metadata.retry_count,
        repair=result.metadata.repair_applied,
        model=result.metadata.model_used,
    )


async def _diagnose() -> None:
    """Quick connectivity check — sends a minimal request to verify the API key."""
    from openai import AsyncOpenAI, AuthenticationError, RateLimitError
    from app.config import config

    console.print("\n[bold cyan]Running API diagnostics…[/bold cyan]\n")

    # Check 1 — config loaded
    masked = config.openrouter_api_key[:8] + "..." + config.openrouter_api_key[-4:] \
        if len(config.openrouter_api_key) > 12 else "TOO SHORT — likely invalid"
    console.print(f"  [green]✓[/green] API key loaded: [dim]{masked}[/dim]")
    console.print(f"  [green]✓[/green] Primary model: [dim]{config.model_name}[/dim]")
    console.print(f"  [green]✓[/green] Fallback models: [dim]{', '.join(config.fallback_models)}[/dim]")

    # Check 2 — live API call
    console.print("\n  Testing live connection to OpenRouter…")
    client = AsyncOpenAI(api_key=config.openrouter_api_key, base_url=config.base_url, default_headers={"HTTP-Referer": config.http_referer, "X-Title": config.app_title})
    try:
        resp = await client.chat.completions.create(
            model=config.model_name,
            max_tokens=5,
            messages=[{"role": "user", "content": "Hi"}],
        )
        console.print(f"  [green]✓[/green] API key is [bold green]VALID[/bold green] — "
                      f"got response from '{config.model_name}'")
        console.print(f"  [green]✓[/green] Sample reply: [dim]{resp.choices[0].message.content!r}[/dim]")
    except AuthenticationError:
        console.print(
            "  [red]✗[/red] API key is [bold red]INVALID[/bold red].\n"
            "    → Get a valid key at [link=https://openrouter.ai/keys]https://openrouter.ai/keys[/link]\n"
            "    → Make sure OPENROUTER_API_KEY in .env starts with 'sk-or-v1-'"
        )
    except RateLimitError:
        console.print(
            "  [yellow]![/yellow] API key is [bold yellow]VALID[/bold yellow] but "
            f"'{config.model_name}' is currently rate-limited.\n"
            "    → This is normal for free-tier models — the fallback chain will handle it.\n"
            "    → Check [link=https://openrouter.ai/activity]https://openrouter.ai/activity[/link] "
            "to confirm requests are reaching OpenRouter.\n"
            "    → Make sure you are viewing logs in the correct [bold]Workspace[/bold]."
        )
    except Exception as exc:
        console.print(f"  [red]✗[/red] Unexpected error: {exc}")


def cmd_extract_file(file_path: str) -> None:
    console.print(f"\n[bold blue]Reading:[/bold blue] {file_path}")
    try:
        text = read_file(file_path)
    except FileNotFoundError:
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        sys.exit(1)
    except IOError as exc:
        console.print(f"[bold red]Cannot read file:[/bold red] {exc}")
        sys.exit(1)
    console.print(Panel(text[:800] + ("…" if len(text) > 800 else ""), title="Input Text"))
    asyncio.run(_run_extraction(text))


def cmd_extract_text(raw_text: str) -> None:
    if not raw_text or not raw_text.strip():
        console.print("[bold red]Error:[/bold red] Text argument must not be empty.")
        sys.exit(1)
    console.print(Panel(raw_text, title="Input Text"))
    asyncio.run(_run_extraction(raw_text))


def cmd_diagnose() -> None:
    asyncio.run(_diagnose())


def print_usage() -> None:
    console.print(
        Panel(
            "\n"
            "[bold]Extract from a file:[/bold]\n"
            "  python run.py extract sample_inputs/customer_email.txt\n\n"
            "[bold]Extract from raw text:[/bold]\n"
            '  python run.py text "Customer wants refund for broken headphones"\n\n'
            "[bold]Diagnose API key / connectivity:[/bold]\n"
            "  python run.py diagnose\n",
            title="[bold cyan]structured-json-extractor CLI[/bold cyan]",
        )
    )