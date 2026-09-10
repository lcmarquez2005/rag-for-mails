import sys
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

from src.config import SAMPLE_MAILS_DIR, OUTPUT_JSON_PATH, OLLAMA_MODEL
from src.extractor import is_ollama_available
from src.pipeline import IngestionPipeline, PipelineResult
from src.schemas import ShiftReport
from src.gmail_runner import run_gmail

try:
    import readline
    # Habilitar edición de línea de GNU readline (Backspace, Supr, Flechas)
    readline.parse_and_bind(r'"\e[3~": delete-char')
    readline.parse_and_bind(r'"\C-h": backward-delete-char')
    readline.parse_and_bind(r'"\C-?": backward-delete-char')
except ImportError:
    pass

console = Console()


def display_welcome_banner():
    banner = Text()
    banner.append("🏭 RAG FOR MAILS - EXTRACCIÓN DE DATOS DE MOLDEO\n", style="bold cyan")
    banner.append("Extracción Estructurada con LangChain, Ollama y Pydantic V2\n", style="italic white")
    
    ollama_status = "[bold green]ONLINE (qwen3:8b)[/]" if is_ollama_available() else "[bold yellow]OFFLINE (Usando Motor Mock Determinista)[/]"
    banner.append(f"Estado de Ollama: {ollama_status}", style="dim")
    
    console.print(Panel(banner, border_style="cyan", padding=(1, 2)))


def display_report_results(result: PipelineResult):
    if not result.success:
        console.print(Panel(f"[bold red]❌ Error de Procesamiento:[/] {result.error_message}", border_style="red"))
        return

    report: ShiftReport = result.report
    
    table = Table(title=f"📋 Datos Extraídos ({result.source_file or 'Entrada Directa'})", border_style="bright_blue")
    table.add_column("Máquina ID", style="bold cyan", justify="center")
    table.add_column("Turno", style="white", justify="center")
    table.add_column("Líder de Turno", style="magenta")
    table.add_column("Paro (min)", justify="right", style="yellow")
    table.add_column("Piezas Aprobadas", justify="right", style="green")
    table.add_column("Piezas Rechazadas", justify="right", style="red")
    table.add_column("Motivos", style="white")

    for rec in report.records:
        reasons_text = ", ".join(rec.reasons) if rec.reasons else "N/A"
        table.add_row(
            rec.machine_id,
            rec.shift or "N/A",
            rec.shift_leader,
            str(rec.downtime_minutes),
            str(rec.approved_parts),
            str(rec.rejected_parts),
            reasons_text
        )

    console.print(table)
    console.print(f"[bold green]✔[/] Excel actualizado en: [cyan]{result.excel_path}[/]")
    console.print(f"[bold green]✔[/] JSON guardado en: [cyan]{result.json_path}[/]\n")


def run_demo(force_mock: bool = False):
    console.print("[bold blue]▶ Ejecutando caso de prueba del README (Turno 1 Estándar)...[/]\n")
    pipeline = IngestionPipeline(force_mock=force_mock)
    demo_file = SAMPLE_MAILS_DIR / "turno1_estandar.txt"
    result = pipeline.process_file(demo_file)
    display_report_results(result)


def run_file(file_path: str, force_mock: bool = False):
    console.print(f"[bold blue]▶ Procesando archivo: {file_path}...[/]\n")
    pipeline = IngestionPipeline(force_mock=force_mock)
    result = pipeline.process_file(file_path)
    display_report_results(result)


def run_batch(force_mock: bool = False):
    console.print(f"[bold blue]▶ Procesando lote completo en {SAMPLE_MAILS_DIR}...[/]\n")
    pipeline = IngestionPipeline(force_mock=force_mock)
    results = pipeline.process_directory(SAMPLE_MAILS_DIR)
    
    for res in results:
        display_report_results(res)


def run_interactive(force_mock: bool = False):
    pipeline = IngestionPipeline(force_mock=force_mock)
    try:
        while True:
            console.print("\n[bold cyan]─── MENÚ INTERACTIVO ───[/]")
            console.print("1. Procesar archivo de muestra")
            console.print("2. Pegar texto de correo/chat en vivo")
            console.print("3. Procesar todos los correos en lote (Batch)")
            console.print("4. Gmail: Consultar correos no leídos")
            console.print("5. Gmail: Consultar y procesar correos (marcar como leídos)")
            console.print("6. Salir")
            
            choice = Prompt.ask("\nSelecciona una opción", choices=["1", "2", "3", "4", "5", "6"], default="1")
            
            if choice == "1":
                files = sorted(list(SAMPLE_MAILS_DIR.glob("*.txt")))
                if not files:
                    console.print("[yellow]No se encontraron archivos en data/sample_mails/[/]")
                    continue
                console.print("\nArchivos disponibles:")
                for idx, f in enumerate(files, 1):
                    console.print(f"  {idx}. {f.name}")
                f_choice = Prompt.ask("Elige el número de archivo", choices=[str(i) for i in range(1, len(files) + 1)])
                selected_file = files[int(f_choice) - 1]
                result = pipeline.process_file(selected_file)
                display_report_results(result)
            elif choice == "2":
                console.print("\n[bold yellow]Pega el texto del correo (Escribe 'FIN' en una línea separada al terminar):[/]")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "FIN":
                        break
                    lines.append(line)
                raw_text = "\n".join(lines).strip()
                if raw_text:
                    result = pipeline.process_text(raw_text, source_file="Entrada Manual")
                    display_report_results(result)
                else:
                    console.print("[yellow]Texto vacío cancelado.[/]")
            elif choice == "3":
                run_batch(force_mock=force_mock)
            elif choice == "4":
                run_gmail(
                    process=False,
                    force_mock=force_mock,
                    console=console,
                    result_callback=display_report_results,
                )
            elif choice == "5":
                run_gmail(
                    process=True,
                    force_mock=force_mock,
                    console=console,
                    result_callback=display_report_results,
                )
            elif choice == "6":
                console.print("[bold green]¡Hasta pronto![/]")
                break
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold yellow]Operación cancelada. ¡Hasta pronto![/]")


def main():
    display_welcome_banner()
    args = sys.argv[1:]
    force_mock = "--mock" in args
    process_flag = "--process" in args
    args = [a for a in args if a not in ("--mock", "--process")]

    if not args or args[0] == "interactive":
        run_interactive(force_mock=force_mock)
    elif args[0] == "demo":
        run_demo(force_mock=force_mock)
    elif args[0] == "batch":
        run_batch(force_mock=force_mock)
    elif args[0] == "gmail":
        run_gmail(
            process=process_flag,
            force_mock=force_mock,
            console=console,
            result_callback=display_report_results,
        )
    elif args[0] in ("process-file", "file") and len(args) > 1:
        run_file(args[1], force_mock=force_mock)
    else:
        # Si se pasó una ruta directa
        if Path(args[0]).exists():
            run_file(args[0], force_mock=force_mock)
        else:
            console.print(f"[bold red]Comando no reconocido:[/] {args[0]}")
            console.print("Uso: python main.py [demo | batch | gmail [--process] | process-file <ruta> | interactive] [--mock]")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold yellow]Programa interrumpido.[/]")
