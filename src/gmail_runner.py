from typing import Callable, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.gmail_client import GmailClient, GmailMessage
from src.pipeline import IngestionPipeline, PipelineResult


def display_gmail_table(emails: List[GmailMessage], console: Console) -> None:
    """Muestra una tabla con los correos no leídos autorizados encontrados."""
    table = Table(title="📬 Correos no leídos autorizados en Gmail", border_style="cyan")
    table.add_column("ID", style="bold cyan")
    table.add_column("De", style="white")
    table.add_column("Asunto", style="yellow")
    table.add_column("Fecha", style="magenta")
    table.add_column("Snippet", style="dim")

    for email in emails:
        snip = email.snippet[:50] + "..." if len(email.snippet) > 50 else email.snippet
        table.add_row(email.id, email.sender, email.subject, email.date, snip)
    console.print(table)


def run_gmail(
    process: bool = False,
    force_mock: bool = False,
    client: Optional[GmailClient] = None,
    pipeline: Optional[IngestionPipeline] = None,
    console: Optional[Console] = None,
    result_callback: Optional[Callable[[PipelineResult], None]] = None,
) -> List[GmailMessage]:
    """
    Orquesta la consulta y, opcionalmente, el procesamiento y marcado como leído
    de correos autorizados en Gmail.
    Retorna la lista de correos autorizados encontrados.
    """
    console = console or Console()
    console.print("[bold blue]▶ Conectando a Gmail API...[/]")

    try:
        client = client or GmailClient()
        console.print(f"Buscando correos no leídos con remitente: [cyan]{client.authorized_sender}[/]")
        emails = client.fetch_authorized_unread_emails()
    except FileNotFoundError as fnf:
        console.print(Panel(f"[bold red]❌ Archivo no encontrado:[/] {fnf}", border_style="red"))
        return []
    except Exception as e:
        console.print(Panel(f"[bold red]❌ Error al consultar Gmail API:[/] {e}", border_style="red"))
        return []

    if not emails:
        console.print(f"[yellow]No se encontraron correos no leídos autorizados de {client.authorized_sender}.[/]\n")
        return []

    console.print(f"[bold green]✔ Se encontraron {len(emails)} correo(s) autorizado(s):[/]\n")
    display_gmail_table(emails, console)

    if not process:
        console.print("\n[dim]Para procesar y exportar a Excel/JSON, ejecuta:[/] [bold cyan]python main.py gmail --process[/]\n")
        return emails

    pipeline = pipeline or IngestionPipeline(force_mock=force_mock)
    for email in emails:
        console.print(f"\n[bold cyan]─── Procesando Correo ID: {email.id} ({email.subject}) ───[/]")
        result = pipeline.process_gmail_message(email)

        if result_callback:
            result_callback(result)

        if result.success:
            try:
                client.mark_as_read(email.id)
                console.print(f"[bold green]✔ Correo {email.id} marcado como leído en Gmail.[/]")
            except Exception as e:
                console.print(f"[yellow]No se pudo marcar como leído: {e}[/]")

    return emails
