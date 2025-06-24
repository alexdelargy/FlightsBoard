from datetime import datetime
from itertools import cycle
import base64
import imghdr

import pandas as pd
import pytz
import requests
import main as st
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
from data import getFlightsFR24

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
EASTERN = pytz.timezone("US/Eastern")
REFRESH_INTERVAL_MS = 0.1 * 60 * 1000  # 1 minute
CSV_PATH = "SampleData.csv"  # replace with live API if desired
ICON_URL = (
    "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas/airplane.png"
)
LOGO_LOOKUP = "https://content.airhex.com/content/logos/airlines_%%_130_130_s.png"
    # add more airline logos here…

AIRPLANE_PNG = "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas/airplane.png"  # 128×128 transparent

st.set_page_config(page_title="Flights Overhead", page_icon="✈️", layout="centered")

# ─────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_flights() -> pd.DataFrame:
    """Return sample data (or swap in an API call)."""
    df = getFlightsFR24(miles=20)
    df["ETA"] = pd.to_datetime(df["ETA"], errors="coerce")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# AUTO‑REFRESH
count = st_autorefresh(interval=REFRESH_INTERVAL_MS, key="flight_cycle")

# SESSION STATE
if "df" not in st.session_state:
    st.session_state.df = fetch_flights()
    st.session_state.cycle = cycle(st.session_state.df.itertuples())
    st.session_state.index = 0

if st.session_state.index >= len(st.session_state.df):
    st.session_state.df = fetch_flights()
    st.session_state.cycle = cycle(st.session_state.df.itertuples())
    st.session_state.index = 0

# Only increment index when auto-refresh triggers (count > 0)
if count > 0:
    st.session_state.index = count

# Get the current flight
flight = list(st.session_state.df.itertuples())[st.session_state.index % len(st.session_state.df)]

# ─────────────────────────────────────────────────────────────────────────────
# STYLE — LED MATRIX VIBES ✨
# ─────────────────────────────────────────────────────────────────────────────
STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DotGothic16&display=swap');
body, .stApp {
    background: #181825 !important;
    zoom: 2;
}
.matrix-card {
    background:#000;
    border:4px solid #222;
    border-radius:20px;
    padding:2rem 2.5vw 2.5rem 2.5vw;
    box-shadow:0 8px 24px rgba(0,0,0,0.6);
    width:100vw;
    max-width:100vw;
    margin-left:calc(-50vw + 50%);
    margin-right:calc(-50vw + 50%);
}
.matrix-font {
    font-family:'DotGothic16', monospace;
    line-height:1.05;
    text-shadow:0 0 6px rgba(255,255,255,0.1),0 0 12px currentColor;
}
.route-row {
    font-size:4rem;font-weight:bold;letter-spacing:0.12em;color:#fffa72;
}
.route-arrow {color:#ff3b28;}
.airline-row {font-size:2.8rem;color:#38bdf8;}
.flightno-row {font-size:2.8rem;color:#38bdf8;}
.type-row {font-size:2.8rem;color:#a78bfa;}
.metrics-row {font-size:2.8rem;display:flex;gap:2.5rem;margin-top:1.8rem;}
.metrics-row span {text-shadow:0 0 6px rgba(255,255,255,0.1),0 0 12px currentColor;}
.mi {color:#f472b6;}
.ft {color:#38bdf8;}
.eta-label,.eta-time,.eta-ampm {color:#fbbf24;}
.logo-box {width:130px;height:130px;background:#111;border-radius:12px;display:flex;align-items:center;justify-content:center;}
.logo-box img {width:100%;object-fit:contain;border-radius:10px;}
</style>
"""

st.markdown(STYLES, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# LOGO HANDLING
# ─────────────────────────────────────────────────────────────────────────────
logo_url = LOGO_LOOKUP.replace("%%", flight.FlightNo[:2])
if not logo_url:
    logo_html = "✈️"
else:
    try:
        img_data = requests.get(logo_url, timeout=5).content
        # Assume all airline logos are PNGs now
        mime = "image/png"
        b64 = base64.b64encode(img_data).decode()
        logo_html = f'<img src="data:{mime};base64,{b64}">'  # Always PNG
    except Exception:
        logo_html = "✈️"

# ─────────────────────────────────────────────────────────────────────────────
# ETA FORMATTING
# ─────────────────────────────────────────────────────────────────────────────
if pd.notna(flight.ETA):
    eta_eastern = (
        flight.ETA.tz_localize("UTC").astimezone(EASTERN)
        if flight.ETA.tzinfo is None
        else flight.ETA.astimezone(EASTERN)
    )
    eta_hour = eta_eastern.strftime("%I:%M").lstrip("0")
    eta_ampm = eta_eastern.strftime("%p")
else:
    eta_hour, eta_ampm = "--", "--"

# ─────────────────────────────────────────────────────────────────────────────
# RENDER CARD
# ─────────────────────────────────────────────────────────────────────────────
card_html = f"""
<div style='display:flex; justify-content:center; width:100%;'>
  <div class='matrix-card matrix-font' style='width:900px; max-width:95vw; margin:0 auto;'>
     <div style='display:flex;gap:2rem;align-items:center;'>
        <div class='logo-box'>{logo_html}</div>
        <div style='flex:1;'>
            <div class='route-row matrix-font'>
               <span>{flight.Orig}</span>
               <span class='route-arrow'>&#9654;</span>
               <span>{flight.Dest}</span>
            </div>
            <div style='display:flex;gap:1rem;margin-top:1rem;'>
                <span class='flightno-row'>{flight.FlightNo}</span>
                <span class='type-row'>{flight.Type}</span>
            </div>
        </div>
     </div>
     <div class='metrics-row matrix-font'>
         <span class='ft'>{int(flight.Alt):,}ft</span>
         <span class='eta-time' style='white-space:nowrap;color:#fbbf24;'>ETA: {eta_hour} {eta_ampm}</span>
         <span class='mi'>{flight.Distance:.2f}mi</span>
     </div>
  </div>
</div>
"""

st.markdown(card_html, unsafe_allow_html=True)

