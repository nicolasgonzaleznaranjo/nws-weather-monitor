from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import re

import pandas as pd
import requests
import streamlit as st

APP_NAME = "NWS Weather Monitor"
NWS_BASE_URL = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "NWS Weather Monitor (contact: personal streamlit app)",
    "Accept": "application/geo+json",
}

CITIES = {
    "Atlanta": {"lat": 33.7490, "lon": -84.3880, "tz": "America/New_York", "climate": "humid"},
    "Austin": {"lat": 30.2672, "lon": -97.7431, "tz": "America/Chicago", "climate": "hot_humid"},
    "Boston": {"lat": 42.3601, "lon": -71.0589, "tz": "America/New_York", "climate": "coastal"},
    "Chicago": {"lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago", "climate": "continental"},
    "Dallas": {"lat": 32.7767, "lon": -96.7970, "tz": "America/Chicago", "climate": "hot_humid"},
    "Denver": {"lat": 39.7392, "lon": -104.9903, "tz": "America/Denver", "climate": "dry"},
    "Houston": {"lat": 29.7604, "lon": -95.3698, "tz": "America/Chicago", "climate": "hot_humid"},
    "Las Vegas": {"lat": 36.1699, "lon": -115.1398, "tz": "America/Los_Angeles", "climate": "desert"},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles", "climate": "coastal"},
    "Miami": {"lat": 25.7617, "lon": -80.1918, "tz": "America/New_York", "climate": "tropical"},
    "Minneapolis": {"lat": 44.9778, "lon": -93.2650, "tz": "America/Chicago", "climate": "continental"},
    "New Orleans": {"lat": 29.9511, "lon": -90.0715, "tz": "America/Chicago", "climate": "humid"},
    "New York City": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York", "climate": "coastal"},
    "Oklahoma City": {"lat": 35.4676, "lon": -97.5164, "tz": "America/Chicago", "climate": "plains"},
    "Philadelphia": {"lat": 39.9526, "lon": -75.1652, "tz": "America/New_York", "climate": "humid"},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740, "tz": "America/Phoenix", "climate": "desert"},
    "San Antonio": {"lat": 29.4241, "lon": -98.4936, "tz": "America/Chicago", "climate": "hot_humid"},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "tz": "America/Los_Angeles", "climate": "coastal"},
    "Seattle/Tacoma": {"lat": 47.6062, "lon": -122.3321, "tz": "America/Los_Angeles", "climate": "marine"},
    "Washington DC": {"lat": 38.9072, "lon": -77.0369, "tz": "America/New_York", "climate": "humid"},
}

def safe_time(dt):
    return dt.strftime("%I:%M %p").lstrip("0")

def c_to_f(v):
    return None if v is None else (v * 9 / 5) + 32

def mps_to_mph(v):
    return None if v is None else v * 2.23694

def number_from_text(text):
    if not text:
        return None
    m = re.search(r"\d+", str(text))
    return int(m.group()) if m else None

def heat_index_f(temp_f, rh):
    if temp_f is None or rh is None or temp_f < 80 or rh < 40:
        return temp_f
    t = temp_f
    r = rh
    return (-42.379 + 2.04901523*t + 10.14333127*r - 0.22475541*t*r - 0.00683783*t*t - 0.05481717*r*r + 0.00122874*t*t*r + 0.00085282*t*r*r - 0.00000199*t*t*r*r)

def sky_from_text(text, pop):
    t = (text or "").lower()
    if "clear" in t or "sunny" in t:
        return 10
    if "partly" in t:
        return 45
    if "mostly cloudy" in t:
        return 75
    if "cloudy" in t or "overcast" in t:
        return 90
    return 80 if (pop or 0) >= 60 else 50

def confidence(row, event_type, now, climate):
    if row["Source"] == "OBSERVED":
        return 100
    hrs = max((row["Time"] - now).total_seconds() / 3600, 0)
    score = 92 - min(hrs * 1.25, 40)
    sky = row.get("Sky Cover %") or 50
    pop = row.get("Precip %") or 0
    humidity = row.get("Humidity %") or 50
    dew = row.get("Dewpoint") or 50
    wind = row.get("Wind mph") or 5
    if event_type == "high":
        score -= pop * 0.15
        score -= max(sky - 50, 0) * 0.10
        if sky < 35 and pop < 20:
            score += 4
        if climate in ["desert", "hot_humid"]:
            score -= 2
    else:
        if humidity > 70 and sky > 60:
            score += 4
        if humidity < 45 and wind < 6:
            score -= 5
        if dew < 45:
            score -= 2
    return int(max(45, min(100, score)))

def nws_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def load_city(city_name):
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    now = datetime.now(tz)
    start = datetime.combine(now.date(), time.min, tzinfo=tz)
    hours = [start + timedelta(hours=i) for i in range(48)]

    point = nws_get(f"{NWS_BASE_URL}/points/{city['lat']:.4f},{city['lon']:.4f}")
    hourly_url = point["properties"]["forecastHourly"]
    forecast = nws_get(hourly_url)["properties"]["periods"]

    forecast_rows = {}
    for p in forecast:
        h = datetime.fromisoformat(p["startTime"]).astimezone(tz).replace(minute=0, second=0, microsecond=0)
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        humidity = (p.get("relativeHumidity") or {}).get("value")
        dew = c_to_f((p.get("dewpoint") or {}).get("value"))
        temp = p.get("temperature")
        desc = p.get("shortForecast", "")
        forecast_rows[h] = {
            "Time": h, "Source": "FORECAST", "Temp": temp, "Dewpoint": dew,
            "Heat Index": heat_index_f(temp, humidity), "Wind mph": number_from_text(p.get("windSpeed")),
            "Wind Dir": p.get("windDirection") or "-", "Gust mph": number_from_text(p.get("windGust")),
            "Sky Cover %": sky_from_text(desc, pop), "Precip %": pop, "Humidity %": humidity,
            "Rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() or (pop or 0) >= 50 else "-",
            "Thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "Description": desc,
        }

    observed_rows = {}
    try:
        station_url = point["properties"]["observationStations"]
        stations = nws_get(station_url)["features"]
        station_id = stations[0]["properties"]["stationIdentifier"]
        obs = nws_get(f"{NWS_BASE_URL}/stations/{station_id}/observations", params={"start": start.isoformat(), "end": now.isoformat()}).get("features", [])
        for f in obs:
            props = f.get("properties", {})
            if not props.get("timestamp"):
                continue
            h = datetime.fromisoformat(props["timestamp"]).astimezone(tz).replace(minute=0, second=0, microsecond=0)
            temp = c_to_f((props.get("temperature") or {}).get("value"))
            dew = c_to_f((props.get("dewpoint") or {}).get("value"))
            humidity = (props.get("relativeHumidity") or {}).get("value")
            desc = props.get("textDescription") or "Observed"
            observed_rows[h] = {
                "Time": h, "Source": "OBSERVED", "Temp": temp, "Dewpoint": dew,
                "Heat Index": heat_index_f(temp, humidity), "Wind mph": mps_to_mph((props.get("windSpeed") or {}).get("value")),
                "Wind Dir": "-", "Gust mph": mps_to_mph((props.get("windGust") or {}).get("value")),
                "Sky Cover %": sky_from_text(desc, 0), "Precip %": 100 if "rain" in desc.lower() else 0,
                "Humidity %": humidity, "Rain": "Yes" if "rain" in desc.lower() else "-",
                "Thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
                "Description": desc,
            }
    except Exception:
        pass

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    rows = []
    for h in hours:
        if h <= current_hour and h in observed_rows:
            rows.append(observed_rows[h])
        elif h in forecast_rows:
            rows.append(forecast_rows[h])
        else:
            rows.append({"Time": h, "Source": "OBSERVED" if h <= current_hour else "FORECAST", "Temp": None, "Dewpoint": None, "Heat Index": None, "Wind mph": None, "Wind Dir": "-", "Gust mph": None, "Sky Cover %": None, "Precip %": None, "Humidity %": None, "Rain": "-", "Thunder": "-", "Description": "No data"})
    return pd.DataFrame(rows), now

def extreme(df, date_value, kind, now, climate):
    d = df[(df["Time"].dt.date == date_value) & df["Temp"].notna()]
    if d.empty:
        return None
    idx = d["Temp"].idxmax() if kind == "high" else d["Temp"].idxmin()
    row = d.loc[idx]
    return row, confidence(row, kind, now, climate)

def card(label, item, kind):
    if item is None:
        st.metric(label, "N/A", "No data")
        return
    row, conf = item
    st.metric(label, f"{round(row['Temp'])}°F", f"{safe_time(row['Time'])} · {conf}%")

st.set_page_config(page_title=APP_NAME, layout="wide")
st.title("NWS Weather Monitor")
st.caption("Fast 48-hour monitor using National Weather Service data only.")

city_name = st.selectbox("City", list(CITIES.keys()))
if st.button("Refresh now"):
    st.cache_data.clear()
    st.rerun()

try:
    df, now = load_city(city_name)
except Exception as e:
    st.error("NWS data failed to load. Try Refresh now or check Streamlit logs.")
    st.exception(e)
    st.stop()

city = CITIES[city_name]
today = now.date()
tomorrow = today + timedelta(days=1)

st.caption(f"Local time: {now.strftime('%Y-%m-%d %I:%M %p %Z')}")

c1, c2, c3, c4 = st.columns(4)
with c1:
    card("Today High", extreme(df, today, "high", now, city["climate"]), "high")
with c2:
    card("Today Low", extreme(df, today, "low", now, city["climate"]), "low")
with c3:
    card("Tomorrow High", extreme(df, tomorrow, "high", now, city["climate"]), "high")
with c4:
    card("Tomorrow Low", extreme(df, tomorrow, "low", now, city["climate"]), "low")

st.subheader("48-hour timeline")
selected = st.slider("Hour", 0, 47, min(now.hour, 47))
row = df.iloc[selected]
st.write(f"Selected: **{row['Time'].strftime('%a %Y-%m-%d %I:%M %p')}** · **{row['Source']}** · {row['Description']}")

show = df.copy()
show["Time"] = show["Time"].dt.strftime("%a %I %p")
for col in ["Temp", "Dewpoint", "Heat Index", "Wind mph", "Gust mph", "Sky Cover %", "Precip %", "Humidity %"]:
    show[col] = show[col].apply(lambda x: "-" if pd.isna(x) else round(x))
st.dataframe(show, use_container_width=True, height=520)

st.line_chart(df.set_index("Time")["Temp"])
