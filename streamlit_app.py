from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import re

import pandas as pd
import requests
import streamlit as st


APP_NAME = "NWS Weather Monitor"
NWS_BASE_URL = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "NWS Weather Monitor beginner Streamlit app",
    "Accept": "application/geo+json",
}


CITIES = {
    "Atlanta": {"state": "GA", "lat": 33.7490, "lon": -84.3880, "tz": "America/New_York", "climate": "humid"},
    "Austin": {"state": "TX", "lat": 30.2672, "lon": -97.7431, "tz": "America/Chicago", "climate": "hot_humid"},
    "Boston": {"state": "MA", "lat": 42.3601, "lon": -71.0589, "tz": "America/New_York", "climate": "coastal"},
    "Chicago": {"state": "IL", "lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago", "climate": "continental"},
    "Dallas": {"state": "TX", "lat": 32.7767, "lon": -96.7970, "tz": "America/Chicago", "climate": "hot_humid"},
    "Denver": {"state": "CO", "lat": 39.7392, "lon": -104.9903, "tz": "America/Denver", "climate": "dry"},
    "Houston": {"state": "TX", "lat": 29.7604, "lon": -95.3698, "tz": "America/Chicago", "climate": "hot_humid"},
    "Las Vegas": {"state": "NV", "lat": 36.1699, "lon": -115.1398, "tz": "America/Los_Angeles", "climate": "desert"},
    "Los Angeles": {"state": "CA", "lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles", "climate": "coastal"},
    "Miami": {"state": "FL", "lat": 25.7617, "lon": -80.1918, "tz": "America/New_York", "climate": "tropical"},
    "Minneapolis": {"state": "MN", "lat": 44.9778, "lon": -93.2650, "tz": "America/Chicago", "climate": "continental"},
    "New Orleans": {"state": "LA", "lat": 29.9511, "lon": -90.0715, "tz": "America/Chicago", "climate": "humid"},
    "New York City": {"state": "NY", "lat": 40.7128, "lon": -74.0060, "tz": "America/New_York", "climate": "coastal"},
    "Oklahoma City": {"state": "OK", "lat": 35.4676, "lon": -97.5164, "tz": "America/Chicago", "climate": "plains"},
    "Philadelphia": {"state": "PA", "lat": 39.9526, "lon": -75.1652, "tz": "America/New_York", "climate": "humid"},
    "Phoenix": {"state": "AZ", "lat": 33.4484, "lon": -112.0740, "tz": "America/Phoenix", "climate": "desert"},
    "San Antonio": {"state": "TX", "lat": 29.4241, "lon": -98.4936, "tz": "America/Chicago", "climate": "hot_humid"},
    "San Francisco": {"state": "CA", "lat": 37.7749, "lon": -122.4194, "tz": "America/Los_Angeles", "climate": "coastal"},
    "Seattle/Tacoma": {"state": "WA", "lat": 47.6062, "lon": -122.3321, "tz": "America/Los_Angeles", "climate": "marine"},
    "Washington DC": {"state": "DC", "lat": 38.9072, "lon": -77.0369, "tz": "America/New_York", "climate": "humid"},
}


def page_setup():
    st.set_page_config(page_title=APP_NAME, layout="wide")
    st.markdown(
        """
        <meta http-equiv="refresh" content="3600">
        <style>
        .stApp {
            background: #0b111b;
            color: #eef3fb;
        }
        [data-testid="stSidebar"] {
            background: #111927;
            border-right: 1px solid #263244;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #121c2b, #0e1622);
            border: 1px solid #2a374b;
            border-radius: 8px;
            padding: 1rem;
        }
        .top-card, .detail-card, .note-card {
            background: linear-gradient(145deg, #121c2b, #0e1622);
            border: 1px solid #2a374b;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            min-height: 150px;
        }
        .muted {
            color: #a9b4c3;
            font-size: 0.9rem;
        }
        .big-number {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
        }
        .hot {
            color: #ff5a5f;
        }
        .cold {
            color: #67a3ff;
        }
        .good {
            color: #61d66f;
            font-weight: 700;
        }
        .warn {
            color: #ffd24a;
            font-weight: 700;
        }
        .bad {
            color: #ff6b6b;
            font-weight: 700;
        }
        .source-observed {
            color: #61d66f;
            font-weight: 800;
        }
        .source-forecast {
            color: #67a3ff;
            font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def nws_get(url, params=None):
    response = requests.get(url, headers=HEADERS, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_point_data(lat, lon):
    return nws_get(f"{NWS_BASE_URL}/points/{lat:.4f},{lon:.4f}")


@st.cache_data(ttl=3600, show_spinner=False)
def get_hourly_forecast(forecast_hourly_url):
    return nws_get(forecast_hourly_url)


@st.cache_data(ttl=3600, show_spinner=False)
def get_station_list(stations_url):
    return nws_get(stations_url)


@st.cache_data(ttl=3600, show_spinner=False)
def get_observations(station_id, start_iso, end_iso):
    url = f"{NWS_BASE_URL}/stations/{station_id}/observations"
    return nws_get(url, params={"start": start_iso, "end": end_iso})


def c_to_f(value):
    if value is None:
        return None
    return (value * 9 / 5) + 32


def mps_to_mph(value):
    if value is None:
        return None
    return value * 2.23694


def degrees_to_compass(degrees):
    if degrees is None:
        return "-"
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(degrees / 22.5) % 16
    return directions[index]


def number_from_text(text):
    if not text:
        return None
    match = re.search(r"\d+", str(text))
    return int(match.group()) if match else None


def round_or_none(value):
    if value is None or pd.isna(value):
        return None
    return int(round(value))


def heat_index_f(temp_f, humidity):
    if temp_f is None or humidity is None or temp_f < 80 or humidity < 40:
        return temp_f
    t = temp_f
    rh = humidity
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    return hi


def estimate_sky_cover(description, pop):
    text = (description or "").lower()
    if "sunny" in text or "clear" in text:
        return 10
    if "mostly sunny" in text or "mostly clear" in text:
        return 25
    if "partly" in text:
        return 45
    if "mostly cloudy" in text:
        return 75
    if "cloudy" in text or "overcast" in text:
        return 90
    if pop is not None and pop >= 60:
        return 80
    if pop is not None and pop >= 30:
        return 60
    return 50


def rain_flag(description, pop):
    text = (description or "").lower()
    return "Yes" if any(word in text for word in ["rain", "shower", "drizzle"]) or (pop or 0) >= 50 else "-"


def thunder_flag(description):
    text = (description or "").lower()
    return "Yes" if any(word in text for word in ["thunder", "storm"]) else "-"


def build_forecast_rows(periods, city_tz):
    rows = {}
    for period in periods:
        start = datetime.fromisoformat(period["startTime"]).astimezone(city_tz)
        hour_key = start.replace(minute=0, second=0, microsecond=0)
        temp = period.get("temperature")
        dewpoint = c_to_f(period.get("dewpoint", {}).get("value"))
        humidity = period.get("relativeHumidity", {}).get("value")
        pop = period.get("probabilityOfPrecipitation", {}).get("value")
        wind = number_from_text(period.get("windSpeed"))
        gust = number_from_text(period.get("windGust"))
        description = period.get("shortForecast", "")
        sky = estimate_sky_cover(description, pop)
        rows[hour_key] = {
            "time": hour_key,
            "source": "FORECAST",
            "temperature": temp,
            "dewpoint": dewpoint,
            "heat_index": heat_index_f(temp, humidity),
            "wind": wind,
            "wind_direction": period.get("windDirection") or "-",
            "gust": gust,
            "sky_cover": sky,
            "precip_probability": pop,
            "humidity": humidity,
            "rain": rain_flag(description, pop),
            "thunder": thunder_flag(description),
            "description": description or "Forecast",
        }
    return rows


def build_observed_rows(features, city_tz):
    rows = {}
    for feature in features:
        props = feature.get("properties", {})
        timestamp = props.get("timestamp")
        if not timestamp:
            continue
        obs_time = datetime.fromisoformat(timestamp).astimezone(city_tz)
        hour_key = obs_time.replace(minute=0, second=0, microsecond=0)
        temp = c_to_f(props.get("temperature", {}).get("value"))
        dewpoint = c_to_f(props.get("dewpoint", {}).get("value"))
        humidity = props.get("relativeHumidity", {}).get("value")
        wind = mps_to_mph(props.get("windSpeed", {}).get("value"))
        gust = mps_to_mph(props.get("windGust", {}).get("value"))
        wind_direction = degrees_to_compass(props.get("windDirection", {}).get("value"))
        description = props.get("textDescription") or "Observed weather"
        pop = 100 if rain_flag(description, 0) == "Yes" else 0
        rows[hour_key] = {
            "time": hour_key,
            "source": "OBSERVED",
            "temperature": temp,
            "dewpoint": dewpoint,
            "heat_index": heat_index_f(temp, humidity),
            "wind": wind,
            "wind_direction": wind_direction,
            "gust": gust,
            "sky_cover": estimate_sky_cover(description, pop),
            "precip_probability": pop,
            "humidity": humidity,
            "rain": rain_flag(description, pop),
            "thunder": thunder_flag(description),
            "description": description,
        }
    return rows


def blank_row(hour, source):
    return {
        "time": hour,
        "source": source,
        "temperature": None,
        "dewpoint": None,
        "heat_index": None,
        "wind": None,
        "wind_direction": "-",
        "gust": None,
        "sky_cover": None,
        "precip_probability": None,
        "humidity": None,
        "rain": "-",
        "thunder": "-",
        "description": "No data available",
    }


def get_weather_data(city_name, refresh_key):
    del refresh_key
    city = CITIES[city_name]
    city_tz = ZoneInfo(city["tz"])
    now = datetime.now(city_tz)
    start = datetime.combine(now.date(), time.min, tzinfo=city_tz)
    hours = [start + timedelta(hours=i) for i in range(48)]

    point_data = get_point_data(city["lat"], city["lon"])
    props = point_data["properties"]
    forecast_data = get_hourly_forecast(props["forecastHourly"])
    forecast_rows = build_forecast_rows(forecast_data["properties"]["periods"], city_tz)

    observed_rows = {}
    try:
        station_data = get_station_list(props["observationStations"])
        station_id = station_data["features"][0]["properties"]["stationIdentifier"]
        observations = get_observations(station_id, start.isoformat(), now.isoformat())
        observed_rows = build_observed_rows(observations.get("features", []), city_tz)
    except Exception:
        observed_rows = {}

    merged = []
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    for hour in hours:
        if hour <= current_hour and hour in observed_rows:
            row = observed_rows[hour]
        elif hour in forecast_rows:
            row = forecast_rows[hour]
        else:
            row = blank_row(hour, "OBSERVED" if hour < now else "FORECAST")
        merged.append(row)

    return pd.DataFrame(merged), now


def confidence_class(score):
    if score >= 80:
        return "good"
    if score >= 65:
        return "warn"
    return "bad"


def forecast_confidence(row, event_type, now, climate):
    if row["source"] == "OBSERVED":
        return 100

    event_time = row["time"]
    hours_remaining = max((event_time - now).total_seconds() / 3600, 0)
    score = 92 - min(hours_remaining * 1.25, 35)

    sky = row.get("sky_cover") or 50
    humidity = row.get("humidity") or 50
    dewpoint = row.get("dewpoint") or 50
    pop = row.get("precip_probability") or 0
    wind = row.get("wind") or 5

    if event_type == "high":
        score -= pop * 0.18
        score -= max(sky - 45, 0) * 0.12
        score += 5 if sky < 35 and pop < 20 else 0
        score -= 4 if dewpoint > 72 else 0
    else:
        score += 4 if humidity > 70 and sky > 60 else 0
        score -= 5 if humidity < 45 and wind < 6 else 0
        score -= 3 if climate in ["desert", "dry"] else 0
        score -= pop * 0.08

    if climate in ["coastal", "marine"]:
        score += 3
    if climate in ["plains", "continental"] and hours_remaining > 18:
        score -= 3

    return int(max(45, min(score, 100)))


def daily_extreme(df, day, kind, now, climate):
    day_rows = df[df["time"].dt.date == day].copy()
    day_rows = day_rows.dropna(subset=["temperature"])
    if day_rows.empty:
        return None
    index = day_rows["temperature"].idxmax() if kind == "high" else day_rows["temperature"].idxmin()
    row = day_rows.loc[index]
    return {
        "temp": round_or_none(row["temperature"]),
        "hour": row["time"].strftime("%-I:%M %p"),
        "confidence": forecast_confidence(row, kind, now, climate),
        "source": row["source"],
        "description": row["description"],
    }


def risk_text(day_rows, high, low):
    pop_max = day_rows["precip_probability"].fillna(0).max()
    sky_avg = day_rows["sky_cover"].fillna(50).mean()
    humidity_avg = day_rows["humidity"].fillna(50).mean()
    thunder = (day_rows["thunder"] == "Yes").any()

    if thunder:
        return "Thunder risk may disrupt heating"
    if pop_max >= 50:
        return "Rain may cap daytime heating"
    if humidity_avg >= 75 and sky_avg >= 60:
        return "Clouds and humidity hold heat"
    if high and high["temp"] >= 95:
        return "Hot afternoon conditions"
    if low and low["temp"] <= 32:
        return "Freezing overnight risk"
    return "Stable forecast pattern"


def day_card(title, date_value, high, low, risk):
    high_conf_class = confidence_class(high["confidence"]) if high else "warn"
    low_conf_class = confidence_class(low["confidence"]) if low else "warn"
    high_temp = f"{high['temp']}°F" if high else "-"
    low_temp = f"{low['temp']}°F" if low else "-"
    high_hour = high["hour"] if high else "-"
    low_hour = low["hour"] if low else "-"
    high_conf = f"{high['confidence']}%" if high else "-"
    low_conf = f"{low['confidence']}%" if low else "-"

    st.markdown(
        f"""
        <div class="top-card">
            <div style="display:flex; justify-content:space-between; gap:1rem;">
                <div>
                    <div class="muted">{title}</div>
                    <h3 style="margin:0.2rem 0 0.9rem;">{date_value}</h3>
                </div>
                <div class="muted">Main Risk<br><b style="color:#eef3fb;">{risk}</b></div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                <div>
                    <div class="hot" style="font-weight:800;">HIGH</div>
                    <div class="big-number hot">{high_temp}</div>
                    <div>{high_hour}</div>
                    <div class="muted">Confidence: <span class="{high_conf_class}">{high_conf}</span></div>
                </div>
                <div>
                    <div class="cold" style="font-weight:800;">LOW</div>
                    <div class="big-number cold">{low_temp}</div>
                    <div>{low_hour}</div>
                    <div class="muted">Confidence: <span class="{low_conf_class}">{low_conf}</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_value(value, suffix=""):
    if value is None or pd.isna(value):
        return "-"
    return f"{int(round(value))}{suffix}"


def build_display_table(df):
    columns = [row["time"].strftime("%a %-I %p") for _, row in df.iterrows()]
    data = {
        "Source": ["OBS" if value == "OBSERVED" else "FCST" for value in df["source"]],
        "Temperature (°F)": [format_value(v) for v in df["temperature"]],
        "Dewpoint (°F)": [format_value(v) for v in df["dewpoint"]],
        "Heat Index (°F)": [format_value(v) for v in df["heat_index"]],
        "Wind (mph)": [format_value(v) for v in df["wind"]],
        "Wind Direction": list(df["wind_direction"]),
        "Gust (mph)": [format_value(v) for v in df["gust"]],
        "Sky Cover (%)": [format_value(v) for v in df["sky_cover"]],
        "Precip Prob (%)": [format_value(v) for v in df["precip_probability"]],
        "Humidity (%)": [format_value(v) for v in df["humidity"]],
        "Rain": list(df["rain"]),
        "Thunder": list(df["thunder"]),
    }
    return pd.DataFrame(data, index=columns).T


def selected_hour_panel(row):
    source_class = "source-observed" if row["source"] == "OBSERVED" else "source-forecast"
    st.markdown(
        f"""
        <div class="detail-card">
            <div style="display:grid; grid-template-columns:1.4fr repeat(8, 1fr); gap:1rem; align-items:center;">
                <div>
                    <div class="muted">SELECTED HOUR</div>
                    <h2 style="margin:0.1rem 0; color:#67a3ff;">{row['time'].strftime('%-I:%M %p')}</h2>
                    <div>{row['time'].strftime('%A, %b %-d')}</div>
                </div>
                <div><div class="muted">Temp</div><b class="hot">{format_value(row['temperature'], '°F')}</b></div>
                <div><div class="muted">Feels Like</div><b class="hot">{format_value(row['heat_index'], '°F')}</b></div>
                <div><div class="muted">Dewpoint</div><b class="good">{format_value(row['dewpoint'], '°F')}</b></div>
                <div><div class="muted">Humidity</div><b class="cold">{format_value(row['humidity'], '%')}</b></div>
                <div><div class="muted">Wind</div><b>{format_value(row['wind'], ' mph')}<br>{row['wind_direction']}</b></div>
                <div><div class="muted">Gust</div><b>{format_value(row['gust'], ' mph')}</b></div>
                <div><div class="muted">Precip</div><b>{format_value(row['precip_probability'], '%')}</b></div>
                <div><div class="muted">Source</div><b class="{source_class}">{row['source'].title()}</b></div>
            </div>
            <div class="muted" style="margin-top:0.9rem;">{row['description']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    page_setup()

    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0

    with st.sidebar:
        st.title("NWS Weather Monitor")
        city_name = st.selectbox("Select city", list(CITIES.keys()))
        city = CITIES[city_name]
        st.caption(f"{city_name}, {city['state']}")
        if st.button("Refresh now", use_container_width=True):
            st.cache_data.clear()
            st.session_state.refresh_key += 1
            st.rerun()
        st.divider()
        st.caption("Data source: National Weather Service")
        st.caption("Auto-refresh: every 60 minutes")

    city = CITIES[city_name]
    city_tz = ZoneInfo(city["tz"])

    title_col, status_col = st.columns([2, 1])
    with title_col:
        st.title(APP_NAME)
        st.caption("One-page climate monitoring and forecast analysis using National Weather Service data only.")
    with status_col:
        st.write("")
        st.caption("Auto-refresh: every 60 minutes")

    try:
        with st.spinner("Loading National Weather Service data..."):
            df, now = get_weather_data(city_name, st.session_state.refresh_key)
    except Exception as error:
        st.error("The National Weather Service data could not be loaded right now.")
        st.info("Try clicking Refresh now. If that does not work, wait a few minutes and try again.")
        st.caption(f"Technical detail: {error}")
        return

    today = now.date()
    tomorrow = today + timedelta(days=1)
    today_rows = df[df["time"].dt.date == today]
    tomorrow_rows = df[df["time"].dt.date == tomorrow]

    today_high = daily_extreme(df, today, "high", now, city["climate"])
    today_low = daily_extreme(df, today, "low", now, city["climate"])
    tomorrow_high = daily_extreme(df, tomorrow, "high", now, city["climate"])
    tomorrow_low = daily_extreme(df, tomorrow, "low", now, city["climate"])

    st.caption(f"Last updated: {now.strftime('%b %-d, %Y at %-I:%M %p %Z')}")

    card_col_1, card_col_2 = st.columns(2)
    with card_col_1:
        day_card(
            "TODAY",
            now.strftime("%B %-d, %Y"),
            today_high,
            today_low,
            risk_text(today_rows, today_high, today_low),
        )
    with card_col_2:
        day_card(
            "TOMORROW",
            (now + timedelta(days=1)).strftime("%B %-d, %Y"),
            tomorrow_high,
            tomorrow_low,
            risk_text(tomorrow_rows, tomorrow_high, tomorrow_low),
        )

    st.subheader("Hourly Timeline: 48-hour view")
    selected_index = st.slider("Move through the 48 hours", 0, 47, min(max(now.hour, 0), 47))
    selected_row = df.iloc[selected_index]

    st.dataframe(
        build_display_table(df),
        use_container_width=True,
        height=460,
    )

    selected_hour_panel(selected_row)

    st.markdown(
        """
        <div class="note-card">
            <b>Simple confidence method:</b>
            closer forecast hours score higher. Heavy clouds, rain chances, high humidity, dewpoint,
            heat index, and local climate type adjust the score. Observed hours are already known,
            so they show 100% confidence.
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
