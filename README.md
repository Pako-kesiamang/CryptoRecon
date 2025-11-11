# CryptoRecon
🪙 solana-to-koinly

A Python tool to convert Solana transactions into Koinly-compatible CSVs, automatically enriching liquidity positions, swaps, and token/SOL movements. Designed for crypto tax analysts and enthusiasts who want clean, ready-to-import Koinly files.

🚀 Features

Automatically fetches and parses Solana transactions.

Detects and classifies:

Sent / Received tokens

CLMM liquidity events (addLiquidity, removeLiquidity, addLiquidityByStrategy)

Token & SOL balance changes

Merges multiple token transfers per timestamp into one Koinly row.

Excludes fee rows for clean imports.

Outputs ready-to-import CSVs for Koinly.

🧩 Requirements

Python 3.9+

Libraries:

pip install requests


Helius API key for transaction enrichment.

⚙️ Setup

Clone the repository:

git clone https://github.com/<your-username>/solana-to-koinly.git
cd solana-to-koinly


Add your Helius API key to the environment:

export HELIUS_API_KEY="your_api_key_here"


Run the script:

python3 solana_to_koinly.py


Output will be saved as:

koinly_output.csv

📄 CSV Example
Date (UTC)	Sent Amount	Sent Currency	Received Amount	Received Currency	Label	TxHash
2025-11-10 15:32:11	0.45	SOL	25.3	USDC	Swap	5gPQbQ...
🧠 How It Works

Pulls Solana transaction JSONs using Helius API.

Enriches with parsed instructions for swaps, liquidity, and transfers.

Detects and classifies token movements automatically.

Converts transactions into Koinly’s import format, merging token changes per timestamp.

🛠️ Supported Instructions

addLiquidity

removeLiquidity

addLiquidityByStrategy

swap

transfer

stake / unstake

…and more Solana DeFi instructions can be added as needed.

🛠️ Future Improvements

Support for more Solana pools (Raydium, Orca, Jupiter).

Optional fee inclusion toggle.

Parallel API requests for faster batch processing.

Direct Koinly API integration.

🤝 Contributing

Pull requests welcome! For major changes, open an issue first to discuss.
