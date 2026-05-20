# Campsite Availability Checker

Automatically monitors campsite availability across Southern California and beyond. Polls booking platforms every 15 minutes and sends Discord notifications when new tent sites open up — with weekends (Fri–Sun) highlighted and prioritized.

Deployed as an Azure Functions timer trigger with persistent state via Azure Table Storage.

---

## Features

- Monitors 23 campgrounds across Recreation.gov and ReserveCalifornia
- Filters to tent/standard sites only (excludes RV, hookup, electric, cabin, group, yurt)
- Detects new openings by diffing current availability against last known state
- Prioritizes weekend dates (Friday–Sunday) in notifications
- Shows site numbers when available
- `@everyone` Discord ping on new openings
- Runs continuously on Azure — no need to keep your computer on

---

## APIs Used

### Recreation.gov RIDB API
- **Endpoint:** `https://www.recreation.gov/api/camps/availability/campground/{facility_id}/month`
- **Auth:** Free API key from [ridb.recreation.gov/profile](https://ridb.recreation.gov/profile)
- **Used for:** National parks and forests — Joshua Tree, Yosemite, Sequoia, Big Bear, Idyllwild

### ReserveCalifornia Tyler/RDR API
- **Endpoint:** `https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com/rdr/search/place`
- **Auth:** None required (public API used by reservecalifornia.com)
- **Used for:** California state parks — Doheny, Carlsbad, Palomar, Anza-Borrego, Lake Tahoe, and more

### Discord Webhooks
- **Docs:** [discord.com/developers/docs/resources/webhook](https://discord.com/developers/docs/resources/webhook)
- **Used for:** Sending campsite availability notifications with `@everyone` to a Discord channel

### Azure Functions (Timer Trigger)
- Runs the availability check on a 15-minute cron schedule (`0 */15 * * * *`)
- Flex Consumption plan — Linux, Python 3.13

### Azure Table Storage
- Stores last-known availability state per campground across invocations
- Enables diff-based new-opening detection

---

## Watched Campgrounds

See [WATCHED_CAMPGROUNDS.md](WATCHED_CAMPGROUNDS.md) for the full list with distances, PlaceIds, and facility IDs.

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd campsite_agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.campsite.example .env
```

Fill in your values:

| Variable | Description |
|---|---|
| `DISCORD_WEBHOOK_URL` | Your Discord channel webhook URL |
| `RECREATION_GOV_API_KEY` | Free key from ridb.recreation.gov/profile |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Portal → Storage Account → Access keys |
| `CHECK_DATE_START` | Start of search window, e.g. `2026-06-01` |
| `CHECK_DATE_END` | End of search window, e.g. `2026-08-31` |
| `MAX_DISTANCE_MILES` | Max distance from 92126 (default: `300`) |

### 4. Run locally

```bash
cd src
python -c "from react_agent.campsite_agent import run_campsite_check; run_campsite_check(notify=False)"
```

### 5. Deploy to Azure

With the Azure Functions VS Code extension:

```
Ctrl+Shift+P → Azure Functions: Deploy to Function App
```

Set the same environment variables in **Azure Portal → Function App → Configuration → Application settings**.

---

## Adding Campgrounds

Edit `WATCHED_CAMPGROUNDS` in `src/react_agent/campsite_agent.py`.

**Recreation.gov:** Use the facility ID from the URL — `recreation.gov/camping/campgrounds/{id}`

**ReserveCalifornia:** Find the `PlaceId` by opening DevTools (F12) on `reservecalifornia.com`, searching a park, and inspecting the `place` POST request payload in the Network tab.

---

## Project Structure

```
campsite_agent/
├── function_app.py             # Azure Functions timer trigger entry point
├── host.json                   # Azure Functions host config
├── requirements.txt            # Python dependencies
├── WATCHED_CAMPGROUNDS.md      # Full list of monitored campgrounds
└── src/
    └── react_agent/
        └── campsite_agent.py   # Core checker, API clients, Discord notifier
```
