<div align="center">

<!-- Replace YOUR_USERNAME with your GitHub username -->
# 📈 YOUR_USERNAME

### Contribution Trading Chart

<img src="./assets/contributions-candlestick.svg" alt="GitHub Contributions Candlestick Chart" width="100%">

<sub>Each candle = 1 week · 🟢 Bullish (ended week stronger) · 🔴 Bearish (tapered off) · Blue line = 4-week SMA</sub>

---

*My GitHub contributions, visualized as a candlestick trading chart.*
*Green candles mean I finished the week coding harder than I started. Red means I took it easy.*

</div>

---

### 🛠️ How It Works

This chart is **auto-generated daily** by a GitHub Action that:

1. Fetches my contribution data via the GitHub GraphQL API
2. Converts daily commits into weekly **OHLC candlestick** data (Open/High/Low/Close)
3. Renders a pure **SVG** chart with volume bars and moving average
4. Commits the updated chart back to this repo

**Want your own?** Fork this repo, and the Action will auto-detect your username!

<details>
<summary>📖 Reading the Chart</summary>

| Element | Meaning |
|---------|---------|
| 🟢 Green candle | **Bullish week** — Sunday contributions ≥ Monday (finished strong) |
| 🔴 Red candle | **Bearish week** — Sunday contributions < Monday (tapered off) |
| Wick (thin line) | The week's **high** and **low** contribution days |
| Candle body | Range between **open** (Monday) and **close** (Sunday) |
| Blue line | **4-week Simple Moving Average** of closing values |
| Bottom bars | **Volume** — total weekly contributions |

</details>

<details>
<summary>⚡ Setup Instructions</summary>

### Quick Setup

1. **Create a new repo** named exactly your GitHub username (e.g., `octocat/octocat`)
2. **Copy these files** into the repo:
   - `generate_chart.py`
   - `.github/workflows/update-candlestick.yml`
   - `README.md` (this file — customize it!)
3. **Create the assets directory**: `mkdir assets`
4. **Push to main** — the Action will run automatically!
5. The chart updates daily at midnight UTC

### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `GITHUB_TOKEN` | Auto-provided by Actions | API authentication |
| `GITHUB_USERNAME` | Auto-detected from repo owner | Your GitHub username |
| `OUTPUT_PATH` | Default: `assets/contributions-candlestick.svg` | Where to save the SVG |

### Local Testing

```bash
# Demo mode (no token needed)
DEMO_MODE=true python generate_chart.py

# Real data
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_USERNAME=your_username
python generate_chart.py
```

</details>
