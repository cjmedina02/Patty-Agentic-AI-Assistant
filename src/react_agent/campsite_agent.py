"""
File: campsite_agent.py
Description:
    Campsite availability checker. Polls Recreation.gov and ReserveCalifornia
    for tent site openings across Southern California and beyond, then sends
    Discord notifications — with weekends highlighted — when new dates open up.

    Supported platforms:
      * Recreation.gov   — national parks and forests (official RIDB API)
      * ReserveCalifornia — CA state parks (Tyler/RDR API)

    Environment variables:
      DISCORD_WEBHOOK_URL             - Discord channel webhook URL
      MAX_DISTANCE_MILES              - radius filter from 92126 (default: 300)
      RECREATION_GOV_API_KEY          - free key from ridb.recreation.gov/profile
      AZURE_STORAGE_CONNECTION_STRING - from Azure portal
      CHECK_DATE_START                - e.g. 2026-06-01
      CHECK_DATE_END                  - e.g. 2026-08-31
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from typing import Annotated, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

load_dotenv()
log = logging.getLogger("campsite_checker")

# ============================================================
# CONFIGURATION
# ============================================================

MAX_DISTANCE_MILES = int(os.getenv("MAX_DISTANCE_MILES", "300"))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
RECREATION_GOV_API_KEY = os.getenv("RECREATION_GOV_API_KEY", "")
CHECK_DATE_START = os.getenv("CHECK_DATE_START", "")
CHECK_DATE_END = os.getenv("CHECK_DATE_END", "")
STATE_FILE = os.getenv("CAMPSITE_STATE_FILE", "campsite_state.json")

# Home base: Mira Mesa, San Diego CA (92126)
HOME_LAT = 32.9153
HOME_LON = -117.1317

WEEKEND_DAYS = {4, 5, 6}  # Friday=4, Saturday=5, Sunday=6

# ============================================================
# WATCHED CAMPGROUNDS
# ============================================================

WATCHED_CAMPGROUNDS: list[dict[str, Any]] = [
    # ── California State Parks (ReserveCalifornia) ───────────────────────────
    {
        "name": "Doheny State Beach",
        "facility_id": "717",
        "place_id": 639,
        "source": "reservecalifornia",
        "lat": 33.4614,
        "lon": -117.6843,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/717",
    },
    {
        "name": "South Carlsbad State Beach",
        "facility_id": "720",
        "place_id": 720,
        "source": "reservecalifornia",
        "lat": 33.1100,
        "lon": -117.3200,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/720",
    },
    {
        "name": "San Elijo State Beach",
        "facility_id": "721",
        "place_id": 709,
        "source": "reservecalifornia",
        "lat": 33.0175,
        "lon": -117.2820,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/721",
    },
    {
        "name": "Crystal Cove State Park",
        "facility_id": "723",
        "place_id": 635,
        "source": "reservecalifornia",
        "lat": 33.5672,
        "lon": -117.8373,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/723",
    },
    {
        "name": "Palomar Mountain SP",
        "facility_id": "714",
        "place_id": 687,
        "source": "reservecalifornia",
        "lat": 33.3428,
        "lon": -116.9117,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/714",
    },
    {
        "name": "Idyllwild / Mt San Jacinto SP",
        "facility_id": "712",
        "place_id": -1,  # coord-based search (PlaceId=0 on site)
        "place_lat": 33.7631,
        "place_lon": -116.7364,
        "source": "reservecalifornia",
        "lat": 33.7406,
        "lon": -116.7155,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/712",
    },
    {
        "name": "Anza-Borrego Desert SP",
        "facility_id": "639",
        "place_id": 2,
        "source": "reservecalifornia",
        "lat": 33.2581,
        "lon": -116.4108,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/639",
    },
    {
        "name": "Leo Carrillo State Beach",
        "facility_id": "610",
        "place_id": 665,
        "source": "reservecalifornia",
        "lat": 34.0453,
        "lon": -118.9343,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/610",
    },
    {
        "name": "D.L. Bliss SP (Lake Tahoe)",
        "facility_id": "680",
        "place_id": 637,
        "source": "reservecalifornia",
        "lat": 38.9699,
        "lon": -120.1063,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/680",
    },
    {
        "name": "Emerald Bay SP (Lake Tahoe)",
        "facility_id": "679",
        "place_id": 641,
        "source": "reservecalifornia",
        "lat": 38.9527,
        "lon": -120.1049,
        "url": "https://www.reservecalifornia.com/Web/Default.aspx#!park/679",
    },
    # ── National Parks & Forests (Recreation.gov) ────────────────────────────
    {
        "name": "Fern Basin CG (Idyllwild, San Bernardino NF)",
        "facility_id": "231969",
        "source": "recreation.gov",
        "lat": 33.7800,
        "lon": -116.6900,
        "url": "https://www.recreation.gov/camping/campgrounds/231969",
    },
    {
        "name": "Marion Mountain CG (Idyllwild, San Bernardino NF)",
        "facility_id": "231973",
        "source": "recreation.gov",
        "lat": 33.7850,
        "lon": -116.6950,
        "url": "https://www.recreation.gov/camping/campgrounds/231973",
    },
    {
        "name": "Serrano CG (Big Bear, San Bernardino NF)",
        "facility_id": "232250",
        "source": "recreation.gov",
        "lat": 34.2440,
        "lon": -116.8860,
        "url": "https://www.recreation.gov/camping/campgrounds/232250",
    },
    {
        "name": "Black Rock CG (Joshua Tree NP)",
        "facility_id": "232473",
        "source": "recreation.gov",
        "lat": 34.0778,
        "lon": -116.3878,
        "url": "https://www.recreation.gov/camping/campgrounds/232473",
    },
    {
        "name": "Indian Cove CG (Joshua Tree NP)",
        "facility_id": "232472",
        "source": "recreation.gov",
        "lat": 34.0920,
        "lon": -116.1590,
        "url": "https://www.recreation.gov/camping/campgrounds/232472",
    },
    {
        "name": "Jumbo Rocks CG (Joshua Tree NP)",
        "facility_id": "272300",
        "source": "recreation.gov",
        "lat": 34.0270,
        "lon": -116.0590,
        "url": "https://www.recreation.gov/camping/campgrounds/272300",
    },
    {
        "name": "Cottonwood CG (Joshua Tree NP)",
        "facility_id": "272299",
        "source": "recreation.gov",
        "lat": 33.7410,
        "lon": -115.8170,
        "url": "https://www.recreation.gov/camping/campgrounds/272299",
    },
    {
        "name": "Upper Pines CG (Yosemite NP)",
        "facility_id": "232447",
        "source": "recreation.gov",
        "lat": 37.7384,
        "lon": -119.5578,
        "url": "https://www.recreation.gov/camping/campgrounds/232447",
    },
    {
        "name": "Lower Pines CG (Yosemite NP)",
        "facility_id": "232450",
        "source": "recreation.gov",
        "lat": 37.7384,
        "lon": -119.5522,
        "url": "https://www.recreation.gov/camping/campgrounds/232450",
    },
    {
        "name": "North Pines CG (Yosemite NP)",
        "facility_id": "232449",
        "source": "recreation.gov",
        "lat": 37.7408,
        "lon": -119.5486,
        "url": "https://www.recreation.gov/camping/campgrounds/232449",
    },
    {
        "name": "Lodgepole CG (Sequoia NP)",
        "facility_id": "232461",
        "source": "recreation.gov",
        "lat": 36.5916,
        "lon": -118.7283,
        "url": "https://www.recreation.gov/camping/campgrounds/232461",
    },
    {
        "name": "Dorst Creek CG (Sequoia NP)",
        "facility_id": "232460",
        "source": "recreation.gov",
        "lat": 36.6580,
        "lon": -118.7720,
        "url": "https://www.recreation.gov/camping/campgrounds/232460",
    },
    {
        "name": "Potwisha CG (Sequoia NP)",
        "facility_id": "249979",
        "source": "recreation.gov",
        "lat": 36.4960,
        "lon": -118.8330,
        "url": "https://www.recreation.gov/camping/campgrounds/249979",
    },
]

# ============================================================
# HTTP SESSION
# ============================================================

def _make_session() -> requests.Session:
    """Build a requests Session with retries and browser-like headers."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return session

# ============================================================
# HELPERS
# ============================================================

def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _within_range(cg: dict) -> bool:
    return _haversine_miles(HOME_LAT, HOME_LON, cg["lat"], cg["lon"]) <= MAX_DISTANCE_MILES


def _is_weekend(date_str: str) -> bool:
    """Return True if date falls on Friday, Saturday, or Sunday."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").weekday() in WEEKEND_DAYS
    except ValueError:
        return False


def _sort_dates_weekend_first(dates: list[str]) -> list[str]:
    """Sort dates with weekends first, then weekdays."""
    return sorted(dates, key=lambda d: (0 if _is_weekend(d) else 1, d))

# ============================================================
# STATE PERSISTENCE
# ============================================================

def _load_state() -> dict:
    az_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if az_conn:
        try:
            from azure.data.tables import TableServiceClient
            svc = TableServiceClient.from_connection_string(az_conn)
            table = svc.get_table_client("CampsiteState")
            state = {}
            for entity in table.list_entities():
                state[entity["RowKey"]] = json.loads(entity.get("AvailabilityJson", "[]"))
            return state
        except Exception as e:
            log.warning(f"Azure Table read failed, using local fallback: {e}")
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict) -> None:
    az_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if az_conn:
        try:
            from azure.data.tables import TableServiceClient
            svc = TableServiceClient.from_connection_string(az_conn)
            table = svc.get_table_client("CampsiteState")
            try:
                table.create_table()
            except Exception:
                pass
            for key, dates in state.items():
                table.upsert_entity({
                    "PartitionKey": "campsite",
                    "RowKey": key,
                    "AvailabilityJson": json.dumps(dates),
                })
            return
        except Exception as e:
            log.warning(f"Azure Table write failed, using local fallback: {e}")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ============================================================
# RECREATION.GOV API
# ============================================================

def _recgov_check(
    session: requests.Session, facility_id: str, start: str, end: str
) -> tuple[list[str], list[dict]]:
    """
    Query Recreation.gov availability API.
    Returns (available_dates, site_details) where site_details includes
    site name, loop, and price per night.
    """
    if not RECREATION_GOV_API_KEY:
        log.warning("RECREATION_GOV_API_KEY not set — skipping Recreation.gov query")
        return [], []

    url = f"https://www.recreation.gov/api/camps/availability/campground/{facility_id}/month"
    headers = {"apikey": RECREATION_GOV_API_KEY}
    available: set[str] = set()
    site_info: dict[str, dict] = {}  # date -> {site, loop, price}

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    current = start_dt.replace(day=1)

    while current <= end_dt:
        params = {"start_date": current.strftime("%Y-%m-01T00:00:00.000Z")}
        try:
            resp = session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for site_id, site_data in (data.get("campsites") or {}).items():
                site_type = (site_data.get("campsite_type") or "").lower()
                if any(x in site_type for x in ["rv", "hookup", "electric", "cabin", "group"]):
                    continue
                site_name = site_data.get("site") or site_id
                loop = site_data.get("loop") or ""
                price = site_data.get("min_num_people_per_reservation") or 0
                for date_str, status in (site_data.get("availabilities") or {}).items():
                    if status == "Available":
                        date = date_str[:10]
                        if start <= date <= end:
                            available.add(date)
                            # Keep the first site info found per date
                            if date not in site_info:
                                site_info[date] = {
                                    "site": site_name,
                                    "loop": loop,
                                }
        except Exception as e:
            log.error(f"Recreation.gov error for {facility_id}: {e}")

        current = current.replace(
            month=current.month % 12 + 1,
            year=current.year + (1 if current.month == 12 else 0),
        )

    sorted_dates = sorted(available)
    details = [
        {"date": d, **site_info.get(d, {}), "is_weekend": _is_weekend(d)}
        for d in sorted_dates
    ]
    return sorted_dates, details

# ============================================================
# RESERVE CALIFORNIA API
# ============================================================

RESERVECA_BASE = "https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com"


def _reserveca_check(
    session: requests.Session,
    facility_id: str,
    place_id: int,
    start: str,
    end: str,
    place_lat: float = 0.0,
    place_lon: float = 0.0,
) -> tuple[list[str], list[dict]]:
    """
    Query ReserveCalifornia availability via the Tyler/RDR API.
    Returns (available_dates, site_details).

    API base: california-rdr.prod.cali.rd12.recreation-management.tylerapp.com
    place_id=-1 means coordinate-based search (site returns PlaceId=0).
    """
    available: set[str] = set()
    site_info: dict[str, dict] = {}

    session.headers.update({
        "Origin": "https://www.reservecalifornia.com",
        "Referer": "https://www.reservecalifornia.com/",
        "Content-Type": "application/json",
    })

    # Warm-up GET to establish session cookies
    try:
        session.get(
            f"{RESERVECA_BASE}/rdr/fd/citypark/namecontains/California",
            timeout=10,
        )
    except Exception:
        pass

    url = f"{RESERVECA_BASE}/rdr/search/place"
    resolved_place_id = 0 if place_id == -1 else place_id
    payload = {
        "PlaceId": resolved_place_id,
        "Latitude": place_lat,
        "Longitude": place_lon,
        "Nights": 1,
        "CustomerId": 0,
        "StartDate": start,
        "UnitCategoryId": 0,
        "SleepingUnitId": 0,
        "MinVehicleLength": 0,
        "UnitTypesGroupIds": [],
        "AmenityIds": [],
        "Sort": "distance",
        "IsADA": False,
        "RestrictADA": False,
        "NearbyLimit": 100,
        "isSearchAllParks": False,
        "customerClassificationId": 1,
        "InSeasonOnly": True,
        "WebOnly": True,
        "NearbyCountLimit": 10,
        "NearbyOnlyAvailable": False,
        "CountNearby": True,
        "CountUnits": True,
        "HighlightedPlaceId": 0,
    }
    try:
        resp = session.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        log.info(f"ReserveCA {facility_id}: HTTP {resp.status_code}, {len(resp.content)} bytes")
        if not resp.content:
            log.warning(f"ReserveCA returned empty body for {facility_id}")
            return [], []
        data = resp.json()
        facilities = data.get("Facilities") or []
        for fac in facilities:
            for unit in (fac.get("Units") or []):
                unit_name = (unit.get("Name") or "").lower()
                unit_type = (unit.get("UnitTypeName") or "").lower()
                if any(x in unit_name or x in unit_type
                       for x in ["rv", "hookup", "electric", "cabin", "group", "yurt"]):
                    continue
                display_name = unit.get("Name") or unit.get("UnitId") or "?"
                for slot in (unit.get("Slices") or []):
                    date_str = (slot.get("Date") or slot.get("StartDate") or "")[:10]
                    is_free = slot.get("IsFree") or slot.get("IsAvailable") or False
                    is_blocked = slot.get("IsBlocked") or False
                    if date_str and is_free and not is_blocked and start <= date_str <= end:
                        available.add(date_str)
                        if date_str not in site_info:
                            site_info[date_str] = {"site": display_name}
    except Exception as e:
        log.error(f"ReserveCA error for {facility_id}: {e}")

    sorted_dates = sorted(available)
    details = [
        {"date": d, **site_info.get(d, {}), "is_weekend": _is_weekend(d)}
        for d in sorted_dates
    ]
    return sorted_dates, details

# ============================================================
# DISCORD NOTIFIER
# ============================================================

def _send_discord(message: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set — notification skipped")
        return False
    try:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message, "username": "Campsite Watcher 🏕️"},
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Discord notification sent.")
        return True
    except Exception as e:
        log.error(f"Discord webhook failed: {e}")
        return False


def _format_discord_message(cg: dict, dist: int, new_dates: list[str], details: list[dict], booking_url: str) -> str:
    """
    Format a Discord notification message.
    Weekends are listed first and flagged with 🏖️.
    Site numbers included when available.
    """
    sorted_new = _sort_dates_weekend_first(new_dates)

    lines = []
    for d in sorted_new[:8]:
        detail = next((x for x in details if x.get("date") == d), {})
        site = detail.get("site", "")
        is_wknd = detail.get("is_weekend") or _is_weekend(d)
        flag = "🏖️ WEEKEND" if is_wknd else "📅 Weekday"
        site_str = f" — Site {site}" if site else ""
        lines.append(f"{flag} {d}{site_str}")

    if len(sorted_new) > 8:
        lines.append(f"...and {len(sorted_new) - 8} more dates")

    dates_block = "\n".join(lines)
    return (
        f"@everyone\n"
        f"🏕️ **New campsite opening!**\n"
        f"**{cg['name']}** — {dist} mi from San Diego\n"
        f"{dates_block}\n"
        f"🔗 Book now: {booking_url}"
    )

# ============================================================
# CORE CHECK LOGIC
# ============================================================

def run_campsite_check(
    date_start: str = "",
    date_end: str = "",
    notify: bool = True,
) -> dict[str, Any]:
    """
    Main entry point. Checks all watched campgrounds, compares against
    stored state, and fires Discord notifications for new openings.
    Weekends (Fri–Sun) are prioritized in notifications.
    """
    start = date_start or CHECK_DATE_START
    end = date_end or CHECK_DATE_END
    if not start or not end:
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    log.info(f"Checking campsites {start} → {end}")

    session = _make_session()
    prior_state = _load_state()
    new_state: dict[str, list] = {}
    new_openings: list[dict] = []
    all_available: list[dict] = []

    for cg in WATCHED_CAMPGROUNDS:
        dist = _haversine_miles(HOME_LAT, HOME_LON, cg["lat"], cg["lon"])
        if dist > MAX_DISTANCE_MILES:
            log.info(f"Skipping {cg['name']} ({dist:.0f} mi — out of range)")
            continue

        log.info(f"Checking {cg['name']} ({dist:.0f} mi) via {cg['source']}…")
        source = cg["source"]
        fid = cg["facility_id"]

        if source == "recreation.gov":
            available_dates, details = _recgov_check(session, fid, start, end)
        else:
            pid = cg.get("place_id", 0)
            if pid == 0:
                log.warning(f"Skipping {cg['name']} — place_id not configured")
                continue
            available_dates, details = _reserveca_check(
                session, fid, pid, start, end,
                place_lat=cg.get("place_lat", 0.0),
                place_lon=cg.get("place_lon", 0.0),
            )

        state_key = f"{fid}_{source}"
        prev_dates = set(prior_state.get(state_key, []))
        curr_dates = set(available_dates)
        new_dates = sorted(curr_dates - prev_dates)
        new_state[state_key] = sorted(curr_dates)

        if available_dates:
            weekend_dates = [d for d in available_dates if _is_weekend(d)]
            all_available.append({
                "campground": cg["name"],
                "source": source,
                "distance_miles": round(dist),
                "available_dates": _sort_dates_weekend_first(available_dates)[:10],
                "weekend_dates": weekend_dates[:5],
                "total_slots": len(available_dates),
            })

        if new_dates:
            entry = {
                "campground": cg["name"],
                "source": source,
                "distance_miles": round(dist),
                "new_dates": new_dates,
                "new_weekend_dates": [d for d in new_dates if _is_weekend(d)],
                "booking_url": cg["url"],
            }
            new_openings.append(entry)

            if notify:
                msg = _format_discord_message(cg, round(dist), new_dates, details, cg["url"])
                _send_discord(msg)

        time.sleep(1.0)

    _save_state(new_state)
    log.info(f"Check complete. {len(new_openings)} campground(s) with new openings.")
    return {
        "new_openings": new_openings,
        "all_available": all_available,
        "date_range": f"{start} to {end}",
        "campsites_checked": sum(1 for c in WATCHED_CAMPGROUNDS if _within_range(c)),
    }

# ============================================================
# LANGGRAPH TOOLS
# ============================================================

@tool
def check_campsites(date_start: str = "", date_end: str = "") -> str:
    """
    Check all watched campgrounds for available tent sites.
    Optionally provide date_start and date_end as YYYY-MM-DD strings.
    Weekends (Fri–Sun) are highlighted. Sends Discord notifications for new openings.
    """
    result = run_campsite_check(date_start=date_start, date_end=date_end, notify=True)

    if not result["all_available"]:
        return (
            f"No tent site availability found across {result['campsites_checked']} "
            f"watched campgrounds for {result['date_range']}."
        )

    lines = [f"Campsite availability ({result['date_range']}):"]
    for cg in result["all_available"]:
        weekend_str = f" | 🏖️ Weekends: {', '.join(cg['weekend_dates'])}" if cg["weekend_dates"] else ""
        dates = ", ".join(cg["available_dates"])
        lines.append(
            f"• {cg['campground']} ({cg['distance_miles']} mi) — "
            f"{cg['total_slots']} slot(s). Next: {dates}{weekend_str}"
        )
    if result["new_openings"]:
        lines.append(f"\n🆕 {len(result['new_openings'])} campground(s) with NEW openings — Discord notified!")
    return "\n".join(lines)


@tool
def list_watched_campgrounds() -> str:
    """List all campgrounds being monitored with distance and booking platform."""
    lines = ["Watched campgrounds (from zip 92126):"]
    for cg in WATCHED_CAMPGROUNDS:
        dist = _haversine_miles(HOME_LAT, HOME_LON, cg["lat"], cg["lon"])
        status = "✅" if dist <= MAX_DISTANCE_MILES else "⚠️ out of range"
        lines.append(f"• {cg['name']} — {dist:.0f} mi — {cg['source']} — {status}")
    return "\n".join(lines)


@tool
def add_campground(name: str, facility_id: str, source: str, lat: float, lon: float, url: str = "") -> str:
    """
    Add a new campground to the watch list at runtime.
    source must be 'reservecalifornia' or 'recreation.gov'.
    """
    WATCHED_CAMPGROUNDS.append({
        "name": name,
        "facility_id": facility_id,
        "source": source,
        "lat": lat,
        "lon": lon,
        "url": url or f"https://www.recreation.gov/camping/campgrounds/{facility_id}",
    })
    dist = _haversine_miles(HOME_LAT, HOME_LON, lat, lon)
    return f"Added '{name}' ({dist:.0f} mi, {source}) to the watch list."

# ============================================================
# AGENT
# ============================================================

SYSTEM_PROMPT = """
You are the Campsite Checker Agent. You monitor campsite availability across
Recreation.gov and ReserveCalifornia, and alert via Discord when new tent sites
open up — with weekends (Fri–Sun) prioritized.

Tools:
- check_campsites(date_start, date_end) — query all watched campgrounds
- list_watched_campgrounds() — show the watch list with distances
- add_campground(name, facility_id, source, lat, lon, url) — add a new campground
"""


class State(TypedDict):
    messages: Annotated[list[BaseMessage], lambda x, y: x + y]


def initialize_campsite_agent() -> StateGraph:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    tools = [check_campsites, list_watched_campgrounds, add_campground]
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools=tools)

    def agent_node(state: State) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        return {"messages": [llm_with_tools.invoke(messages)]}

    def route(state: State) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route, ["tools", END])
    builder.add_edge("tools", "agent")
    return builder.compile()


graph = initialize_campsite_agent()
