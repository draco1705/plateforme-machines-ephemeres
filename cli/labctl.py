import argparse
import requests
import json
import sys
import os

API_URL = os.getenv("LABHACKER_API_URL", "http://localhost:8000")
TOKEN_FILE = os.path.expanduser("~/.labhacker_token")

def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return None

def set_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def login(args):
    print("Logging in...")
    resp = requests.post(f"{API_URL}/login", json={"username": args.username, "password": args.password})
    if resp.status_code == 200:
        set_token(resp.json().get("token"))
        print("Logged in successfully!")
    else:
        print("Login failed!")

def logout(args):
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print("Logged out successfully!")
    else:
        print("Not logged in.")

def reserve(args):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = {"machine": args.machine, "duration": args.duration}
    resp = requests.post(f"{API_URL}/reservations", json=data, headers=headers)
    if resp.status_code == 201:
        res = resp.json()
        print(f"Reservation successful! ID: {res['id']}, Machine: {res['machine']}, Status: {res['status']}")
    else:
        print(f"Failed to reserve: {resp.text}")

def list_res(args):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{API_URL}/reservations", headers=headers)
    if resp.status_code == 200:
        reservations = resp.json()
        print(f"{'ID':<40} | {'Machine':<10} | {'Worker':<10} | {'Status'}")
        print("-" * 80)
        for r in reservations:
            print(f"{r['id']:<40} | {r['machine']:<10} | {r.get('worker', 'N/A'):<10} | {r['status']}")
    else:
        print(f"Failed to fetch: {resp.text}")

def delete_res(args):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.delete(f"{API_URL}/reservations/{args.id}", headers=headers)
    if resp.status_code == 200:
        print("Reservation deleted.")
    else:
        print(f"Failed to delete: {resp.text}")

def main():
    parser = argparse.ArgumentParser(description="LabHacker CLI")
    subparsers = parser.add_subparsers(dest="command")

    login_p = subparsers.add_parser("login")
    login_p.add_argument("username")
    login_p.add_argument("password")

    subparsers.add_parser("logout")

    reserve_p = subparsers.add_parser("reserve")
    reserve_p.add_argument("--machine", default="kali", help="Machine image to deploy")
    reserve_p.add_argument("--duration", type=int, default=3600, help="Duration in seconds")

    subparsers.add_parser("list")

    delete_p = subparsers.add_parser("delete")
    delete_p.add_argument("id", help="Reservation ID")

    args = parser.parse_args()

    if args.command == "login":
        login(args)
    elif args.command == "logout":
        logout(args)
    elif args.command == "reserve":
        reserve(args)
    elif args.command == "list":
        list_res(args)
    elif args.command == "delete":
        delete_res(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
