"""
File: function_app.py
Description:
    Azure Functions entry point for the Campsite Checker.
    Runs on a timer trigger every 15 minutes to poll campsite availability
    and send Discord notifications when new tent sites open up.

    Deploy with:
        func azure functionapp publish <YOUR_FUNCTION_APP_NAME>

    Required Azure app settings (set in Azure Portal -> Configuration):
        DISCORD_WEBHOOK_URL
        RECREATION_GOV_API_KEY
        AZURE_STORAGE_CONNECTION_STRING
        CHECK_DATE_START   (optional, e.g. 2026-06-01)
        CHECK_DATE_END     (optional, e.g. 2026-08-31)
        MAX_DISTANCE_MILES (optional, default 300)
"""

import azure.functions as func
import logging
import json

# Add src to path so react_agent package is importable
import sys, os
# Insert src/ so react_agent package is found, but import ONLY campsite_agent
# directly — avoids loading graph.py which pulls in alu_agent (needs TAVILY_API_KEY)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Temporarily stub out the __init__.py auto-import of graph so we don't
# trigger the full supervisor chain (and its Tavily dependency) at function startup
import importlib, types
# Create a lightweight react_agent namespace that won't auto-import graph.py
if "react_agent" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "react_agent",
        os.path.join(os.path.dirname(__file__), "src", "react_agent", "__init__.py"),
    )
    # Override __init__ to be empty so graph.py is never imported on startup
    mod = types.ModuleType("react_agent")
    mod.__path__ = [os.path.join(os.path.dirname(__file__), "src", "react_agent")]
    mod.__package__ = "react_agent"
    sys.modules["react_agent"] = mod

from react_agent.campsite_agent import run_campsite_check

app = func.FunctionApp()

@app.timer_trigger(
    schedule="0 */15 * * * *",   # every 15 minutes
    arg_name="myTimer",
    run_on_startup=True,          # run once immediately on deploy to verify config
    use_monitor=False,
)
def campsite_checker_timer(myTimer: func.TimerRequest) -> None:
    """Azure Timer Trigger — polls campsites every 15 minutes."""
    if myTimer.past_due:
        logging.warning("Timer is past due. Running check now anyway.")

    logging.info("Campsite checker triggered. Starting availability scan...")

    try:
        result = run_campsite_check(notify=True)
        logging.info(
            f"Check complete. "
            f"Checked {result['campsites_checked']} campgrounds. "
            f"{len(result['new_openings'])} with new openings. "
            f"Date range: {result['date_range']}."
        )
        if result["new_openings"]:
            for cg in result["new_openings"]:
                logging.info(
                    f"  NEW: {cg['campground']} ({cg['distance_miles']} mi) "
                    f"— dates: {', '.join(cg['new_dates'][:5])}"
                )
        else:
            logging.info("  No new openings since last check.")
    except Exception as e:
        logging.error(f"Campsite checker failed: {e}", exc_info=True)
