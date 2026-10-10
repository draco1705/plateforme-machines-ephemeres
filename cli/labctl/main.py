"""Labctl — CLI for Plateforme Machines Éphémères."""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
import urllib3
import webbrowser

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Suppress insecure SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = os.getenv("LABHACKER_API_URL", "http://localhost:8000")
TOKEN_FILE = os.path.expanduser("~/.labhacker_token")
console = Console()


# ─── HELPERS ────────────────────────────────────────
def get_token():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            return None
    return None


def set_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass


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


def format_remaining_time(end_time_str):
    if not end_time_str:
        return "-"
    try:
        # Parse ISO date
        end = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = end - now
        if diff.total_seconds() <= 0:
            return "[dim]Expiré[/dim]"
        mins = int(diff.total_seconds() // 60)
        hours = mins // 60
        rem_mins = mins % 60
        if hours > 0:
            return f"{hours}h {rem_mins}m"
        return f"{rem_mins}m"
    except Exception:
        return "-"


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


def cmd_create_machine(args):
    """Créer un template de machine dans le catalogue."""
    payload = {
        "name": args.name,
        "image": args.image,
        "cpu_min": args.cpu,
        "ram_min_mb": args.ram,
        "port": args.port,
    }
    r = requests.post(f"{API_URL}/machines", json=payload, headers=auth_headers())
    if r.status_code == 201:
        m = r.json()
        print_success(f"Machine créée avec succès : ID={m['id']}, Nom='{m['name']}', Image='{m['image']}'")
    else:
        print_error(f"Échec création machine : {r.status_code} {r.text}")
        sys.exit(1)


def resolve_machine_id(machine_arg, image_arg, headers):
    """Trouve ou crée une machine correspondant au nom ou à l'image."""
    target = machine_arg or image_arg
    if not target:
        return None

    r = requests.get(f"{API_URL}/machines", headers=headers)
    if r.status_code == 200:
        machines = r.json()
        for m in machines:
            if m["name"].lower() == target.lower() or target.lower() in m["image"].lower():
                return m["id"]

    # Si non trouvé et image spécifiée, créer dynamiquement
    create_payload = {
        "name": target.split("/")[-1].split(":")[0],
        "image": target if ":" in target or "/" in target else f"{target}:latest",
        "cpu_min": 1,
        "ram_min_mb": 256,
        "port": 80,
    }
    cr = requests.post(f"{API_URL}/machines", json=create_payload, headers=headers)
    if cr.status_code == 201:
        new_m = cr.json()
        print_info(f"Modèle machine '{new_m['name']}' créé dynamiquement (ID={new_m['id']})")
        return new_m["id"]

    return None


def cmd_reserve(args):
    headers = auth_headers()
    machine_id = args.machine_id

    if not machine_id:
        target_name = args.image or args.machine
        if target_name:
            machine_id = resolve_machine_id(args.machine, args.image, headers)
            if not machine_id:
                print_error(f"Machine ou image '{target_name}' introuvable.")
                sys.exit(1)
        else:
            print_error("Veuillez spécifier soit --machine-id, soit --image / --machine.")
            sys.exit(1)

    payload = {
        "machine_id": machine_id,
        "cpu": args.cpu,
        "ram_mb": args.ram,
        "duration_minutes": args.duration,
    }
    r = requests.post(f"{API_URL}/reservations", json=payload, headers=headers)
    if r.status_code == 201:
        res = r.json()
        print_success(f"Réservation #{res['id']} créée (status: {res['status']})")
        print_info(f"Suivez avec : labctl status {res['id']}")
        print_info(f"Connectez-vous avec : labctl connect {res['id']}")
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
    table.add_column("Temps restant")
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
        rem = format_remaining_time(res.get("end_time"))
        table.add_row(
            str(res["id"]),
            str(res.get("machine_id", "?")),
            str(res.get("worker_id") or "-"),
            str(res["cpu"]),
            f"{res['ram_mb']} MB",
            f"[{color}]{st}[/{color}]",
            rem,
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
    rem = format_remaining_time(res.get("end_time"))
    panel = Panel.fit(
        f"[bold]Status[/bold]        : {res['status']}\n"
        f"[bold]Machine ID[/bold]    : {res.get('machine_id')}\n"
        f"[bold]Worker ID[/bold]     : {res.get('worker_id') or '-'}\n"
        f"[bold]Container ID[/bold]  : {res.get('container_id') or '-'}\n"
        f"[bold]CPU[/bold]           : {res['cpu']}\n"
        f"[bold]RAM[/bold]           : {res['ram_mb']} MB\n"
        f"[bold]Start[/bold]         : {res.get('start_time')}\n"
        f"[bold]End[/bold]           : {res.get('end_time')}\n"
        f"[bold]Temps restant[/bold] : {rem}\n"
        f"[bold]Access URL[/bold]    : {res.get('access_url') or '-'}",
        title=f"Réservation #{res['id']}",
        border_style="cyan",
    )
    console.print(panel)
    if res.get("status") == "RUNNING" and res.get("access_url"):
        print_info(f"Pour vous connecter : labctl connect {res['id']}")


def cmd_start(args):
    r = requests.post(f"{API_URL}/reservations/{args.id}/start", headers=auth_headers())
    if r.status_code in (200, 202):
        print_success(f"Réservation #{args.id} démarrée")
    else:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)


def cmd_stop(args):
    r = requests.post(f"{API_URL}/reservations/{args.id}/stop", headers=auth_headers())
    if r.status_code in (200, 202):
        print_success(f"Réservation #{args.id} arrêtée")
    else:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)


def cmd_delete(args):
    r = requests.delete(
        f"{API_URL}/reservations/{args.id}",
        headers=auth_headers(),
    )
    if r.status_code == 204:
        print_success(f"Réservation #{args.id} annulée")
    elif r.status_code == 409:
        print_error("Réservation déjà terminée")
    else:
        print_error(f"{r.status_code} {r.text}")
        sys.exit(1)


def cmd_connect(args):
    """Vérifie l'accès au conteneur de la réservation et s'y connecte via le Reverse Proxy."""
    headers = auth_headers()
    print_info(f"Vérification de la réservation #{args.id}...")

    # Attente / vérification de l'état
    max_wait = 15 if args.wait else 1
    res = None
    for attempt in range(max_wait):
        r = requests.get(f"{API_URL}/reservations/{args.id}", headers=headers)
        if r.status_code != 200:
            print_error(f"Réservation #{args.id} introuvable : {r.status_code} {r.text}")
            sys.exit(1)
        res = r.json()
        if res.get("status") == "RUNNING":
            break
        elif res.get("status") in ("EXPIRED", "CANCELLED", "FAILED"):
            print_error(f"La réservation #{args.id} est dans l'état : {res.get('status')}")
            sys.exit(1)
        if attempt < max_wait - 1:
            console.print(f"[yellow]En attente de démarrage (statut: {res.get('status')})...[/yellow]")
            time.sleep(2)

    status = res.get("status")
    if status != "RUNNING":
        print_error(f"Le conteneur n'est pas encore prêt (statut actuel: {status}). Réessayez dans un instant avec '--wait'.")
        sys.exit(1)

    access_url = res.get("access_url") or f"https://lab-{args.id}.lab.local"
    console.print(f"[bold green]✓ Conteneur actif ![/bold green]")
    console.print(f"  • Worker       : [cyan]{res.get('worker_id') or 'local'}[/cyan]")
    console.print(f"  • Container ID : [cyan]{res.get('container_id', '')[:12]}[/cyan]")
    console.print(f"  • URL Proxy    : [bold underline cyan]{access_url}[/bold underline cyan]")

    # Tester la connexion HTTP(S) via le reverse proxy Traefik
    print_info("Test de connexion HTTP/HTTPS via le Reverse Proxy...")
    host_header = f"lab-{args.id}.lab.local"
    connected = False
    http_status = None
    sample_content = ""

    # Test 1: Via nom de domaine direct
    try:
        resp = requests.get(access_url, verify=False, timeout=5)
        connected = True
        http_status = resp.status_code
        sample_content = resp.text[:120].strip().replace("\n", " ")
    except Exception:
        # Test 2: Fallback direct sur localhost avec Host header (au cas où DNS/hosts pas configuré)
        try:
            resp = requests.get("https://127.0.0.1/", headers={"Host": host_header}, verify=False, timeout=5)
            connected = True
            http_status = resp.status_code
            sample_content = resp.text[:120].strip().replace("\n", " ")
        except Exception:
            try:
                resp = requests.get("http://127.0.0.1/", headers={"Host": host_header}, timeout=5)
                connected = True
                http_status = resp.status_code
                sample_content = resp.text[:120].strip().replace("\n", " ")
            except Exception as e:
                connected = False

    if connected:
        print_success(f"Connexion réussie au conteneur ! HTTP {http_status}")
        if sample_content:
            console.print(f"  [dim]Réponse : {sample_content}[/dim]")
    else:
        print_info("Le conteneur démarre ou la résolution DNS locale nécessite 'scripts/update-hosts.ps1'.")

    console.print("\n[bold]Manières d'accéder au conteneur :[/bold]")
    console.print(f"  1. Navigateur Web : [underline cyan]{access_url}[/underline cyan]")
    console.print(f"  2. Commande curl  : [green]curl -k {access_url}[/green]")
    console.print(f"     (Alternative)  : [green]curl -k --resolve {host_header}:443:127.0.0.1 {access_url}[/green]")

    # Indication SSH pour machines de type Kali
    console.print(f"  3. Connexion SSH (Kali / Linux) :")
    console.print(f"     [green]ssh root@{host_header} -p 22[/green]  (mdp: kali)")

    if args.browser:
        print_info("Ouverture du navigateur web...")
        webbrowser.open(access_url)


# ─── MAIN ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="labctl",
        description="CLI dédiée pour Plateforme de Machines Éphémères",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p = sub.add_parser("login", help="Se connecter à la plateforme")
    p.add_argument("username", help="Email utilisateur")
    p.add_argument("password", help="Mot de passe")
    p.set_defaults(func=cmd_login)

    # logout
    p = sub.add_parser("logout", help="Se déconnecter")
    p.set_defaults(func=cmd_logout)

    # machines
    p = sub.add_parser("machines", help="Lister les templates de machines")
    p.set_defaults(func=cmd_machines)

    # create-machine
    p = sub.add_parser("create-machine", help="Créer un nouveau template de machine")
    p.add_argument("--name", required=True, help="Nom de la machine (ex: kali, ubuntu)")
    p.add_argument("--image", required=True, help="Image Docker (ex: kalilinux/kali-rolling)")
    p.add_argument("--cpu", type=int, default=1, help="CPU minimum requis")
    p.add_argument("--ram", type=int, default=512, help="RAM minimum (MB)")
    p.add_argument("--port", type=int, default=80, help="Port exposé par le conteneur")
    p.set_defaults(func=cmd_create_machine)

    # reserve
    p = sub.add_parser("reserve", help="Créer une réservation (instancier une machine)")
    p.add_argument("--machine-id", type=int, default=None, help="ID de la machine template")
    p.add_argument("--image", default=None, help="Nom de l'image (ex: kali, nginxdemos/hello)")
    p.add_argument("--machine", default=None, help="Nom du template de machine (ex: kali, nginx)")
    p.add_argument("--cpu", type=int, default=1, help="Nombre de coeurs CPU")
    p.add_argument("--ram", type=int, default=512, help="Mémoire RAM en MB")
    p.add_argument("--duration", type=int, default=30, help="Durée en minutes")
    p.set_defaults(func=cmd_reserve)

    # list
    p = sub.add_parser("list", help="Lister les réservations actives")
    p.set_defaults(func=cmd_list)

    # status
    p = sub.add_parser("status", help="Détails et statut d'une réservation")
    p.add_argument("id", type=int, help="ID de la réservation")
    p.set_defaults(func=cmd_status)

    # connect
    p = sub.add_parser("connect", help="Se connecter à un conteneur via le Reverse Proxy")
    p.add_argument("id", type=int, help="ID de la réservation")
    p.add_argument("--wait", action="store_true", help="Attendre que le conteneur soit en RUNNING")
    p.add_argument("--browser", action="store_true", help="Ouvrir automatiquement dans le navigateur")
    p.set_defaults(func=cmd_connect)

    # start
    p = sub.add_parser("start", help="Démarrer une réservation")
    p.add_argument("id", type=int, help="ID de la réservation")
    p.set_defaults(func=cmd_start)

    # stop
    p = sub.add_parser("stop", help="Arrêter une réservation")
    p.add_argument("id", type=int, help="ID de la réservation")
    p.set_defaults(func=cmd_stop)

    # delete
    p = sub.add_parser("delete", help="Annuler / supprimer une réservation")
    p.add_argument("id", type=int, help="ID de la réservation")
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
