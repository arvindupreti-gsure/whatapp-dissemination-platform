# -*- coding: utf-8 -*-
"""Runtime configuration for the dissemination platform proof of concept."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MEDIA_DIR = DATA_DIR / "media"
DATA_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "wdap.sqlite3"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

HOST = os.environ.get("WDAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("WDAP_PORT", "8000"))
PUBLIC_BASE_URL = os.environ.get("WDAP_PUBLIC_URL", f"http://{HOST}:{PORT}")

# Channel adapter: simulator | cloud_api | linked_device
DEFAULT_CHANNEL = os.environ.get("WDAP_CHANNEL", "simulator")

# --- Rate governance -------------------------------------------------------
# Section 5.3 of the proposal: configurable send rate, randomised intervals,
# daily ceiling and a staged warm-up profile.
SEND_RATE_PER_SEC = float(os.environ.get("WDAP_SEND_RATE", "25"))
SEND_JITTER_PCT = float(os.environ.get("WDAP_SEND_JITTER", "0.35"))
WORKER_COUNT = int(os.environ.get("WDAP_WORKERS", "8"))
DAILY_CEILING = int(os.environ.get("WDAP_DAILY_CEILING", "200000"))
MAX_ATTEMPTS = int(os.environ.get("WDAP_MAX_ATTEMPTS", "3"))
RETRY_BACKOFF_SEC = float(os.environ.get("WDAP_RETRY_BACKOFF", "2"))

# --- Interval reporting ----------------------------------------------------
# The Scope of Work asks for 15 min, 1 hr, 3 hr and 8 hr snapshots. Real
# intervals make a demonstration impossible to observe, so TIME_SCALE
# compresses them. 1.0 is production semantics; 0.01 turns 15 minutes into
# 9 seconds. The labels never change, only the wall-clock spacing.
SNAPSHOT_INTERVALS = [
    ("15m", 15 * 60),
    ("1h", 60 * 60),
    ("3h", 3 * 60 * 60),
    ("8h", 8 * 60 * 60),
]
TIME_SCALE = float(os.environ.get("WDAP_TIME_SCALE", "0.01"))

# --- Simulator behaviour ---------------------------------------------------
# Models the outcome distribution the Week 1 proof of concept would measure
# for real. Every number here is an assumption, not an observation.
SIM_FAILURE_RATE = float(os.environ.get("WDAP_SIM_FAILURE", "0.031"))
SIM_TRANSIENT_SHARE = float(os.environ.get("WDAP_SIM_TRANSIENT", "0.55"))
SIM_DELIVER_MS = (120, 900)
SIM_READ_PROBABILITY = float(os.environ.get("WDAP_SIM_READ", "0.72"))
SIM_CLICK_OF_READ = float(os.environ.get("WDAP_SIM_CLICK", "0.18"))
SIM_REPLY_OF_READ = float(os.environ.get("WDAP_SIM_REPLY", "0.04"))
SIM_OPTOUT_OF_READ = float(os.environ.get("WDAP_SIM_OPTOUT", "0.006"))

# --- Official WhatsApp Cloud API (real calls when configured) --------------
CLOUD_API_VERSION = os.environ.get("WDAP_GRAPH_VERSION", "v21.0")
CLOUD_API_BASE = f"https://graph.facebook.com/{CLOUD_API_VERSION}"
CLOUD_PHONE_NUMBER_ID = os.environ.get("WDAP_PHONE_NUMBER_ID", "")
CLOUD_WABA_ID = os.environ.get("WDAP_WABA_ID", "")
CLOUD_ACCESS_TOKEN = os.environ.get("WDAP_ACCESS_TOKEN", "")
CLOUD_VERIFY_TOKEN = os.environ.get("WDAP_VERIFY_TOKEN", "wdap-poc-verify")

# --- Linked device bridge (Node + Baileys) ---------------------------------
BRIDGE_URL = os.environ.get("WDAP_BRIDGE_URL", "http://127.0.0.1:8787")
BRIDGE_TOKEN = os.environ.get("WDAP_BRIDGE_TOKEN", "wdap-local-bridge")

# --- Security --------------------------------------------------------------
SESSION_TTL_HOURS = int(os.environ.get("WDAP_SESSION_TTL", "12"))
# Key for field level encryption of channel credentials at rest.
SECRET_KEY = os.environ.get("WDAP_SECRET_KEY", "")

ROLES = ["SUPER_ADMIN", "CAMPAIGN_MANAGER", "ANALYST", "VIEWER"]

# Permission matrix. Every API route declares a permission and the matrix
# decides, so role behaviour is auditable in one place.
PERMISSIONS = {
    "SUPER_ADMIN": {
        "group.read", "group.write", "campaign.read", "campaign.write",
        "campaign.execute", "analytics.read", "report.export", "user.read",
        "user.write", "settings.write", "audit.read", "template.write",
    },
    "CAMPAIGN_MANAGER": {
        "group.read", "group.write", "campaign.read", "campaign.write",
        "campaign.execute", "analytics.read", "report.export", "template.write",
    },
    "ANALYST": {
        "group.read", "campaign.read", "analytics.read", "report.export",
    },
    "VIEWER": {
        "group.read", "campaign.read", "analytics.read",
    },
}


def scaled(seconds: float) -> float:
    """Apply the demonstration time compression to an interval."""
    return seconds * TIME_SCALE
