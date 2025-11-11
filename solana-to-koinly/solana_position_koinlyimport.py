#!/usr/bin/env python3
"""
solana_to_koinly.py
- Enrich LB CLMM positions with token/SOL changes
- Classify using instructions → Sent/Received
- Export Koinly CSV: **one row per token**, **NO fee rows**, merged timestamp
"""

import json
import csv
import time
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from solana.rpc.api import Client
from solders.signature import Signature

# ==============================================================
# CONFIG
# ==============================================================
# Read API key from file for security
with open("apikey.txt", "r") as f:
    HELIUS_API_KEY = f.read().strip()


INPUT_FILE = "positions.json"
ENRICHED_FILE = "positions_enriched.json"
OUTPUT_CSV = "koinly_import.csv"

# ==============================================================
# 1. Helius RPC
# ==============================================================
client = Client(f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}")

# ==============================================================
# 2. Token Symbol Lookup
# ==============================================================
TOKEN_LIST: Dict[str, str] = {}
FALLBACK_SYMBOLS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERZ8eA6x3vDb9Qb1uC3Z8v84Jq6kD45hDn": "USDT",
    "mSoLzCrqS813FJ3kC2J9WpZKuE4YjXhJ4xHza9jkjx2": "mSOL",
    "ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq": "ZEUS",
}

def load_jupiter_tokens() -> None:
    global TOKEN_LIST
    if TOKEN_LIST:
        return
    print("Downloading Jupiter token list...")
    try:
        data = requests.get("https://token.jup.ag/strict", timeout=10).json()
        TOKEN_LIST = {t["address"]: t["symbol"] for t in data}
        print(f"Loaded {len(TOKEN_LIST)} tokens.")
    except Exception as e:
        print(f"Warning: Token list failed: {e}")
        TOKEN_LIST = {}

def token_symbol(mint: str) -> str:
    if not mint:
        return ""
    load_jupiter_tokens()
    return TOKEN_LIST.get(mint, FALLBACK_SYMBOLS.get(mint, f"{mint[:6]}..{mint[-4:]}"))

# ==============================================================
# 3. Load Input
# ==============================================================
print(f"Loading {INPUT_FILE}...")
with open(INPUT_FILE, "r") as f:
    transactions = json.load(f)
print(f"Loaded {len(transactions)} transactions.")

# ==============================================================
# 4. Enrich with Balance Changes
# ==============================================================
def enrich_transaction(tx: dict) -> dict:
    tx_hash = tx.get("txHash")
    if not tx_hash:
        return tx

    try:
        sig = Signature.from_string(tx_hash)
        resp = client.get_transaction(sig, max_supported_transaction_version=0)
        result = resp.value
        if not result or not result.transaction or not result.transaction.meta:
            print(f"Warning: No meta for {tx_hash}")
            return tx

        meta = result.transaction.meta
        pre_map = {b.mint: b for b in (meta.pre_token_balances or [])}
        post_map = {b.mint: b for b in (meta.post_token_balances or [])}

        changes = []
        for mint, post in post_map.items():
            pre = pre_map.get(mint)
            pre_amt = Decimal(pre.ui_token_amount.ui_amount or 0) if pre else Decimal(0)
            post_amt = Decimal(post.ui_token_amount.ui_amount or 0)
            delta = post_amt - pre_amt
            if delta == 0:
                continue

            mint_str = str(mint)
            changes.append({
                "mint": mint_str,
                "symbol": token_symbol(mint_str),
                "change": float(delta)
            })

        # SOL delta (fee payer)
        if meta.pre_balances and meta.post_balances:
            pre_sol = meta.pre_balances[0] / 1e9
            post_sol = meta.post_balances[0] / 1e9
            sol_delta = round(post_sol - pre_sol, 9)
            if sol_delta != 0:
                changes.append({
                    "mint": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                    "change": sol_delta
                })

        tx["token_bal_change"] = changes
        return tx

    except Exception as e:
        print(f"Error enriching {tx_hash}: {e}")
        return tx

# Enrich
print("Enriching with token/SOL changes...")
for tx in transactions:
    if all(i.get("type") == "claimFee" for i in tx.get("parsedInstruction", [])):
        print(f"Skipping {tx.get('txHash', '')}: claimFee only")
        continue
    tx = enrich_transaction(tx)
    time.sleep(0.12)

with open(ENRICHED_FILE, "w") as f:
    json.dump(transactions, f, indent=2)
print(f"Enriched JSON → {ENRICHED_FILE}")

# ==============================================================
# 5. Koinly Classification (Instruction-Driven)
# ==============================================================
# ==============================================================
# 5. Koinly Classification (Instruction-Driven, REVERSED for merge wallet)
# ==============================================================
# ==============================================================
# 5. Koinly Classification (Instruction-Driven)
# ==============================================================

# Inverted logic (so actions reflect what happens to the wallet side)
INSTRUCTION_ACTION = {
    "initializePosition": "Received",
    "addLiquidityByStrategy": "Received",
    "addLiquidity": "Received",
    "removeLiquidityByRange": "Sent",
    "removeLiquidity": "Sent",
    "removeLiquidityV2": "Sent",
    "closePosition": "Sent",
    "claimFee": "Skip"
}

def get_action(tx: dict) -> str:
    instrs = [i["type"] for i in tx.get("parsedInstruction", []) if i["type"] != "claimFee"]
    if not instrs:
        return "Skip"
    if any(t in instrs for t in ["removeLiquidityByRange", "removeLiquidity", "removeLiquidityV2", "closePosition"]):
        return "Sent"
    if any(t in instrs for t in ["initializePosition", "addLiquidityByStrategy", "addLiquidity"]):
        return "Received"
    return "Other"

def get_explanation(action: str) -> str:
    return {
        "Sent": "Withdraw/Close: Sending tokens",
        "Received": "Open/Add: Receiving tokens",
        "Other": "Other — review manually"
    }.get(action, "")



def blocktime_to_koinly(block_time: int) -> str:
    return datetime.utcfromtimestamp(block_time).strftime("%Y-%m-%d %H:%M:%S")

# ==============================================================
# 6. Generate CSV — NO FEE ROWS
# ==============================================================
print("Generating Koinly CSV (no fee rows)...")
csv_rows: List[List] = []

for tx in transactions:
    action = get_action(tx)
    if action == "Skip":
        continue

    tx_hash = tx.get("txHash", "")
    block_time = tx.get("blockTime", 0)
    if block_time == 0:
        continue

    timestamp = blocktime_to_koinly(block_time)
    explanation = get_explanation(action)

    for change in tx.get("token_bal_change", []):
        amount = abs(change["change"])
        symbol = change["symbol"]
        mint = change["mint"]

        if action == "Sent":
            sent_amt, sent_curr = amount, symbol
            recv_amt, recv_curr = "", ""
        else:
            sent_amt, sent_curr = "", ""
            recv_amt, recv_curr = amount, symbol

        desc = f"{explanation} | Mint: {mint} | Tx: {tx_hash}"

        csv_rows.append([
            timestamp,
            sent_amt,
            sent_curr,
            recv_amt,
            recv_curr,
            "", "",  # Fee columns empty
            action,
            desc, tx_hash
        ])

# ==============================================================
# 7. Write CSV
# ==============================================================
header = [
    "Date",
    "Sent Amount",
    "Sent Currency",
    "Received Amount",
    "Received Currency",
    "Fee Amount",
    "Fee Currency",
    "Label",
    "Description","TxHash"
]

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(csv_rows)

print(f"\nDone! {len(csv_rows)} rows → {OUTPUT_CSV}")
print("Upload to Koinly → Wallets → Solana → Import CSV")
print(f"Audit file: {ENRICHED_FILE}")