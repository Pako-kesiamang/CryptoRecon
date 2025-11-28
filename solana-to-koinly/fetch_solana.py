#!/usr/bin/env python3
"""
fetch_helius.py
Fetch Solana transactions for an address using the Helius API.
Save as positions.json (ready for solana_to_koinly.py)
"""

import requests
import json
import os

def fetch_transactions(address: str, api_key: str, limit: int = 1000):
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions?api-key={api_key}"
    body = {"limit": limit}
    print(f"Requesting: {url} with body={body}")

    try:
        res = requests.post(url, json=body, timeout=20)
    except requests.RequestException as e:
        print("Request failed:", e)
        raise SystemExit(1)

    if res.status_code != 200:
        print(f"Helius API error {res.status_code}:")
        print(res.text)
        raise SystemExit(1)

    try:
        return res.json()
    except ValueError:
        print("Invalid JSON response from Helius:")
        print(res.text)
        raise SystemExit(1)

def save_positions(data: list, out_path: str):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved {len(data)} transactions → {out_path}")

def main():
    address = input("Enter Solana address: ").strip()
    if not (32 <= len(address) <= 44):
        print("Warning: address length looks unusual. Check the address.")

    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        key_path = os.path.join(os.path.dirname(__file__), "apikey.txt")
        if os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as kf:
                api_key = kf.read().strip()

    if not api_key:
        print("Error: Helius API key not found.")
        print("Set environment variable HELIUS_API_KEY or create solana-to-koinly/apikey.txt with the key.")
        raise SystemExit(1)

    out_path = os.path.join(os.path.dirname(__file__), "positions.json")
    data = fetch_transactions(address, api_key)
    save_positions(data, out_path)

if __name__ == "__main__":
    main()
