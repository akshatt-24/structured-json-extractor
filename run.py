"""
run.py — CLI entry point.

Usage:
    python run.py extract sample_inputs/customer_email.txt
    python run.py text "Customer wants refund"
    python run.py diagnose
"""

import sys
from rich.console import Console

console = Console()


def main() -> None:
    args = sys.argv[1:]

    if not args:
        from app.cli import print_usage
        print_usage()
        sys.exit(0)

    command = args[0].lower()

    if command == "extract":
        if len(args) < 2:
            console.print("[bold red]Error:[/bold red] 'extract' requires a file path.\n"
                          "  Example: python run.py extract sample_inputs/customer_email.txt")
            sys.exit(1)
        from app.cli import cmd_extract_file
        cmd_extract_file(args[1])

    elif command == "text":
        if len(args) < 2:
            console.print("[bold red]Error:[/bold red] 'text' requires a text argument.\n"
                          '  Example: python run.py text "Customer wants refund"')
            sys.exit(1)
        from app.cli import cmd_extract_text
        cmd_extract_text(" ".join(args[1:]))

    elif command == "diagnose":
        from app.cli import cmd_diagnose
        cmd_diagnose()

    else:
        console.print(f"[bold red]Unknown command:[/bold red] '{command}'")
        from app.cli import print_usage
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()