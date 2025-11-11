# CryptoRecon
# 🪙 solana-to-koinly

A Python tool to **convert Solana transactions into Koinly-compatible CSVs**, automatically enriching liquidity positions, swaps, and token/SOL movements. Designed for crypto tax analysts and enthusiasts who want clean, ready-to-import Koinly files.

---

## 🚀 Features
- Automatically fetches and parses Solana transactions.
- Detects and classifies:
  - Sent / Received tokens
  - CLMM liquidity events (`addLiquidity`, `removeLiquidity`, `addLiquidityByStrategy`)
  - Token & SOL balance changes
- Merges multiple token transfers per timestamp into **one Koinly row**.
- Excludes fee rows for clean imports.
- Outputs **ready-to-import CSVs** for Koinly.

---

## 🧩 Requirements
- Python 3.9+
- Libraries:
```bash
pip install requests

