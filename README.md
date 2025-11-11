# 🪙 CryptoRecon

**CryptoRecon** is a Python-based toolset for **automated cryptocurrency transaction reconciliation**. It fetches transaction data from multiple chains and wallets, enriches it with contextual information, classifies transactions (transfers, swaps, liquidity events, staking, rewards), and produces structured outputs suitable for tax reporting, portfolio tracking, or analytics.

---

## 🚀 Features

- **Multi-chain support**: Fetch and reconcile transactions from Solana, Ethereum, BNB Chain, Polygon, and others.
- **Transaction enrichment**: Add context via blockchain APIs (e.g., Helius for Solana) and parse instructions for swaps, liquidity, staking, and rewards.
- **Automated classification**: Identify and label transaction types automatically.
- **CSV exports for tax tools**: Generate ready-to-import files for Koinly, CoinTracking, or custom analytics.
- **Flexible architecture**: Modular design allows adding new chains, wallets, or DeFi protocols.
- **Merge & clean**: Combine multiple token movements into single entries, exclude unnecessary fee rows, and simplify reporting.

---

## 🧩 Requirements

- Python 3.9+
- Libraries:
```bash
pip install requests pandas


