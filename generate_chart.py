#!/usr/bin/env python3
"""
GitHub Contributions Candlestick Chart Generator
═══════════════════════════════════════════════════

Transforms your GitHub contribution history into a trading-style
candlestick (OHLC) chart SVG for your profile README.

Each candle = 1 week:
  - Open  = Monday's contributions
  - Close = Sunday's contributions
  - High  = Max daily contributions that week
  - Low   = Min daily contributions that week
  - Green = Bullish (Close >= Open)
  - Red   = Bearish (Close < Open)

Usage:
  # With GitHub token (real data):
  GITHUB_TOKEN=ghp_xxx GITHUB_USERNAME=yourname python generate_chart.py

  # Demo mode (sample data):
  DEMO_MODE=true python generate_chart.py

Environment Variables:
  GITHUB_TOKEN    - GitHub Personal Access Token (read:user scope)
  GITHUB_USERNAME - GitHub username to fetch contributions for
  OUTPUT_PATH     - Output SVG path (default: assets/contributions-candlestick.svg)
  DEMO_MODE       - Set to "true" to use sample data instead of API
"""

import json
import math
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

GITHUB_API = "https://api.github.com/graphql"

# Chart dimensions
WIDTH = 900
HEIGHT = 470
MARGIN = {"top": 70, "right": 40, "bottom": 60, "left": 55}
VOLUME_HEIGHT = 50
VOLUME_GAP = 10

# Colors (GitHub dark theme)
COLORS = {
    "bg":            "#0d1117",
    "bg_bottom":     "#010409",
    "panel":         "#161b22",
    "border":        "#30363d",
    "grid":          "#21262d",
    "text":          "#c9d1d9",
    "text_dim":      "#8b949e",
    "green":         "#26a641",
    "green_bright":  "#3fb950",
    "red":           "#f85149",
    "red_bright":    "#ff7b72",
    "green_vol":     "rgba(38,166,65,0.25)",
    "red_vol":       "rgba(248,81,73,0.25)",
    "ma_line":       "#58a6ff",
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ═══════════════════════════════════════════════════════════════════════════
#  GITHUB API
# ═══════════════════════════════════════════════════════════════════════════

def fetch_contributions(username, token):
    """Fetch contribution calendar data from GitHub GraphQL API."""
    query = """
    query($userName: String!) {
      user(login: $userName) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                weekday
              }
            }
          }
        }
      }
    }
    """

    payload = json.dumps({
        "query": query,
        "variables": {"userName": username}
    }).encode("utf-8")

    req = urllib.request.Request(
        GITHUB_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ GitHub API error: {e.code} {e.reason}")
        body = e.read().decode() if e.fp else ""
        if body:
            print(f"   {body[:200]}")
        sys.exit(1)

    if "errors" in data:
        for err in data["errors"]:
            print(f"❌ GraphQL error: {err.get('message', err)}")
        sys.exit(1)

    user = data.get("data", {}).get("user")
    if not user:
        print(f"❌ User '{username}' not found on GitHub.")
        sys.exit(1)

    return user["contributionsCollection"]["contributionCalendar"]


# ═══════════════════════════════════════════════════════════════════════════
#  DATA PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

def contributions_to_ohlc(calendar):
    """Convert daily contribution data to weekly OHLC candles."""
    weeks = calendar["weeks"]
    candles = []

    for week in weeks:
        days = week["contributionDays"]
        if not days:
            continue

        counts = [d["contributionCount"] for d in days]
        dates = [d["date"] for d in days]

        open_val = counts[0]
        close_val = counts[-1]
        high_val = max(counts)
        low_val = min(counts)
        total_vol = sum(counts)

        candles.append({
            "open":       open_val,
            "high":       high_val,
            "low":        low_val,
            "close":      close_val,
            "volume":     total_vol,
            "date_start": dates[0],
            "date_end":   dates[-1],
            "bullish":    close_val >= open_val,
            "days":       counts,
        })

    return candles


def compute_moving_average(candles, period=4):
    """Compute simple moving average of close values."""
    closes = [c["close"] for c in candles]
    ma = []
    for i in range(len(closes)):
        if i < period - 1:
            ma.append(None)
        else:
            avg = sum(closes[i - period + 1 : i + 1]) / period
            ma.append(avg)
    return ma


# ═══════════════════════════════════════════════════════════════════════════
#  SVG RENDERING
# ═══════════════════════════════════════════════════════════════════════════

def _esc(s):
    """Escape text for XML."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def generate_svg(candles, username, total_contributions):
    """Generate a complete candlestick chart as SVG string."""

    if not candles:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="470">'
            '<rect width="900" height="470" fill="#0d1117" rx="12"/>'
            '<text x="450" y="235" fill="#c9d1d9" text-anchor="middle" '
            'font-family="monospace" font-size="16">No contribution data found</text>'
            '</svg>'
        )

    # ── Layout calculations ──────────────────────────────────────────────
    chart_left = MARGIN["left"]
    chart_right = WIDTH - MARGIN["right"]
    chart_top = MARGIN["top"]
    chart_bottom = HEIGHT - MARGIN["bottom"] - VOLUME_HEIGHT - VOLUME_GAP
    chart_width = chart_right - chart_left
    chart_height = chart_bottom - chart_top

    vol_top = chart_bottom + VOLUME_GAP
    vol_bottom = HEIGHT - MARGIN["bottom"]
    vol_height = vol_bottom - vol_top

    n = len(candles)
    candle_slot = chart_width / max(n, 1)
    candle_width = max(candle_slot * 0.55, 2)

    # ── Y-axis scale ─────────────────────────────────────────────────────
    all_highs = [c["high"] for c in candles]
    y_data_max = max(all_highs) if max(all_highs) > 0 else 10
    y_min = 0
    y_max = y_data_max * 1.15  # headroom

    max_vol = max(c["volume"] for c in candles)
    if max_vol == 0:
        max_vol = 1

    ma_values = compute_moving_average(candles, period=4)

    def y_pos(val):
        if y_max == y_min:
            return chart_top + chart_height / 2
        return chart_bottom - (val - y_min) / (y_max - y_min) * chart_height

    def vol_y(val):
        return vol_bottom - (val / max_vol) * vol_height

    def candle_x(i):
        return chart_left + i * candle_slot + candle_slot / 2

    # ── Compute stats ────────────────────────────────────────────────────
    first_close = candles[0]["close"]
    last_close = candles[-1]["close"]
    pct_change = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0.0
    avg_daily = total_contributions / max(n * 7, 1)
    best_day = max(max(c["days"]) for c in candles)
    bullish_weeks = sum(1 for c in candles if c["bullish"])
    bearish_weeks = n - bullish_weeks

    # Current bullish streak
    streak = 0
    for c in reversed(candles):
        if c["bullish"]:
            streak += 1
        else:
            break

    trend_color = COLORS["green_bright"] if pct_change >= 0 else COLORS["red_bright"]
    trend_arrow = "▲" if pct_change >= 0 else "▼"
    trend_sign = "+" if pct_change >= 0 else ""

    # ── Nice Y-axis tick values ──────────────────────────────────────────
    def nice_ticks(max_val, num_ticks=5):
        if max_val <= 0:
            return [0]
        raw_step = max_val / num_ticks
        magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
        nice_steps = [1, 2, 5, 10]
        step = magnitude
        for ns in nice_steps:
            if ns * magnitude >= raw_step:
                step = ns * magnitude
                break
        ticks = []
        val = 0
        while val <= max_val:
            ticks.append(int(val))
            val += step
        return ticks

    y_ticks = nice_ticks(y_max)

    # ═════════════════════════════════════════════════════════════════════
    #  BUILD SVG
    # ═════════════════════════════════════════════════════════════════════
    parts = []

    # ── <svg> root + defs ────────────────────────────────────────────────
    parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="2" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{COLORS['bg']}"/>
    <stop offset="100%" stop-color="{COLORS['bg_bottom']}"/>
  </linearGradient>
  <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{COLORS['green_bright']}"/>
    <stop offset="100%" stop-color="{COLORS['green']}"/>
  </linearGradient>
  <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{COLORS['red_bright']}"/>
    <stop offset="100%" stop-color="{COLORS['red']}"/>
  </linearGradient>
  <clipPath id="chartClip">
    <rect x="{chart_left}" y="{chart_top}" width="{chart_width}" height="{chart_height}"/>
  </clipPath>
</defs>''')

    # ── Background ───────────────────────────────────────────────────────
    parts.append(f'''
<!-- Background -->
<rect width="{WIDTH}" height="{HEIGHT}" rx="12" fill="url(#bgGrad)" stroke="{COLORS['border']}" stroke-width="1"/>''')

    # ── Title bar ────────────────────────────────────────────────────────
    parts.append(f'''
<!-- Title bar -->
<text x="{chart_left}" y="30" fill="{COLORS['text']}" font-family="'Segoe UI','SF Pro Display',system-ui,sans-serif" font-size="18" font-weight="700">{_esc(username.upper())}</text>
<text x="{chart_left}" y="50" fill="{trend_color}" font-family="'SF Mono','Cascadia Code',monospace" font-size="14" font-weight="600">{trend_arrow} {trend_sign}{pct_change:.1f}%</text>
<text x="{chart_left + 110}" y="50" fill="{COLORS['text_dim']}" font-family="'Segoe UI',system-ui,sans-serif" font-size="11">Contributions · {n} weeks · Total: {total_contributions:,}</text>
<text x="{chart_right}" y="30" fill="{COLORS['text_dim']}" font-family="'SF Mono',monospace" font-size="10" text-anchor="end">AVG/DAY: {avg_daily:.1f}  |  BEST: {best_day}  |  STREAK: {streak}W</text>
<text x="{chart_right}" y="46" fill="{COLORS['text_dim']}" font-family="'SF Mono',monospace" font-size="10" text-anchor="end">BULLISH: {bullish_weeks}W  |  BEARISH: {bearish_weeks}W</text>''')

    # ── Chart panel background ───────────────────────────────────────────
    parts.append(f'''
<!-- Chart panel -->
<rect x="{chart_left}" y="{chart_top}" width="{chart_width}" height="{chart_height}" rx="3" fill="{COLORS['panel']}" opacity="0.4"/>''')

    # ── Grid lines + Y-axis labels ───────────────────────────────────────
    parts.append('\n<!-- Grid + Y-axis -->')
    for tick in y_ticks:
        yp = y_pos(tick)
        if yp < chart_top or yp > chart_bottom:
            continue
        parts.append(
            f'<line x1="{chart_left}" y1="{yp:.1f}" x2="{chart_right}" y2="{yp:.1f}" '
            f'stroke="{COLORS["grid"]}" stroke-width="0.5" stroke-dasharray="4,3"/>'
        )
        parts.append(
            f'<text x="{chart_left - 8}" y="{yp + 3:.1f}" fill="{COLORS["text_dim"]}" '
            f'font-family="monospace" font-size="9" text-anchor="end">{tick}</text>'
        )

    # ── Volume bars ──────────────────────────────────────────────────────
    parts.append(f'\n<!-- Volume bars -->')
    parts.append(
        f'<text x="{chart_left}" y="{vol_top - 3}" fill="{COLORS["text_dim"]}" '
        f'font-family="monospace" font-size="8">VOL (weekly)</text>'
    )
    for i, candle in enumerate(candles):
        x = candle_x(i)
        vh = (candle["volume"] / max_vol) * vol_height
        color = COLORS["green_vol"] if candle["bullish"] else COLORS["red_vol"]
        parts.append(
            f'<rect x="{x - candle_width/2:.1f}" y="{vol_bottom - vh:.1f}" '
            f'width="{candle_width:.1f}" height="{vh:.1f}" fill="{color}" rx="1"/>'
        )

    # ── Candlesticks ─────────────────────────────────────────────────────
    parts.append(f'\n<!-- Candlesticks -->')
    for i, candle in enumerate(candles):
        x = candle_x(i)
        o, c = candle["open"], candle["close"]
        h, l = candle["high"], candle["low"]

        body_top_y = y_pos(max(o, c))
        body_bot_y = y_pos(min(o, c))
        body_h = max(body_bot_y - body_top_y, 1)  # min 1px visible

        wick_top_y = y_pos(h)
        wick_bot_y = y_pos(l)

        if candle["bullish"]:
            fill = "url(#greenGrad)"
            stroke = COLORS["green"]
        else:
            fill = "url(#redGrad)"
            stroke = COLORS["red"]

        # Wick line
        parts.append(
            f'<line x1="{x:.1f}" y1="{wick_top_y:.1f}" x2="{x:.1f}" y2="{wick_bot_y:.1f}" '
            f'stroke="{stroke}" stroke-width="1" stroke-linecap="round"/>'
        )
        # Candle body
        parts.append(
            f'<rect x="{x - candle_width/2:.1f}" y="{body_top_y:.1f}" '
            f'width="{candle_width:.1f}" height="{body_h:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="0.5" rx="1"/>'
        )

    # ── Moving average line ──────────────────────────────────────────────
    parts.append(f'\n<!-- SMA(4) Moving Average -->')
    ma_points = []
    for i, ma_val in enumerate(ma_values):
        if ma_val is not None:
            mx = candle_x(i)
            my = y_pos(ma_val)
            ma_points.append(f"{mx:.1f},{my:.1f}")

    if len(ma_points) >= 2:
        parts.append(
            f'<polyline points="{" ".join(ma_points)}" fill="none" '
            f'stroke="{COLORS["ma_line"]}" stroke-width="1.5" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="0.7" '
            f'clip-path="url(#chartClip)" filter="url(#glow)"/>'
        )
        parts.append(
            f'<text x="{chart_right}" y="{chart_top + 14}" fill="{COLORS["ma_line"]}" '
            f'font-family="monospace" font-size="9" text-anchor="end" opacity="0.8">'
            f'── SMA(4)</text>'
        )

    # ── X-axis month labels ──────────────────────────────────────────────
    parts.append(f'\n<!-- X-axis -->')
    last_month = None
    for i, candle in enumerate(candles):
        month = int(candle["date_start"].split("-")[1])
        if month != last_month:
            x = candle_x(i)
            parts.append(
                f'<text x="{x:.1f}" y="{HEIGHT - MARGIN["bottom"] + 18}" '
                f'fill="{COLORS["text_dim"]}" font-family="monospace" font-size="9" '
                f'text-anchor="middle">{MONTHS[month - 1]}</text>'
            )
            # Small tick mark
            parts.append(
                f'<line x1="{x:.1f}" y1="{vol_bottom}" x2="{x:.1f}" y2="{vol_bottom + 4}" '
                f'stroke="{COLORS["grid"]}" stroke-width="1"/>'
            )
            last_month = month

    # ── Decorative elements ──────────────────────────────────────────────
    # Horizontal separator lines
    parts.append(f'''
<!-- Separators -->
<line x1="{chart_left}" y1="{chart_top - 5}" x2="{chart_right}" y2="{chart_top - 5}" stroke="{COLORS['border']}" stroke-width="0.5"/>
<line x1="{chart_left}" y1="{chart_bottom}" x2="{chart_right}" y2="{chart_bottom}" stroke="{COLORS['border']}" stroke-width="0.5"/>''')

    # ── Footer ───────────────────────────────────────────────────────────
    now_str = datetime.now(tz=__import__('datetime').timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(f'''
<!-- Footer -->
<text x="{WIDTH / 2}" y="{HEIGHT - 10}" fill="{COLORS['text_dim']}" font-family="'Segoe UI',system-ui,sans-serif" font-size="9" text-anchor="middle" opacity="0.4">github-contributions-candlestick · updated {now_str}</text>''')

    # ── Close ────────────────────────────────────────────────────────────
    parts.append('\n</svg>')

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
#  DEMO DATA GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

def generate_demo_data():
    """Generate realistic-looking demo contribution data for testing."""
    import random
    random.seed(42)

    candles = []
    base = 4

    for week_idx in range(52):
        days = []
        for day in range(7):
            if day < 5:  # weekday — more active
                mu = base + 3
                count = max(0, int(random.gauss(mu, mu * 0.6)))
            else:  # weekend — less active
                mu = base * 0.4 + 1
                count = max(0, int(random.gauss(mu, mu * 0.8)))
            days.append(count)

        # Organic drift — slowly trend upward with seasonal dips
        seasonal = math.sin(week_idx / 52 * 2 * math.pi) * 1.5
        base = max(1, base + random.gauss(0.08, 0.8) + seasonal * 0.05)

        start_date = datetime(2025, 9, 1) + timedelta(weeks=week_idx)
        dates = [(start_date + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(7)]

        candles.append({
            "open":       days[0],
            "high":       max(days),
            "low":        min(days),
            "close":      days[-1],
            "volume":     sum(days),
            "date_start": dates[0],
            "date_end":   dates[-1],
            "bullish":    days[-1] >= days[0],
            "days":       days,
        })

    total = sum(c["volume"] for c in candles)
    return candles, total


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    # Fix Windows console encoding for Unicode output
    import io
    if sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    username    = os.environ.get("GITHUB_USERNAME", "")
    token       = os.environ.get("GITHUB_TOKEN", "")
    output_path = os.environ.get("OUTPUT_PATH", "assets/contributions-candlestick.svg")
    demo_mode   = os.environ.get("DEMO_MODE", "false").lower() == "true"

    print("╔══════════════════════════════════════════════════╗")
    print("║  📈 GitHub Contributions Candlestick Generator  ║")
    print("╚══════════════════════════════════════════════════╝\n")

    if demo_mode or not token:
        if not demo_mode:
            print("⚠  No GITHUB_TOKEN found — running in DEMO MODE")
            print("   Set GITHUB_TOKEN and GITHUB_USERNAME for real data.\n")
        else:
            print("🎭 Demo mode enabled — using sample data.\n")

        username = username or "trader-dev"
        candles, total = generate_demo_data()
    else:
        if not username:
            print("❌ GITHUB_USERNAME environment variable is required.")
            sys.exit(1)

        print(f"📡 Fetching contributions for @{username}...")
        calendar = fetch_contributions(username, token)
        total = calendar["totalContributions"]
        candles = contributions_to_ohlc(calendar)
        print(f"   ✓ {total:,} contributions across {len(candles)} weeks\n")

    print(f"🕯️  Rendering candlestick chart ({len(candles)} candles)...")
    svg = generate_svg(candles, username, total)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)

    file_size = os.path.getsize(output_path)
    print(f"   ✓ Saved to: {output_path}")
    print(f"   ✓ Dimensions: {WIDTH}×{HEIGHT}px")
    print(f"   ✓ File size: {file_size / 1024:.1f} KB")

    # Quick stats recap
    bullish = sum(1 for c in candles if c["bullish"])
    bearish = len(candles) - bullish
    print(f"\n📊 Stats: {total:,} contributions | "
          f"🟢 {bullish}W bullish | 🔴 {bearish}W bearish")
    print("✅ Done!\n")


if __name__ == "__main__":
    main()
