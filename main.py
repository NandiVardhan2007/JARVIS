"""
VISION — Standalone Autonomous AI Multimodal Operating System.
Main entry point supporting CLI mode, Web Gateway mode, and Full Autonomous Daemon mode.
"""

import sys
import asyncio
import argparse
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from loguru import logger

from vision.config import config
from vision.core.engine import vision_engine
from vision.cognitive.load_balancer import load_balancer
from vision.tools.registry import tool_registry

console = Console()


def print_banner():
    banner = Text("""
 ██╗   ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗
 ██║   ██║██║██╔════╝██║██╔═══██╗████╗  ██║
 ██║   ██║██║███████╗██║██║   ██║██╔██╗ ██║
 ╚██╗ ██╔╝██║╚════██║██║██║   ██║██║╚██╗██║
  ╚████╔╝ ██║███████║██║╚██████╔╝██║ ╚████║
   ╚═══╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
    Autonomous Multimodal AI Operating System
    """, style="bold cyan")
    console.print(Panel(banner, border_style="cyan", subtitle="v1.0.0 Standalone Engine"))

    table = Table(title="System Endpoints & Active Engine Config", border_style="blue")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Configuration / Status", style="green")

    table.add_row("LLM Load Balancer", f"{len(load_balancer.providers)} endpoints ({config.VISION_LOAD_BALANCER_STRATEGY})")
    table.add_row("Primary Model", f"Groq ({config.VISION_LLM_MODEL})")
    table.add_row("Fallback / Sub-Agents", f"NVIDIA NIM ({config.VISION_NIM_LLM_MODEL})")
    table.add_row("TTS Engine", f"Cartesia / Piper ({config.VISION_TTS_VOICE})")
    table.add_row("STT Engine", f"Groq Whisper ({config.VISION_STT_MODEL})")
    table.add_row("Registered Tools", f"{len(tool_registry.get_all_schemas())} tools active")
    table.add_row("Mobile Control", f"ADB -> {config.VISION_PHONE_IP}:{config.VISION_PHONE_PORT}")
    table.add_row("Web Server Host", f"http://{config.HOST}:{config.PORT}")

    console.print(table)


async def run_cli_mode():
    """Interactive CLI chat loop with real-time tool execution."""
    await vision_engine.initialize()
    console.print("\n[bold green]VISION CLI Online.[/bold green] Type 'exit' or 'quit' to close.\n")

    session_id = "cli_session"
    while True:
        try:
            user_input = console.input("[bold yellow]You > [/bold yellow]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[bold red]Shutting down VISION...[/bold red]")
                break

            with console.status("[bold cyan]VISION is thinking & orchestrating...[/bold cyan]", spinner="dots"):
                result = await vision_engine.process_user_input(
                    user_text=user_input,
                    session_id=session_id,
                    channel="cli",
                    synthesize_voice=False
                )

            console.print(f"[bold cyan]VISION ({result.get('provider', 'AI')} - {result.get('latency_ms', 0):.0f}ms):[/bold cyan]\n{result.get('response')}\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]\n")


def run_web_mode():
    """Launch FastAPI Web Server & WebSocket gateway."""
    uvicorn.run(
        "vision.gateways.web.server:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )


def main():
    parser = argparse.ArgumentParser(description="VISION Autonomous AI System")
    parser.add_argument("--mode", choices=["cli", "web", "all"], default="cli", help="Operating mode")
    args = parser.parse_args()

    print_banner()

    if args.mode == "web":
        run_web_mode()
    else:
        asyncio.run(run_cli_mode())


if __name__ == "__main__":
    main()
