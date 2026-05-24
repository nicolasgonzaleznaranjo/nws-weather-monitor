import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup

st.set_page_config(page_title="NWS Weather Monitor", layout="wide")

# -----------------------------
# Basic config
# -----------------------------
NWS_HEADERS = {
    "User-Agent": "nws-weather-monitor/1.0 (personal weather monitor)",
    "Accept": "application/geo+json, application/json",
}

CITIES = {
    "Atlanta": {"lat": 33.6407, "lon": -84.4277, "station": "KATL", "tz": "America/New_York", "regime": "humid"},
    "Austin": {"lat": 30.1945, "lon": -97.6699, "station": "KAUS", "tz": "America/Chicago", "regime": "humid"},
    "Boston": {"lat": 42.3656, "lon": -71.0096, "station": "KBOS", "tz": "America/New_York", "regime": "northeast"},
    "Chicago": {"lat": 41.7868, "lon": -87.7522, "station": "KMDW", "tz": "America/Chicago", "regime": "lake"},
    "Dallas": {"lat": 32.8998, "lon": -97.0403, "station": "KDFW", "tz": "America/Chicago", "regime": "humid"},
    "Denver": {"lat": 39.8561, "lon": -104.6737, "station": "KDEN", "tz": "America/Denver", "regime": "elevation"},
    "Houston": {"lat": 29.6454, "lon": -95.2789, "station": "KHOU", "tz": "America/Chicago", "regime": "humid"},
    "Las Vegas": {"lat": 36.0840, "lon": -115.1537, "station": "KLAS", "tz": "America/Los_Angeles", "regime": "desert"},
    "Los Angeles": {"lat": 33.9416, "lon": -118.4085, "station": "KLAX", "tz": "America/Los_Angeles", "regime": "marine"},
    "Miami": {"lat": 25.7959, "lon": -80.2870, "station": "KMIA", "tz": "America/New_York", "regime": "humid"},
    "Minneapolis": {"lat": 44.8848, "lon": -93.2223, "station": "KMSP", "tz": "America/Chicago", "regime": "northern"},
    "New Orleans": {"lat": 29.9934, "lon": -90.2580, "station": "KMSY", "tz": "America/Chicago", "regime": "humid"},
    "New York City": {"lat": 40.7789, "lon": -73.9692, "station": "KNYC", "tz": "America/New_York", "regime": "northeast"},
    "Oklahoma City": {"lat": 35.3931, "lon": -97.6007, "station": "KOKC", "tz": "America/Chicago", "regime": "plains"},
    "Philadelphia": {"lat": 39.8729, "lon": -75.2437, "station": "KPHL", "tz": "America/New_York", "regime": "northeast"},
    "Phoenix": {"lat": 33.4278, "lon": -112.0035, "station": "KPHX", "tz": "America/Phoenix", "regime": "desert"},
    "San Antonio": {"lat": 29.5337, "lon": -98.4698, "station": "KSAT", "tz": "America/Chicago", "regime": "humid"},
    "San Francisco": {"lat": 37.6213, "lon": -122.3790, "station": "KSFO", "tz": "America/Los_Angeles", "regime": "marine"},
    "Seattle/Tacoma": {"lat": 47.4502, "lon": -122.3088, "station": "KSEA", "tz": "America/Los_Angeles", "regime": "marine"},
    "Washington DC": {"lat": 38.8512, "lon": -77.0402, "station": "KDCA", "tz": "America/New_York", "regime": "northeast"},
}

# -----------------------------
# Helpers
# -----------------------------
def safe_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s in ["", "-", "--", "M", "NA", "N/A"]:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def c_to_f(c):
    if c is None:
        return None
    return round((float(c) * 9 / 5) + 32, 1)


def parse_wind_speed(value):
    if value is None:
        return None
    nums = re.findall(r"\d+", str(value))
    if not nums:
        return None
    return float(nums[-1]) if len(nums) > 1 else float(nums[0])


def heat_index_simple(temp_f, rh):
    if temp_f is None or rh is None:
        return None
    if temp_f < 80 or rh < 40:
        return round(temp_f, 1)
    T, R = temp_f, rh
    hi = (-42.379 + 2.04901523*T + 10.14333127*R - 0.22475541*T*R
          - 0.00683783*T*T - 0.05481717*R*R + 0.00122874*T*T*R
          + 0.00085282*T*R*R - 0.00000199*T*T*R*R)
    return round(hi, 1)


def fmt_temp(x):
    if x is None or pd.isna(x):
        return "N/A"
    x = float(x)
    if abs(x - round(x)) < 0.05:
        return f"{int(round(x))}°F"
    return f"{x:.1f}°F"


def fmt_hour(dt):
    if dt is None or pd.isna(dt):
        return "N/A"
    return pd.to_datetime(dt).strftime("%-I:%M %p")


def day_bounds(now_local):
    today_start = datetime.combine(now_local.date(), time(0, 0), tzinfo=now_local.tzinfo)
    tomorrow_start = today_start + timedelta(days=1)
    after_tomorrow_start = today_start + timedelta(days=2)
    return today_start, tomorrow_start, after_tomorrow_start

# -----------------------------
# Data
# -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_forecast_hourly(lat, lon):
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    p = requests.get(points_url, headers=NWS_HEADERS, timeout=20)
    p.raise_for_status()
    forecast_hourly_url = p.json()["properties"]["forecastHourly"]
    r = requests.get(forecast_hourly_url, headers=NWS_HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()["properties"]["periods"]


def periods_to_df(periods, tz_name):
    rows = []
    tz = ZoneInfo(tz_name)
    for p in periods:
        dt = pd.to_datetime(p.get("startTime"), errors="coerce")
        if pd.isna(dt):
            continue
        dt = dt.to_pydatetime().astimezone(tz)
        temp = safe_float(p.get("temperature"))
        dew_f = None
        dew = p.get("dewpoint")
        if isinstance(dew, dict):
            dew_f = c_to_f(dew.get("value"))
        rh = None
        rel = p.get("relativeHumidity")
        if isinstance(rel, dict):
            rh = safe_float(rel.get("value"))
        precip = None
        pop = p.get("probabilityOfPrecipitation")
        if isinstance(pop, dict):
            precip = safe_float(pop.get("value"))
        wind_mph = parse_wind_speed(p.get("windSpeed"))
        rows.append({
            "dt": dt,
            "Time": dt.strftime("%a %-I %p"),
            "Source": "FORECAST",
            "Temp": temp,
            "Dewpoint": dew_f,
            "Heat Index": heat_index_simple(temp, rh),
            "Wind mph": wind_mph,
            "Wind Dir": p.get("windDirection") or "-",
            "Gust mph": None,
            "Sky Cover %": None,
            "Precip %": precip,
            "Humidity %": rh,
            "Rain": "Yes" if "rain" in str(p.get("shortForecast", "")).lower() else "-",
            "Thunder": "Yes" if "thunder" in str(p.get("shortForecast", "")).lower() else "-",
            "Description": p.get("shortForecast") or "-",
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=900, show_spinner=False)
def get_obhistory_html(station):
    url = f"https://forecast.weather.gov/data/obhistory/{station}.html"
    r = requests.get(url, headers={"User-Agent": NWS_HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    return r.text


def parse_obhistory(station, tz_name, now_local):
    try:
        html = get_obhistory_html(station)
    except Exception:
        return pd.DataFrame()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()

    headers = []
    for th in table.find_all("th"):
        text = " ".join(th.get_text(" ", strip=True).split())
        headers.append(text)

    # NWS table headers are sometimes split awkwardly. Parse by fixed column order from rows.
    rows = []
    tz = ZoneInfo(tz_name)
    for tr in table.find_all("tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if len(cells) < 8:
            continue

        day = safe_float(cells[0])
        clock = cells[1] if len(cells) > 1 else None
        if day is None or not clock:
            continue

        try:
            obs_date = now_local.date().replace(day=int(day))
            obs_dt = datetime.strptime(f"{obs_date} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            # Handle month boundary if needed
            if obs_dt > now_local + timedelta(days=1):
                prev_month = (now_local.replace(day=1) - timedelta(days=1)).date()
                obs_date = prev_month.replace(day=int(day))
                obs_dt = datetime.strptime(f"{obs_date} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except Exception:
            continue

        weather = cells[4] if len(cells) > 4 else "-"
        sky = cells[5] if len(cells) > 5 else "-"
        temp = safe_float(cells[6] if len(cells) > 6 else None)
        dew = safe_float(cells[7] if len(cells) > 7 else None)
        rh = safe_float(cells[11] if len(cells) > 11 else None)
        wind_raw = cells[2] if len(cells) > 2 else "-"
        visibility = cells[3] if len(cells) > 3 else "-"

        wind_mph = None
        wind_dir = "-"
        # Some rows put wind direction and speed together, e.g. "NE 10"
        parts = wind_raw.split()
        if len(parts) >= 2:
            wind_dir = parts[0]
            wind_mph = safe_float(parts[1])
        else:
            wind_mph = safe_float(wind_raw)

        rows.append({
            "dt": obs_dt,
            "Time": obs_dt.strftime("%a %-I:%M %p"),
            "Source": "OBSERVED",
            "Temp": temp,
            "Dewpoint": dew,
            "Heat Index": heat_index_simple(temp, rh),
            "Wind mph": wind_mph,
            "Wind Dir": wind_dir,
            "Gust mph": None,
            "Sky Cover %": None,
            "Precip %": None,
            "Humidity %": rh,
            "Rain": "Yes" if "rain" in weather.lower() else "-",
            "Thunder": "Yes" if "thunder" in weather.lower() else "-",
            "Description": weather or sky or "-",
            "Visibility": visibility,
            "Sky Cond": sky,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("dt").drop_duplicates(subset=["dt"], keep="last")


def build_48h(city_cfg):
    tz = ZoneInfo(city_cfg["tz"])
    now = datetime.now(tz)
    today_start, tomorrow_start, after_tomorrow_start = day_bounds(now)

    obs = parse_obhistory(city_cfg["station"], city_cfg["tz"], now)
    periods = get_forecast_hourly(city_cfg["lat"], city_cfg["lon"])
    fcst = periods_to_df(periods, city_cfg["tz"])

    if not obs.empty:
        obs = obs[(obs["dt"] >= today_start) & (obs["dt"] <= now)]
    if not fcst.empty:
        fcst = fcst[(fcst["dt"] > now) & (fcst["dt"] < after_tomorrow_start)]

    merged = pd.concat([obs, fcst], ignore_index=True)
    if merged.empty:
        return merged, obs, fcst, now
    merged = merged.sort_values("dt").reset_index(drop=True)
    return merged, obs, fcst, now

# -----------------------------
# Probability + regime
# -----------------------------
def base_confidence(event_dt, now):
    if event_dt is None or pd.isna(event_dt):
        return 50
    hours = max(0, (pd.to_datetime(event_dt).to_pydatetime() - now).total_seconds() / 3600)
    if hours <= 2:
        return 88
    if hours <= 4:
        return 84
    if hours <= 8:
        return 78
    if hours <= 12:
        return 72
    if hours <= 18:
        return 66
    if hours <= 24:
        return 60
    if hours <= 36:
        return 55
    return 50


def classify_heat_regime(row, city_regime):
    score = 0
    reasons = []
    temp = safe_float(row.get("Temp"))
    dew = safe_float(row.get("Dewpoint"))
    hi = safe_float(row.get("Heat Index"))
    wind = safe_float(row.get("Wind mph"))
    sky = safe_float(row.get("Sky Cover %"))
    precip = safe_float(row.get("Precip %"))
    rh = safe_float(row.get("Humidity %"))
    rain = str(row.get("Rain", "-")).lower()
    thunder = str(row.get("Thunder", "-")).lower()

    if dew is not None:
        if dew >= 70:
            score += 3; reasons.append("very high dewpoint")
        elif dew >= 65:
            score += 2; reasons.append("high dewpoint")
        elif dew <= 40:
            score -= 2; reasons.append("dry air")
        elif dew <= 50:
            score -= 1; reasons.append("moderately dry air")
    if rh is not None:
        if rh >= 85:
            score += 2; reasons.append("high humidity")
        elif rh >= 70:
            score += 1; reasons.append("moderate humidity")
        elif rh <= 40:
            score -= 2; reasons.append("low humidity")
    if sky is not None:
        if sky >= 70:
            score += 2; reasons.append("cloud cover")
        elif sky >= 50:
            score += 1; reasons.append("partial clouds")
        elif sky <= 20:
            score -= 2; reasons.append("clear sky")
        elif sky <= 35:
            score -= 1; reasons.append("mostly clear")
    if wind is not None:
        if wind <= 3:
            score -= 1; reasons.append("calm wind")
        elif wind >= 12:
            score += 1; reasons.append("wind mixing")
    if precip is not None:
        if precip >= 50:
            score += 2; reasons.append("high precip risk")
        elif precip >= 25:
            score += 1; reasons.append("some precip risk")
    if rain not in ["-", "--", "none", "nan", ""]:
        score += 2; reasons.append("rain")
    if thunder not in ["-", "--", "none", "nan", ""]:
        score += 1; reasons.append("thunder")
    if hi is not None and temp is not None and hi - temp >= 3:
        score += 2; reasons.append("heat index")
    elif hi is not None and temp is not None and hi > temp:
        score += 1; reasons.append("humid heat")

    if city_regime == "humid":
        score += 1; reasons.append("humid city")
    elif city_regime == "desert":
        score -= 1; reasons.append("desert baseline")
    elif city_regime == "marine":
        score += 1; reasons.append("marine influence")
    elif city_regime == "elevation":
        score -= 1; reasons.append("elevation cooling")

    if score >= 2:
        return "HEAT RETENTION", score, "#b45309", ", ".join(reasons[:4])
    if score <= -2:
        return "HEAT LOSS", score, "#1d4ed8", ", ".join(reasons[:4])
    return "NEUTRAL", score, "#374151", ", ".join(reasons[:4])


def extreme_for_day(df, start, end, high=True):
    d = df[(df["dt"] >= start) & (df["dt"] < end) & df["Temp"].notna()].copy()
    if d.empty:
        return None, None, None
    idx = d["Temp"].idxmax() if high else d["Temp"].idxmin()
    row = d.loc[idx]
    return float(row["Temp"]), row["dt"], row

# -----------------------------
# CSS / custom real dropdown
# -----------------------------
st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 1180px; }
.nws-card { background:#111827; border:1px solid #263244; border-radius:14px; padding:14px 16px; margin-bottom:10px; }
.metric-title { color:#cbd5e1; font-size:13px; font-weight:700; }
.metric-value { font-size:34px; font-weight:800; margin-top:4px; }
.badge { display:inline-block; padding:5px 9px; border-radius:999px; background:#166534; color:#d1fae5; font-size:12px; font-weight:700; }
.heat-box { border-radius:14px; padding:14px 16px; color:white; font-weight:800; margin:12px 0; border:1px solid rgba(255,255,255,.15); }
.heat-sub { font-size:12px; font-weight:600; opacity:.95; margin-top:7px; }
.native-select { width:100%; height:48px; border-radius:10px; background:#1f2937; color:white; border:1px solid #93c5fd; padding:0 14px; font-size:16px; font-weight:700; }
@media (max-width: 640px) {
  .block-container { padding-left: .75rem; padding-right: .75rem; }
  .metric-value { font-size:30px; }
  h1 { font-size:1.45rem !important; }
  h2 { font-size:1.25rem !important; }
}
</style>
""", unsafe_allow_html=True)

# Query param backed native select. This avoids the mobile keyboard and stays connected.
city_names = list(CITIES.keys())
qp_city = st.query_params.get("city", "Atlanta")
if qp_city not in CITIES:
    qp_city = "Atlanta"

options_html = "".join([
    f'<option value="{quote(name)}" {"selected" if name == qp_city else ""}>{name}</option>'
    for name in city_names
])
components.html(f"""
<label style="color:white;font-weight:700;font-family:sans-serif;font-size:14px;">City</label>
<select class="native-select" onchange="window.parent.location.search='?city='+this.value">
{options_html}
</select>
<style>
.native-select {{ width:100%; height:48px; border-radius:10px; background:#1f2937; color:white; border:1px solid #93c5fd; padding:0 14px; font-size:16px; font-weight:700; }}
</style>
""", height=78)

selected_city = qp_city
cfg = CITIES[selected_city]

# -----------------------------
# App
# -----------------------------
st.title("NWS Weather Monitor")
st.caption("Fast monitor using official NWS station forecast + live station observation history.")

if st.button("Refresh now"):
    st.cache_data.clear()
    st.rerun()

try:
    timeline, obs, fcst, now = build_48h(cfg)
except Exception as e:
    st.error(f"Could not load NWS data for {selected_city}: {e}")
    st.stop()

st.caption(f"Station: {cfg['station']} · City: {selected_city} · Local time: {now.strftime('%Y-%m-%d %-I:%M %p %Z')}")

if timeline.empty:
    st.warning("No data returned from NWS.")
    st.stop()

today_start, tomorrow_start, after_tomorrow_start = day_bounds(now)

t_high, t_high_dt, t_high_row = extreme_for_day(timeline, today_start, tomorrow_start, high=True)
t_low, t_low_dt, t_low_row = extreme_for_day(timeline, today_start, tomorrow_start, high=False)
tm_high, tm_high_dt, tm_high_row = extreme_for_day(timeline, tomorrow_start, after_tomorrow_start, high=True)
tm_low, tm_low_dt, tm_low_row = extreme_for_day(timeline, tomorrow_start, after_tomorrow_start, high=False)

# Current temperature from latest observed row if possible, otherwise nearest forecast.
current_temp = None
if not obs.empty:
    latest_obs = obs.sort_values("dt").tail(1).iloc[0]
    current_temp = latest_obs.get("Temp")
else:
    past_or_now = timeline[timeline["dt"] <= now]
    if not past_or_now.empty:
        current_temp = past_or_now.tail(1).iloc[0].get("Temp")

st.subheader("Today projected temperatures")
c1, c2 = st.columns(2)
with c1:
    conf = base_confidence(t_high_dt, now)
    src = str(t_high_row.get("Source", "")) if t_high_row is not None else ""
    st.markdown(f"""
    <div class='nws-card'>
      <div class='metric-title'>Today High</div>
      <div class='metric-value'>{fmt_temp(t_high)}</div>
      <span class='badge'>↑ {fmt_hour(t_high_dt)} · {conf}% · {src}</span>
    </div>
    """, unsafe_allow_html=True)
with c2:
    conf = base_confidence(t_low_dt, now)
    src = str(t_low_row.get("Source", "")) if t_low_row is not None else ""
    st.markdown(f"""
    <div class='nws-card'>
      <div class='metric-title'>Today Low</div>
      <div class='metric-value'>{fmt_temp(t_low)}</div>
      <span class='badge'>↓ {fmt_hour(t_low_dt)} · {conf}% · {src}</span>
    </div>
    """, unsafe_allow_html=True)

# Heat regime based on the most relevant current/next event row.
regime_row = t_low_row if t_low_row is not None else (timeline.tail(1).iloc[0] if not timeline.empty else {})
heat_label, heat_score, heat_color, heat_reasons = classify_heat_regime(regime_row, cfg["regime"])
st.markdown(f"""
<div class='heat-box' style='background:{heat_color};'>
  {heat_label}
  <div class='heat-sub'>Score {heat_score} · {heat_reasons}</div>
</div>
""", unsafe_allow_html=True)

with st.expander("Tomorrow projected temperatures", expanded=False):
    c3, c4 = st.columns(2)
    with c3:
        st.metric("Tomorrow High", fmt_temp(tm_high), f"{fmt_hour(tm_high_dt)} · {base_confidence(tm_high_dt, now)}%")
    with c4:
        st.metric("Tomorrow Low", fmt_temp(tm_low), f"{fmt_hour(tm_low_dt)} · {base_confidence(tm_low_dt, now)}%")

# Chart above current conditions and table
plot_df = timeline.copy()
plot_df["line_source"] = plot_df["Source"].fillna("FORECAST")
fig = go.Figure()
for source, color in [("OBSERVED", "#ff624d"), ("FORECAST", "#6175ff")]:
    d = plot_df[plot_df["Source"] == source]
    if not d.empty:
        fig.add_trace(go.Scatter(x=d["dt"], y=d["Temp"], mode="lines+markers", name=source, line=dict(color=color, width=2), marker=dict(size=5)))

for label, dt, val, color in [("H", t_high_dt, t_high, "#14b8a6"), ("L", t_low_dt, t_low, "#a855f7"), ("H", tm_high_dt, tm_high, "#fb923c"), ("L", tm_low_dt, tm_low, "#22d3ee")]:
    if dt is not None and val is not None:
        fig.add_trace(go.Scatter(x=[dt], y=[val], mode="markers+text", text=[label], textposition="top center", name=label, marker=dict(size=13, color=color)))

fig.update_layout(
    height=360,
    margin=dict(l=10, r=10, t=25, b=10),
    paper_bgcolor="#0b0f17",
    plot_bgcolor="#0b0f17",
    font=dict(color="#e5e7eb"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(gridcolor="#263244"),
    yaxis=dict(title="Temperature (°F)", gridcolor="#263244"),
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Current conditions")
cc1, cc2, cc3 = st.columns(3)
cc1.metric("Current Temperature", fmt_temp(current_temp))
cc2.metric("Station", cfg["station"])
cc3.metric("Regime", cfg["regime"].title())

st.subheader("Observed + forecast table")
table = timeline.copy()
table = table[["Time", "Source", "Temp", "Dewpoint", "Heat Index", "Wind mph", "Wind Dir", "Gust mph", "Sky Cover %", "Precip %", "Humidity %", "Rain", "Thunder", "Description"]]
st.dataframe(table, use_container_width=True, hide_index=True)

with st.expander("Debug: raw observed rows", expanded=False):
    if obs.empty:
        st.write("No observed rows parsed.")
    else:
        st.dataframe(obs, use_container_width=True, hide_index=True)
