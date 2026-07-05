# --- Broker / data connectivity ---
# Windows-only wheel. The marker means pip SKIPS this line automatically on
# Linux (GitHub Actions' ubuntu-latest runner) and only installs it on a real
# Windows VPS - so one requirements.txt file works for both deployment paths.
MetaTrader5>=5.0.45; sys_platform == "win32"

# --- Data & numerical ---
pandas>=2.2.2
numpy>=1.26.4
scipy>=1.13.1              # Monte Carlo simulation + statistical tests (Module 7)

# --- Telegram delivery ---
requests>=2.32.3           # Raw Bot API calls - no heavy wrapper dependency needed

# --- Scheduling / orchestration ---
schedule>=1.2.2            # Module 8: live polling loop

# --- Config / environment ---
python-dotenv>=1.0.1

# Note: sqlite3 (Module 9 - performance tracking / signal journal) is stdlib,
# no separate install required.
