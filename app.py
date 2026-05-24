from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import math
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from bs4 import BeautifulSoup

APP_NAME = "NWS Weather Monitor"
NWS_BASE_URL = "https://api.weather.gov"
OBHISTORY_BASE_URL = "https://forecast.weather.gov/data/obhistory"
HEADERS = {
    "User-Agent": "NWS Weather Monitor (personal Streamlit app; contact: user)",
    "Accept": "application/geo+json, text/html, */*",
}

CITIES = {
    "Atlanta": {"lat": 33.6407, "lon": -84.4277, "tz": "America/New_York", "station": "KATL", "climate": "humid"},
    "Austin": {"lat": 30.1945, "lon": -97.6699, "tz": "America/Chicago", "station": "KAUS", "climate": "hot_humid"},
    "Boston": {"lat": 42.3656, "lon": -71.0096, "tz": "America/New_York", "station": "KBOS", "climate": "coastal"},
    "Chicago": {"lat": 41.7868, "lon": -87.7522, "tz": "America/Chicago", "station": "KMDW", "climate": "lake"},
    "Dallas": {"lat": 32.8975, "lon": -97.0380, "tz": "America/Chicago", "station": "KDFW", "climate": "hot_humid"},
    "Denver": {"lat": 39.8561, "lon": -104.6737, "tz": "America/Denver", "station": "KDEN", "climate": "dry"},
    "Houston": {"lat": 29.6454, "lon": -95.2789, "tz": "America/Chicago", "station": "KHOU", "climate": "hot_humid"},
    "Las Vegas": {"lat": 36.0840, "lon": -115.1537, "tz": "America/Los_Angeles", "station": "KLAS", "climate": "desert"},
    "Los Angeles": {"lat": 33.9416, "lon": -118.4085, "tz": "America/Los_Angeles", "station": "KLAX", "climate": "coastal"},
    "Miami": {"lat": 25.7959, "lon": -80.2870, "tz": "America/New_York", "station": "KMIA", "climate": "tropical"},
    "Minneapolis": {"lat": 44.8848, "lon": -93.2223, "tz": "America/Chicago", "station": "KMSP", "climate": "continental"},
    "New Orleans": {"lat": 29.9934, "lon": -90.2580, "tz": "America/Chicago", "station": "KMSY", "climate": "humid"},
    "New York City": {"lat": 40.7789, "lon": -73.9692, "tz": "America/New_York", "station": "KNYC", "climate": "coastal"},
    "Oklahoma City": {"lat": 35.3931, "lon": -97.6007, "tz": "America/Chicago", "station": "KOKC", "climate": "plains"},
    "Philadelphia": {"lat": 39.8744, "lon": -75.2424, "tz": "America/New_York", "station": "KPHL", "climate": "humid"},
    "Phoenix": {"lat": 33.4278, "lon": -112.0035, "tz": "America/Phoenix", "station": "KPHX", "climate": "desert"},
    "San Antonio": {"lat": 29.5337, "lon": -98.4698, "tz": "America/Chicago", "station": "KSAT", "climate": "hot_humid"},
    "San Francisco": {"lat": 37.6213, "lon": -122.3790, "tz": "America/Los_Angeles", "station": "KSFO", "climate": "marine"},
    "Seattle/Tacoma": {"lat": 47.4502, "lon": -122.3088, "tz": "America/Los_Angeles", "station": "KSEA", "climate": "marine"},
    "Washington DC": {"lat": 38.8512, "lon": -77.0402, "tz": "America/New_York", "station": "KDCA", "climate": "humid"},
}


def safe_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def fmt_temp(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}°F"
    return f"{value:.1f}°F"


def c_to_f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return (float(v) * 9 / 5) + 32
    except Exception:
        return None


def mps_to_mph(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v) * 2.23694
    except Exception:
        return None


def number_from_text(text: Any) -> float | None:
    if not text:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(text))
    return float(m.group()) if m else None


def heat_index_f(temp_f: float | None, rh: float | None) -> float | None:
    if temp_f is None or rh is None:
        return temp_f
    if temp_f < 80 or rh < 40:
        return temp_f
    t = float(temp_f)
    r = float(rh)
    return (
        -42.379 + 2.04901523 * t + 10.14333127 * r - 0.22475541 * t * r
        - 0.00683783 * t * t - 0.05481717 * r * r
        + 0.00122874 * t * t * r + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )


def sky_from_text(text: str | None, pop: float | None = None) -> int | None:
    t = (text or "").lower()
    if "clear" in t or "sunny" in t:
        return 10
    if "partly" in t or "few" in t:
        return 45
    if "mostly cloudy" in t or "broken" in t:
        return 75
    if "cloudy" in t or "overcast" in t:
        return 90
    if pop is not None and pop >= 60:
        return 80
    return None


def parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    text = str(text).replace("°F", "").replace("M", "").strip()
    if text in {"", "-", "--", "NA", "N/A"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group()) if m else None


def parse_obhistory_datetime(value: str, tz: ZoneInfo, year: int) -> datetime | None:
    value = " ".join(value.split())
    for fmt in ("%b %d, %I:%M %p", "%B %d, %I:%M %p"):
        try:
            dt = datetime.strptime(value, fmt).replace(year=year, tzinfo=tz)
            return dt
        except ValueError:
            continue
    return None


def nws_get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def load_forecast(city_name: str) -> pd.DataFrame:
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    point = nws_get_json(f"{NWS_BASE_URL}/points/{city['lat']:.4f},{city['lon']:.4f}")
    hourly_url = point["properties"]["forecastHourly"]
    periods = nws_get_json(hourly_url)["properties"]["periods"]

    rows = []
    for p in periods:
        ts = datetime.fromisoformat(p["startTime"]).astimezone(tz).replace(minute=0, second=0, microsecond=0)
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        humidity = (p.get("relativeHumidity") or {}).get("value")
        dew = c_to_f((p.get("dewpoint") or {}).get("value"))
        temp = p.get("temperature")
        desc = p.get("shortForecast") or "Forecast"
        rows.append({
            "Time": ts,
            "Source": "FORECAST",
            "Temp": float(temp) if temp is not None else None,
            "Dewpoint": dew,
            "Heat Index": heat_index_f(float(temp), humidity) if temp is not None else None,
            "Wind mph": number_from_text(p.get("windSpeed")),
            "Wind Dir": p.get("windDirection") or "-",
            "Gust mph": number_from_text(p.get("windGust")),
            "Sky Cover %": sky_from_text(desc, pop),
            "Precip %": pop,
            "Humidity %": humidity,
            "Rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() or (pop or 0) >= 50 else "-",
            "Thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "Description": desc,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=900, show_spinner=False)
def load_obhistory(city_name: str, today_iso: str) -> pd.DataFrame:
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    station = city["station"]
    today = datetime.fromisoformat(today_iso).date()
    url = f"{OBHISTORY_BASE_URL}/{station}.html"

    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows = []
    for tr in soup.find_all("tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if len(cells) < 8:
            continue
        dt = parse_obhistory_datetime(cells[0], tz, today.year)
        if dt is None or dt.date() != today:
            continue

        temp = parse_float(cells[1])
        dew = parse_float(cells[2]) if len(cells) > 2 else None
        rh = parse_float(cells[3]) if len(cells) > 3 else None
        heat_index = parse_float(cells[4]) if len(cells) > 4 else None
        wind_chill = parse_float(cells[5]) if len(cells) > 5 else None
        wind_dir = cells[6] if len(cells) > 6 and cells[6] not in {"", "--"} else "-"
        wind = parse_float(cells[7]) if len(cells) > 7 else None
        weather = cells[9] if len(cells) > 9 else "Observed"
        sky = cells[10] if len(cells) > 10 else ""
        desc = " / ".join([x for x in [weather, sky] if x and x not in {"--", "-"}]) or "Observed"

        rows.append({
            "Time": dt,
            "Source": "OBSERVED",
            "Temp": temp,
            "Dewpoint": dew,
            "Heat Index": heat_index or wind_chill or heat_index_f(temp, rh),
            "Wind mph": wind,
            "Wind Dir": wind_dir,
            "Gust mph": None,
            "Sky Cover %": sky_from_text(desc, 0),
            "Precip %": 100 if "rain" in desc.lower() else 0,
            "Humidity %": rh,
            "Rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() else "-",
            "Thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "Description": desc,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("Time").reset_index(drop=True)


def confidence(row: pd.Series, event_type: str, now: datetime, climate: str) -> int:
    if row.get("Source") == "OBSERVED":
        return 100

    hrs = max((row["Time"] - now).total_seconds() / 3600, 0)
    if hrs <= 2:
        score = 88
    elif hrs <= 4:
        score = 84
    elif hrs <= 8:
        score = 78
    elif hrs <= 12:
        score = 72
    elif hrs <= 18:
        score = 66
    elif hrs <= 24:
        score = 60
    elif hrs <= 36:
        score = 55
    else:
        score = 50

    sky = row.get("Sky Cover %")
    pop = row.get("Precip %") or 0
    humidity = row.get("Humidity %") or 50
    dew = row.get("Dewpoint") or 50
    wind = row.get("Wind mph") or 5

    sky = 50 if sky is None or pd.isna(sky) else sky

    if event_type == "high":
        if pop >= 40 or sky >= 75:
            score -= 5
        if sky <= 35 and pop <= 20:
            score += 4
        if climate in {"desert", "hot_humid"}:
            score -= 2  # overshoot risk
        if climate in {"marine", "coastal"}:
            score += 2  # more capped
    else:
        if humidity >= 70 and sky >= 60:
            score += 4
        if humidity <= 45 and wind <= 6 and sky <= 35:
            score -= 5
        if dew <= 45:
            score -= 2

    return int(max(45, min(100, score)))


def build_merged_timeline(observed: pd.DataFrame, forecast: pd.DataFrame, now: datetime) -> pd.DataFrame:
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    end = start + timedelta(days=2)

    observed = observed.copy()
    forecast = forecast.copy()

    if not observed.empty:
        observed = observed[(observed["Time"] >= start) & (observed["Time"] <= now)]
    if not forecast.empty:
        forecast = forecast[(forecast["Time"] > now) & (forecast["Time"] < end)]

    merged = pd.concat([observed, forecast], ignore_index=True)
    if merged.empty:
        return merged
    return merged.sort_values("Time").reset_index(drop=True)


def extreme(df: pd.DataFrame, date_value, kind: str, now: datetime, climate: str):
    d = df[(df["Time"].dt.date == date_value) & df["Temp"].notna()]
    if d.empty:
        return None
    idx = d["Temp"].idxmax() if kind == "high" else d["Temp"].idxmin()
    row = d.loc[idx]
    return row, confidence(row, kind, now, climate)


def metric_card(label: str, item) -> None:
    if item is None:
        st.metric(label, "N/A", "No data")
        return
    row, conf = item
    source = row["Source"]
    st.metric(label, fmt_temp(row["Temp"]), f"{safe_time(row['Time'])} · {conf}% · {source}")


def make_chart(df: pd.DataFrame, today_high, today_low, tomorrow_high, tomorrow_low):
    chart_df = df[df["Temp"].notna()].copy()
    if chart_df.empty:
        return None

    fig = go.Figure()
    for source, group in chart_df.groupby("Source"):
        fig.add_trace(go.Scatter(
            x=group["Time"],
            y=group["Temp"],
            mode="lines+markers",
            name=source,
            hovertemplate="%{x|%a %I:%M %p}<br>%{y:.1f}°F<extra></extra>",
        ))

    markers = []
    for label, item in [
        ("H", today_high), ("L", today_low), ("H", tomorrow_high), ("L", tomorrow_low)
    ]:
        if item is not None:
            row, _ = item
            markers.append((label, row["Time"], row["Temp"]))

    for label, x, y in markers:
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            text=[label], textposition="top center",
            marker=dict(size=14, symbol="circle"),
            name=label,
            hovertemplate=f"{label}: %{{y:.1f}}°F<br>%{{x|%a %I:%M %p}}<extra></extra>",
        ))

    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=25, b=10),
        template="plotly_dark",
        xaxis_title="",
        yaxis_title="Temperature (°F)",
        legend_orientation="h",
        legend_y=1.08,
    )
    return fig


def display_table(df: pd.DataFrame):
    show = df.copy()
    show["Time"] = show["Time"].dt.strftime("%a %m/%d %I:%M %p")
    for col in ["Temp", "Dewpoint", "Heat Index", "Wind mph", "Gust mph", "Sky Cover %", "Precip %", "Humidity %"]:
        show[col] = show[col].apply(lambda x: "-" if x is None or pd.isna(x) else round(float(x), 1))
    st.dataframe(show, use_container_width=True, height=560)


st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Fast monitor using official National Weather Service forecast + live station observation history.")

city_name = st.selectbox("City", list(CITIES.keys()))
city = CITIES[city_name]
tz = ZoneInfo(city["tz"])
now = datetime.now(tz)
today = now.date()
tomorrow = today + timedelta(days=1)

cols = st.columns([1, 4])
with cols[0]:
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()
with cols[1]:
    st.caption(f"Station: {city['station']} · Local time: {now.strftime('%Y-%m-%d %I:%M %p %Z')} · Observed source: obhistory/{city['station']}.html")

try:
    forecast_df = load_forecast(city_name)
    observed_df = load_obhistory(city_name, today.isoformat())
    df = build_merged_timeline(observed_df, forecast_df, now)
except Exception as e:
    st.error("NWS data failed to load. Try Refresh now or check Streamlit logs.")
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("No data available for this city right now.")
    st.stop()

observed_high = None if observed_df.empty else observed_df.loc[observed_df["Temp"].idxmax()] if observed_df["Temp"].notna().any() else None
observed_low = None if observed_df.empty else observed_df.loc[observed_df["Temp"].idxmin()] if observed_df["Temp"].notna().any() else None

today_high = extreme(df, today, "high", now, city["climate"])
today_low = extreme(df, today, "low", now, city["climate"])
tomorrow_high = extreme(df, tomorrow, "high", now, city["climate"])
tomorrow_low = extreme(df, tomorrow, "low", now, city["climate"])

st.subheader("Observed so far")
o1, o2 = st.columns(2)
with o1:
    if observed_high is not None:
        st.metric("Observed High So Far", fmt_temp(observed_high["Temp"]), f"{safe_time(observed_high['Time'])} · live obhistory")
    else:
        st.metric("Observed High So Far", "N/A")
with o2:
    if observed_low is not None:
        st.metric("Observed Low So Far", fmt_temp(observed_low["Temp"]), f"{safe_time(observed_low['Time'])} · live obhistory")
    else:
        st.metric("Observed Low So Far", "N/A")

st.subheader("Projected full-day extremes")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Today High", today_high)
with c2:
    metric_card("Today Low", today_low)
with c3:
    metric_card("Tomorrow High", tomorrow_high)
with c4:
    metric_card("Tomorrow Low", tomorrow_low)

fig = make_chart(df, today_high, today_low, tomorrow_high, tomorrow_low)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Observed + forecast table")
display_table(df)

with st.expander("Debug: raw observed rows from NWS obhistory"):
    if observed_df.empty:
        st.write("No observed rows parsed.")
    else:
        display_table(observed_df)
