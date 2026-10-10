"""Labctl — CLI for Plateforme Machines Éphémères."""
import argparse
import json
import os
import sys

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

API_URL = os.getenv("LABHACKER_API_URL", "http://localhost:8000")
TOKEN_FILE = os.path.expanduser("~/.labhacker_token")
console = Console()


# ─── HELPERS ────────────────────────────────────────
def get_token():
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE).read().strip()
    return None


def set_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    os.chmod(TOKEN_FILE, 0o600)


def auth_headers():
    t = get_token()
    if not t:
        console.print("[red]✗ Non connecté. Lancez 'labctl login <email> <password>'[/red]")
        sys.exit(1)
    return {"Authorization": f"Bearer {t}"}


def print_error(msg):
    console.print(f"[bold red]✗ {msg}[/bold red]")


def print_success(msg):
    console.print(f"[bold green]✓ {msg}[/bold green]")


def print_info(msg):
    console.print(f"[cyan]ℹ {msg}[/cyan]")


# ─── COMMANDS ───────────────────────────────────────
def cmd_login(args):
    try:
        r = requests.post(
            f"{API_URL}/users/login",
            data={"username": args.username, "password": args.password},
            timeout=10,
        )
    except requests.ConnectionError:
        print_error(f"Impossible de joindre {API_URL}")
        sys.exit(1)

    if r.status_code == 200:
        set_token(r.json()["access_token"])
        print_success(f"Connecté en tant que {args.username}")
    else:
        print_error(f"Login échoué : {r.status_code} {r.text}")
        sys.exit(1)


def cmd_logout(args):
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print_success("Déconnecté")
    else:
        print_info("Déjà déconnecté")


def cmd_machines(args):
    r = requests.get(f"{API_URL}/machines", headers=auth_headers())
    if r.status_code != 200:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)

    table = Table(title="Machines disponibles", box=box.ROUNDED)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Nom", style="magenta bold")
    table.add_column("Image Docker", style="green")
    table.add_column("CPU min", justify="right")
    table.add_column("RAM min", justify="right")
    table.add_column("Port", justify="right")

    for m in r.json():
        table.add_row(
            str(m["id"]), m["name"], m["image"],
            str(m["cpu_min"]), f"{m['ram_min_mb']} MB",
            str(m["port"]),
        )
    console.print(table)


def cmd_reserve(args):
    payload = {
        "machine_id": args.machine_id,
        "cpu": args.cpu,
        "ram_mb": args.ram,
        "duration_minutes": args.duration,
    }
    r = requests.post(
        f"{API_URL}/reservations",
        json=payload, headers=auth_headers(),
    )
    if r.status_code == 201:
        res = r.json()
        print_success(f"Réservation #{res['id']} créée (status: {res['status']})")
        print_info(f"Suivez avec : labctl status {res['id']}")
    else:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)


def cmd_list(args):
    r = requests.get(f"{API_URL}/reservations", headers=auth_headers())
    if r.status_code != 200:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)

    reservations = r.json()
    if not reservations:
        print_info("Aucune réservation.")
        return

    table = Table(title="Mes réservations", box=box.ROUNDED)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Machine", justify="right")
    table.add_column("Worker", justify="right")
    table.add_column("CPU", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Status")
    table.add_column("URL", style="green")

    status_color = {
        "PENDING": "yellow",
        "RUNNING": "green",
        "EXPIRED": "dim",
        "CANCELLED": "red",
        "FAILED": "bold red",
    }

    for res in reservations:
        st = res["status"]
        color = status_color.get(st, "white")
        table.add_row(
            str(res["id"]),
            str(res.get("machine_id", "?")),
            str(res.get("worker_id") or "-"),
            str(res["cpu"]),
            f"{res['ram_mb']} MB",
            f"[{color}]{st}[/{color}]",
            res.get("access_url") or "-",
        )
    console.print(table)


def cmd_status(args):
    r = requests.get(
        f"{API_URL}/reservations/{args.id}",
        headers=auth_headers(),
    )
    if r.status_code != 200:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)

    res = r.json()
    panel = Panel.fit(
        f"[bold]Status[/bold]       : {res['status']}\n"
        f"[bold]Machine ID[/bold]   : {res.get('machine_id')}\n"
        f"[bold]Worker ID[/bold]    : {res.get('worker_id') or '-'}\n"
        f"[bold]Container ID[/bold] : {res.get('container_id') or '-'}\n"
        f"[bold]CPU[/bold]          : {res['cpu']}\n"
        f"[bold]RAM[/bold]          : {res['ram_mb']} MB\n"
        f"[bold]Start[/bold]        : {res.get('start_time')}\n"
        f"[bold]End[/bold]          : {res.get('end_time')}\n"
        f"[bold]Access URL[/bold]   : {res.get('access_url') or '-'}",
        title=f"Réservation #{res['id']}",
        border_style="cyan",
    )
    console.print(panel)


def cmd_delete(args):
    r = requests.delete(
        f"{API_URL}/reservations/{args.id}",
        headers=auth_headers(),
    )
    if r.status_code == 204:
        print_success(f"Réservation #{args.id} annulée")
    elif r.status_code == 409:
        print_error(f"Réservation déjà terminée")
    else:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)


# ─── MAIN ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="labctl",
        description="CLI for Plateforme Machines Éphémères",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="Se connecter")
    p.add_argument("username", help="Email")
    p.add_argument("password")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="Se déconnecter")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("machines", help="Lister les templates")
    p.set_defaults(func=cmd_machines)

    p = sub.add_parser("reserve", help="Créer une réservation")
    p.add_argument("--machine-id", type=int, required=True)
    p.add_argument("--cpu", type=int, default=1)
    p.add_argument("--ram", type=int, default=512)
    p.add_argument("--duration", type=int, default=30, help="Minutes")
    p.set_defaults(func=cmd_reserve)

    p = sub.add_parser("list", help="Lister les réservations")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="Détails d'une réservation")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("delete", help="Annuler une réservation")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
