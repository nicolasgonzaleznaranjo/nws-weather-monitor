import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
from io import StringIO
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="NWS Weather Monitor", layout="wide", initial_sidebar_state="collapsed")

NWS_HEADERS = {
    "User-Agent": "nws-weather-monitor/1.0 (personal weather monitor)",
    "Accept": "application/geo+json, application/json, text/html",
}

CITIES = {
    "Atlanta": {"station": "KATL", "tz": "America/New_York", "regime": "humid"},
    "Austin": {"station": "KAUS", "tz": "America/Chicago", "regime": "humid"},
    "Boston": {"station": "KBOS", "tz": "America/New_York", "regime": "northeast"},
    "Chicago": {"station": "KMDW", "tz": "America/Chicago", "regime": "lake"},
    "Dallas": {"station": "KDFW", "tz": "America/Chicago", "regime": "humid"},
    "Denver": {"station": "KDEN", "tz": "America/Denver", "regime": "elevation"},
    "Houston": {"station": "KHOU", "tz": "America/Chicago", "regime": "humid"},
    "Las Vegas": {"station": "KLAS", "tz": "America/Los_Angeles", "regime": "desert"},
    "Los Angeles": {"station": "KLAX", "tz": "America/Los_Angeles", "regime": "marine"},
    "Miami": {"station": "KMIA", "tz": "America/New_York", "regime": "humid"},
    "Minneapolis": {"station": "KMSP", "tz": "America/Chicago", "regime": "northern"},
    "New Orleans": {"station": "KMSY", "tz": "America/Chicago", "regime": "humid"},
    "New York City": {"station": "KNYC", "tz": "America/New_York", "regime": "northeast"},
    "Oklahoma City": {"station": "KOKC", "tz": "America/Chicago", "regime": "plains"},
    "Philadelphia": {"station": "KPHL", "tz": "America/New_York", "regime": "northeast"},
    "Phoenix": {"station": "KPHX", "tz": "America/Phoenix", "regime": "desert"},
    "San Antonio": {"station": "KSAT", "tz": "America/Chicago", "regime": "humid"},
    "San Francisco": {"station": "KSFO", "tz": "America/Los_Angeles", "regime": "marine"},
    "Seattle/Tacoma": {"station": "KSEA", "tz": "America/Los_Angeles", "regime": "marine"},
    "Washington DC": {"station": "KDCA", "tz": "America/New_York", "regime": "northeast"},
}

NAV_OPTIONS = ["All cities", "Links"] + list(CITIES.keys())

DISPLAY_CITY = {
    "Seattle/Tacoma": "Seattle",
}

DIGITAL_FORECAST_URLS_BY_STATION = {
    "KATL": "https://forecast.weather.gov/MapClick.php?lat=33.6367&lon=-84.4279&lg=english&&FcstType=digital",
    "KAUS": "https://forecast.weather.gov/MapClick.php?lat=30.1945&lon=-97.6699&lg=english&&FcstType=digital",
    "KBOS": "https://forecast.weather.gov/MapClick.php?lat=42.3629&lon=-71.0064&lg=english&&FcstType=digital",
    "KMDW": "https://forecast.weather.gov/MapClick.php?lat=41.7868&lon=-87.7455&lg=english&&FcstType=digital",
    "KDFW": "https://forecast.weather.gov/MapClick.php?lat=32.8972&lon=-97.0377&lg=english&&FcstType=digital",
    "KDEN": "https://forecast.weather.gov/MapClick.php?lat=39.8589&lon=-104.6733&lg=english&&FcstType=digital",
    "KHOU": "https://forecast.weather.gov/MapClick.php?lat=29.6524&lon=-95.2772&lg=english&&FcstType=digital",
    "KLAS": "https://forecast.weather.gov/MapClick.php?lat=36.08&lon=-115.1522&lg=english&&FcstType=digital",
    "KLAX": "https://forecast.weather.gov/MapClick.php?lat=33.9425&lon=-118.409&lg=english&&FcstType=digital",
    "KMIA": "https://forecast.weather.gov/MapClick.php?lat=25.7954&lon=-80.2901&lg=english&&FcstType=digital",
    "KMSP": "https://forecast.weather.gov/MapClick.php?lat=44.882&lon=-93.2218&lg=english&&FcstType=digital",
    "KMSY": "https://forecast.weather.gov/MapClick.php?lat=29.9933&lon=-90.259&lg=english&&FcstType=digital",
    "KNYC": "https://forecast.weather.gov/MapClick.php?lat=40.7834&lon=-73.965&lg=english&&FcstType=digital",
    "KOKC": "https://forecast.weather.gov/MapClick.php?lat=35.3931&lon=-97.6009&lg=english&&FcstType=digital",
    "KPHL": "https://forecast.weather.gov/MapClick.php?lat=39.8721&lon=-75.2407&lg=english&&FcstType=digital",
    "KPHX": "https://forecast.weather.gov/MapClick.php?lat=33.4355&lon=-111.9981&lg=english&&FcstType=digital",
    "KSAT": "https://forecast.weather.gov/MapClick.php?lat=29.5338&lon=-98.47&lg=english&&FcstType=digital",
    "KSFO": "https://forecast.weather.gov/MapClick.php?lat=37.6188&lon=-122.3754&lg=english&&FcstType=digital",
    "KSEA": "https://forecast.weather.gov/MapClick.php?lat=47.4499&lon=-122.3118&lg=english&&FcstType=digital",
    "KDCA": "https://forecast.weather.gov/MapClick.php?lat=38.8514&lon=-77.0377&lg=english&&FcstType=digital",
}

OBSERVED_URLS_BY_STATION = {
    "KATL": "https://forecast.weather.gov/data/obhistory/KATL.html",
    "KAUS": "https://forecast.weather.gov/data/obhistory/KAUS.html",
    "KBOS": "https://forecast.weather.gov/data/obhistory/KBOS.html",
    "KMDW": "https://forecast.weather.gov/data/obhistory/KMDW.html",
    "KDFW": "https://forecast.weather.gov/data/obhistory/KDFW.html",
    "KDEN": "https://forecast.weather.gov/data/obhistory/KDEN.html",
    "KHOU": "https://forecast.weather.gov/data/obhistory/KHOU.html",
    "KLAS": "https://www.weather.gov/wrh/timeseries?site=KLAS",
    "KLAX": "https://www.weather.gov/wrh/timeseries?site=KLAX",
    "KMIA": "https://forecast.weather.gov/data/obhistory/KMIA.html",
    "KMSP": "https://forecast.weather.gov/data/obhistory/KMSP.html",
    "KMSY": "https://forecast.weather.gov/data/obhistory/KMSY.html",
    "KNYC": "https://forecast.weather.gov/data/obhistory/KNYC.html",
    "KOKC": "https://forecast.weather.gov/data/obhistory/KOKC.html",
    "KPHL": "https://forecast.weather.gov/data/obhistory/KPHL.html",
    "KPHX": "https://www.weather.gov/wrh/timeseries?site=KPHX",
    "KSAT": "https://forecast.weather.gov/data/obhistory/KSAT.html",
    "KSFO": "https://www.weather.gov/wrh/timeseries?site=KSFO",
    "KSEA": "https://www.weather.gov/wrh/timeseries?site=KSEA",
    "KDCA": "https://forecast.weather.gov/data/obhistory/KDCA.html",
}

KALSHI_MARKETS = {
    "Atlanta": {"low": ("kxlowtatl", "atlanta-daily-low-temperature"), "high": ("kxhightatl", "atlanta-max-temperature")},
    "Austin": {"low": ("kxlowtaus", "austin-low-temperature"), "high": ("kxhighaus", "highest-temperature-in-austin")},
    "Boston": {"low": ("kxlowtbos", "low-temperature-boston"), "high": ("kxhightbos", "boston-maximum-daily-temperature")},
    "Chicago": {"low": ("kxlowtchi", "chicago-daily-low-temperature"), "high": ("kxhighchi", "highest-temperature-in-chicago")},
    "Dallas": {"low": ("kxlowtdal", "dallas-daily-low-temperature"), "high": ("kxhightdal", "dallas-maximum-temperature")},
    "Denver": {"low": ("kxlowtden", "denver-low-temperature"), "high": ("kxhighden", "highest-temperature-in-denver")},
    "Houston": {"low": ("kxlowthou", "houston-low-temperature"), "high": ("kxhighthou", "houston-max-temperature")},
    "Las Vegas": {"low": ("kxlowtlv", "las-vegas-daily-low-temperature"), "high": ("kxhightlv", "las-vegas-max-daily-temperature")},
    "Los Angeles": {"low": ("kxlowtlax", "los-angeles-low-temperature"), "high": ("kxhighlax", "highest-temperature-in-los-angeles")},
    "Miami": {"low": ("kxlowtmia", "miami-low-temperature"), "high": ("kxhighmia", "highest-temperature-in-miami")},
    "Minneapolis": {"low": ("kxlowtmin", "minneapolis-low-temperature"), "high": ("kxhightmin", "minneapolis-daily-high-temperature")},
    "New Orleans": {"low": ("kxlowtnola", "new-orleans-low-temp-daily"), "high": ("kxhightnola", "new-orleans-max-temp-daily")},
    "New York City": {"low": ("kxlowtnyc", "new-york-city-low-temperature"), "high": ("kxhighny", "highest-temperature-in-nyc")},
    "Oklahoma City": {"low": ("kxlowtokc", "oklahoma-city-low-temperature"), "high": ("kxhightokc", "oklahoma-city-maximum-high-temperature")},
    "Philadelphia": {"low": ("kxlowtphil", "lowest-temperature-in-philadelphia"), "high": ("kxhighphil", "highest-temperature-in-philadelphia")},
    "Phoenix": {"low": ("kxlowtphx", "low-temperature-phoenix"), "high": ("kxhightphx", "high-temperature-phoenix")},
    "San Antonio": {"low": ("kxlowtsatx", "san-antonio-daily-low-temperature"), "high": ("kxhightsatx", "san-antonio-daily-maximum-temperature")},
    "San Francisco": {"low": ("kxlowtsfo", "san-francisco-low-temperature"), "high": ("kxhightsfo", "san-francisco-high-temperature-daily")},
    "Seattle/Tacoma": {"low": ("kxlowtsea", "seattle-low-temperature"), "high": ("kxhightsea", "seattle-maximum-temperature-daily")},
    "Washington DC": {"low": ("kxlowtdc", "washington-dc-low-temperature"), "high": ("kxhightdc", "washington-dc-daily-max-temp")},
}

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1120px; }
    h1 { margin-top: 0rem; }
    div[data-testid="stMetricValue"] { font-size: 2.1rem; }
    div[data-testid="stMetricDelta"] { font-size: .85rem; }
    .city-meta { color: #b8bec9; font-size: 0.9rem; margin-top: .15rem; margin-bottom: 1rem; }
    .heat-card { border-radius: 14px; padding: 16px 18px; margin: 12px 0 14px 0; font-weight: 700; }
    .heat-card small { display:block; font-weight:500; margin-top: 8px; color: rgba(255,255,255,.92); }
    .retention { background: linear-gradient(90deg, #9d2b16, #c35b00); border: 1px solid #ffb000; }
    .loss { background: linear-gradient(90deg, #064e8a, #0873b8); border: 1px solid #4cc9f0; }
    .neutral { background: linear-gradient(90deg, #343a46, #4b5563); border: 1px solid #9ca3af; }
    .source-pill { font-size: .78rem; color: #b8bec9; }
    div[data-testid="stBaseButton-pills"] button,
    div[data-testid="stButton"] button {
        border-radius: 999px;
    }
    @media (max-width: 700px) {
        .block-container { padding-left: .75rem; padding-right: .75rem; padding-top: .6rem; max-width: 100%; }
        h1 { font-size: 1.85rem !important; line-height: 1.05; }
        h2 { font-size: 1.28rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.9rem; }
        .city-meta { font-size: 0.82rem; line-height: 1.45; }
        .heat-card { padding: 14px 15px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers
# -----------------------------
def safe_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value).strip()
    if text in {"", "-", "--", "M", "nan", "None"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def safe_int(value):
    number = safe_float(value)
    if number is None:
        return None
    return int(round(number))


def fmt_temp(value):
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}°F"
    return f"{value:.1f}°F"


def fmt_hour(dt):
    if not isinstance(dt, datetime):
        return "N/A"
    return dt.strftime("%-I:%M %p")


def display_city(city_name):
    return DISPLAY_CITY.get(city_name, city_name)


def local_now(tz_name):
    return datetime.now(ZoneInfo(tz_name))


def get_query_city():
    try:
        city = st.query_params.get("city")
    except Exception:
        params = st.experimental_get_query_params()
        value = params.get("city")
        city = value[0] if isinstance(value, list) and value else value
    return city if city in CITIES else None


def set_query_city(city):
    try:
        st.query_params["city"] = city
    except Exception:
        st.experimental_set_query_params(city=city)


def choose_view():
    query_city = get_query_city()

    if "selected_view" not in st.session_state:
        st.session_state.selected_view = query_city or "Atlanta"
    if "selected_city" not in st.session_state:
        st.session_state.selected_city = query_city or "Atlanta"

    last_synced_city = st.session_state.get("_last_synced_city")
    if query_city and query_city != last_synced_city and query_city != st.session_state.selected_city:
        st.session_state.selected_city = query_city
        st.session_state.selected_view = query_city

    if st.session_state.selected_city not in CITIES:
        st.session_state.selected_city = "Atlanta"
    if st.session_state.selected_view not in NAV_OPTIONS:
        st.session_state.selected_view = st.session_state.selected_city

    if hasattr(st, "pills"):
        selected_view = st.pills(
            "City",
            NAV_OPTIONS,
            default=st.session_state.selected_view,
            key="view_picker",
        )
        selected_view = selected_view or st.session_state.selected_view
    elif hasattr(st, "segmented_control"):
        selected_view = st.segmented_control(
            "City",
            NAV_OPTIONS,
            default=st.session_state.selected_view,
            key="view_picker",
        )
        selected_view = selected_view or st.session_state.selected_view
    else:
        selected_view = st.radio(
            "City",
            NAV_OPTIONS,
            key="selected_view",
        )

    st.session_state.selected_view = selected_view

    if selected_view in CITIES:
        st.session_state.selected_city = selected_view
        if get_query_city() != selected_view:
            set_query_city(selected_view)
        st.session_state._last_synced_city = selected_view

    return selected_view


def parse_wind_speed(text):
    if text is None:
        return None
    numbers = re.findall(r"\d+", str(text))
    if not numbers:
        return None
    vals = [int(x) for x in numbers]
    return max(vals) if vals else None


def c_to_f(c):
    if c is None:
        return None
    return float(c) * 9 / 5 + 32


def mps_to_mph(value):
    if value is None:
        return None
    return float(value) * 2.23694


def degrees_to_compass(degrees):
    if degrees is None:
        return "-"
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return directions[round(float(degrees) / 22.5) % 16]


def get_nested_value(obj, key):
    val = obj.get(key)
    if isinstance(val, dict):
        val = val.get("value")
    return val


def find_row(table, words):
    for _, row in table.iterrows():
        label = " ".join(str(v) for v in row.iloc[:2].tolist()).lower()
        if all(word in label for word in words):
            return row.tolist()
    return None


def parse_mmdd_date(value, year):
    text = str(value).strip()
    match = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    return datetime(year, month, day).date()


def clean_link_date(dt):
    return dt.strftime("%y%b%d").lower()


def tomorrow_contract_date():
    return local_now("America/New_York").date() + timedelta(days=1)


def parse_valid_time(valid_time):
    start_text, duration_text = valid_time.split("/")
    start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
    days = 0
    hours = 0
    minutes = 0
    day_match = re.search(r"P(\d+)D", duration_text)
    time_match = re.search(r"T(?:(\d+)H)?(?:(\d+)M)?", duration_text)
    if day_match:
        days = int(day_match.group(1))
    if time_match:
        hours = int(time_match.group(1) or 0)
        minutes = int(time_match.group(2) or 0)
    return start, start + timedelta(days=days, hours=hours, minutes=minutes)


def value_at_hour(values, hour):
    for item in values or []:
        start, end = parse_valid_time(item["validTime"])
        if start <= hour < end:
            return item.get("value")
    return None


def parse_digital_hour(value):
    text = str(value).strip()
    match = re.search(r"\d{1,2}", text)
    if not match:
        return None
    hour = int(match.group(0))
    return hour if 0 <= hour <= 23 else None


def kph_to_mph(value):
    if value is None:
        return None
    return float(value) * 0.621371

# -----------------------------
# NWS fetchers
# -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_station_point(station):
    response = requests.get(f"https://api.weather.gov/stations/{station}", headers=NWS_HEADERS, timeout=20)
    response.raise_for_status()
    coords = response.json()["geometry"]["coordinates"]
    lon, lat = coords[0], coords[1]
    return lat, lon


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_point_urls_for_station(station):
    lat, lon = fetch_station_point(station)
    points = requests.get(f"https://api.weather.gov/points/{lat},{lon}", headers=NWS_HEADERS, timeout=20)
    points.raise_for_status()
    props = points.json()["properties"]
    return {
        "lat": lat,
        "lon": lon,
        "forecast": props["forecast"],
        "forecastHourly": props["forecastHourly"],
        "forecastGridData": props["forecastGridData"],
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_grid_forecast(station, tz_name):
    urls = fetch_point_urls_for_station(station)
    response = requests.get(urls["forecastGridData"], headers=NWS_HEADERS, timeout=30)
    response.raise_for_status()
    props = response.json()["properties"]
    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)
    start = datetime.combine(now.date(), time.min, tzinfo=tz)
    hours = [start + timedelta(hours=i) for i in range(72)]
    rows = []

    for hour in hours:
        hour_utc = hour.astimezone(ZoneInfo("UTC"))
        temp_c = value_at_hour(props.get("temperature", {}).get("values"), hour_utc)
        dew_c = value_at_hour(props.get("dewpoint", {}).get("values"), hour_utc)
        heat_c = value_at_hour(props.get("heatIndex", {}).get("values"), hour_utc)
        humidity = value_at_hour(props.get("relativeHumidity", {}).get("values"), hour_utc)
        pop = value_at_hour(props.get("probabilityOfPrecipitation", {}).get("values"), hour_utc)
        sky = value_at_hour(props.get("skyCover", {}).get("values"), hour_utc)
        wind_kph = value_at_hour(props.get("windSpeed", {}).get("values"), hour_utc)
        gust_kph = value_at_hour(props.get("windGust", {}).get("values"), hour_utc)
        wind_dir = value_at_hour(props.get("windDirection", {}).get("values"), hour_utc)
        thunder = value_at_hour(props.get("probabilityOfThunder", {}).get("values"), hour_utc)
        temp = c_to_f(temp_c)
        if hour is None or temp is None:
            continue

        rows.append({
            "datetime": hour,
            "date": hour.date(),
            "hour": hour.hour,
            "time": hour.strftime("%a %-I %p"),
            "source": "FORECAST",
            "temp": temp,
            "dewpoint": c_to_f(dew_c),
            "heat_index": c_to_f(heat_c) if heat_c is not None else temp,
            "wind_mph": kph_to_mph(wind_kph),
            "wind_dir": degrees_to_compass(wind_dir),
            "gust_mph": kph_to_mph(gust_kph),
            "sky_cover": safe_float(sky),
            "precip": safe_float(pop),
            "humidity": safe_float(humidity),
            "rain": "Yes" if safe_float(pop) is not None and safe_float(pop) >= 50 else "-",
            "thunder": "Yes" if safe_float(thunder) is not None and safe_float(thunder) >= 15 else "-",
            "description": "NWS grid forecast",
        })

    if not rows:
        raise ValueError("No grid forecast rows parsed")
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_api_hourly_forecast(station, tz_name):
    urls = fetch_point_urls_for_station(station)
    hourly_url = urls["forecastHourly"]

    response = requests.get(hourly_url, headers=NWS_HEADERS, timeout=30)
    response.raise_for_status()
    periods = response.json()["properties"]["periods"]
    tz = ZoneInfo(tz_name)
    rows = []
    for p in periods:
        dt = datetime.fromisoformat(p["startTime"].replace("Z", "+00:00")).astimezone(tz)
        temp = safe_float(p.get("temperature"))
        dew_c = get_nested_value(p, "dewpoint")
        rh = get_nested_value(p, "relativeHumidity")
        precip = get_nested_value(p, "probabilityOfPrecipitation")
        wind_mph = parse_wind_speed(p.get("windSpeed"))
        desc = p.get("shortForecast") or ""
        rows.append({
            "datetime": dt,
            "date": dt.date(),
            "hour": dt.hour,
            "time": dt.strftime("%a %-I %p"),
            "source": "FORECAST",
            "temp": temp,
            "dewpoint": c_to_f(dew_c),
            "heat_index": temp,  # NWS hourly API usually does not provide heat index directly
            "wind_mph": wind_mph,
            "wind_dir": p.get("windDirection", "-"),
            "gust_mph": None,
            "sky_cover": None,
            "precip": safe_float(precip),
            "humidity": safe_float(rh),
            "rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() else "-",
            "thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "description": desc,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hourly_forecast(station, tz_name):
    try:
        return fetch_grid_forecast(station, tz_name)
    except Exception:
        return fetch_api_hourly_forecast(station, tz_name)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_digital_forecast(station, tz_name):
    url = DIGITAL_FORECAST_URLS_BY_STATION.get(station)
    if not url:
        lat, lon = fetch_station_point(station)
        url = f"https://forecast.weather.gov/MapClick.php?lat={lat:.4f}&lon={lon:.4f}&lg=english&&FcstType=digital"
    response = requests.get(url, headers=NWS_HEADERS, timeout=30)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)

    for table in tables:
        clean = table.astype(str).replace({"nan": ""})
        date_row = hour_row = temp_row = None
        dew_row = heat_row = wind_row = wind_dir_row = gust_row = sky_row = precip_row = humidity_row = rain_row = thunder_row = None
        for _, row in clean.iterrows():
            row_text = " ".join(str(v) for v in row.tolist()).lower()
            first_cells = " ".join(str(v) for v in row.iloc[:2].tolist()).lower()
            if "date" in first_cells and date_row is None:
                date_row = row.tolist()
            elif "hour" in first_cells and hour_row is None:
                hour_row = row.tolist()
            elif "temperature" in row_text and "dewpoint" not in row_text and temp_row is None:
                temp_row = row.tolist()
            elif "dewpoint" in row_text and dew_row is None:
                dew_row = row.tolist()
            elif "heat index" in row_text and heat_row is None:
                heat_row = row.tolist()
            elif "surface wind" in row_text and wind_row is None:
                wind_row = row.tolist()
            elif "wind dir" in row_text and wind_dir_row is None:
                wind_dir_row = row.tolist()
            elif "gust" in row_text and gust_row is None:
                gust_row = row.tolist()
            elif "sky cover" in row_text and sky_row is None:
                sky_row = row.tolist()
            elif "precipitation" in row_text and precip_row is None:
                precip_row = row.tolist()
            elif "relative" in row_text and "humidity" in row_text and humidity_row is None:
                humidity_row = row.tolist()
            elif "rain" in first_cells and rain_row is None:
                rain_row = row.tolist()
            elif "thunder" in first_cells and thunder_row is None:
                thunder_row = row.tolist()

        if date_row is None or hour_row is None or temp_row is None:
            continue

        rows = []
        current_date = None
        width = max(len(date_row), len(hour_row), len(temp_row))
        for col in range(1, width):
            date_val = date_row[col] if col < len(date_row) else ""
            parsed_date = parse_mmdd_date(date_val, now.year)
            if parsed_date is not None:
                current_date = parsed_date
            if current_date is None:
                continue

            hour_val = hour_row[col] if col < len(hour_row) else ""
            temp_val = temp_row[col] if col < len(temp_row) else None
            hour = parse_digital_hour(hour_val)
            temp = safe_float(temp_val)
            if hour is None or temp is None:
                continue

            dt = datetime.combine(current_date, time(hour), tzinfo=tz)
            dewpoint = safe_float(dew_row[col]) if dew_row and col < len(dew_row) else None
            heat_index = safe_float(heat_row[col]) if heat_row and col < len(heat_row) else None
            wind_mph = safe_float(wind_row[col]) if wind_row and col < len(wind_row) else None
            gust_mph = safe_float(gust_row[col]) if gust_row and col < len(gust_row) else None
            sky_cover = safe_float(sky_row[col]) if sky_row and col < len(sky_row) else None
            precip = safe_float(precip_row[col]) if precip_row and col < len(precip_row) else None
            humidity = safe_float(humidity_row[col]) if humidity_row and col < len(humidity_row) else None
            wind_dir = str(wind_dir_row[col]).strip() if wind_dir_row and col < len(wind_dir_row) else "-"
            rain = str(rain_row[col]).strip() if rain_row and col < len(rain_row) else "-"
            thunder = str(thunder_row[col]).strip() if thunder_row and col < len(thunder_row) else "-"
            rows.append({
                "datetime": dt,
                "date": dt.date(),
                "hour": hour,
                "time": dt.strftime("%a %-I %p"),
                "source": "FORECAST",
                "temp": temp,
                "dewpoint": dewpoint,
                "heat_index": heat_index if heat_index is not None else temp,
                "wind_mph": wind_mph,
                "wind_dir": wind_dir,
                "gust_mph": gust_mph,
                "sky_cover": sky_cover,
                "precip": precip,
                "humidity": humidity,
                "rain": rain if rain and rain.lower() != "nan" else "-",
                "thunder": thunder if thunder and thunder.lower() != "nan" else "-",
                "description": "NWS digital forecast",
            })

        if rows:
            return pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)

    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_daily_forecast(station, tz_name):
    urls = fetch_point_urls_for_station(station)
    response = requests.get(urls["forecast"], headers=NWS_HEADERS, timeout=30)
    response.raise_for_status()
    periods = response.json()["properties"]["periods"]
    tz = ZoneInfo(tz_name)
    rows = []

    for p in periods:
        start_dt = datetime.fromisoformat(p["startTime"].replace("Z", "+00:00")).astimezone(tz)
        rows.append({
            "datetime": start_dt,
            "date": start_dt.date(),
            "name": p.get("name", ""),
            "source": "FORECAST",
            "temp": safe_float(p.get("temperature")),
            "is_daytime": bool(p.get("isDaytime")),
            "wind_mph": parse_wind_speed(p.get("windSpeed")),
            "wind_dir": p.get("windDirection", "-"),
            "description": p.get("shortForecast") or p.get("detailedForecast") or "",
        })
    return pd.DataFrame(rows)


def daily_high_for_date(daily_df, target_date):
    if daily_df.empty:
        return None
    rows = daily_df[
        (daily_df["date"] == target_date)
        & (daily_df["is_daytime"] == True)
        & daily_df["temp"].notna()
    ].copy()
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def official_projected_high(obs_df, hourly_df, daily_df, target_date, tz_name):
    hourly_hi, _ = projected_extremes_for_date(obs_df, hourly_df, target_date, tz_name)
    daily_hi = daily_high_for_date(daily_df, target_date)
    if daily_hi is None:
        return hourly_hi

    now = local_now(tz_name)
    if target_date == now.date() and not obs_df.empty:
        observed_today = obs_df[
            (obs_df["date"] == target_date)
            & obs_df["temp"].notna()
            & (obs_df["datetime"] <= now)
        ].copy()
        if not observed_today.empty:
            observed_hi = observed_today.loc[observed_today["temp"].idxmax()].to_dict()
            if safe_float(observed_hi.get("temp")) is not None and safe_float(observed_hi.get("temp")) >= safe_float(daily_hi.get("temp")):
                return observed_hi

    if hourly_hi is None:
        return daily_hi
    if safe_float(daily_hi.get("temp")) is None:
        return hourly_hi
    if safe_float(hourly_hi.get("temp")) is None:
        return daily_hi
    return daily_hi if safe_float(daily_hi["temp"]) >= safe_float(hourly_hi["temp"]) else hourly_hi


def _parse_obhistory_html(html_text):
    tables = pd.read_html(StringIO(html_text))
    for table in tables:
        table.columns = [
            " ".join(str(part).strip() for part in col if str(part).strip() and not str(part).startswith("Unnamed"))
            if isinstance(col, tuple)
            else str(col).strip()
            for col in table.columns
        ]
        joined = " ".join(table.columns).lower()
        if "date" in joined and "time" in joined and ("temp" in joined or "air" in joined):
            return table
    return pd.DataFrame()


def _parse_wrh_timeseries_html(html_text):
    tables = pd.read_html(StringIO(html_text))
    for table in tables:
        table.columns = [
            " ".join(str(part).strip() for part in col if str(part).strip() and not str(part).startswith("Unnamed"))
            if isinstance(col, tuple)
            else str(col).strip()
            for col in table.columns
        ]
        joined = " ".join(table.columns).lower()
        if "temp" in joined and ("date" in joined or "time" in joined):
            return table
    return pd.DataFrame()


def parse_obhistory_datetime(raw_dt, now, tz):
    text = str(raw_dt).replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+(EDT|EST|CDT|CST|MDT|MST|PDT|PST|MST|AKDT|AKST|HST)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(am|pm)\b", lambda m: m.group(1).upper(), text, flags=re.IGNORECASE)

    day_hour_match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if day_hour_match:
        day = int(day_hour_match.group(1))
        hour = int(day_hour_match.group(2))
        minute = int(day_hour_match.group(3))
        try:
            parsed = datetime(now.year, now.month, day, hour, minute, tzinfo=tz)
            if parsed - now > timedelta(days=2):
                previous_month = (now.replace(day=1) - timedelta(days=1))
                parsed = parsed.replace(year=previous_month.year, month=previous_month.month)
            return parsed
        except Exception:
            pass

    formats = [
        "%d %b %I:%M %p",
        "%d %B %I:%M %p",
        "%d %I:%M %p",
        "%d %H:%M",
        "%b %d %I:%M %p",
        "%B %d %I:%M %p",
        "%b %d, %I:%M %p",
        "%B %d, %I:%M %p",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
    ]

    for fmt in formats:
        try:
            dt_naive = datetime.strptime(text, fmt)
            if dt_naive.year == 1900:
                dt_naive = dt_naive.replace(year=now.year)
            parsed = dt_naive.replace(tzinfo=tz)
            if parsed - now > timedelta(days=30):
                parsed = parsed.replace(year=parsed.year - 1)
            return parsed
        except Exception:
            continue

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    dt_naive = parsed.to_pydatetime()
    if dt_naive.year == 1900:
        dt_naive = dt_naive.replace(year=now.year)
    if dt_naive.tzinfo is None:
        parsed_dt = dt_naive.replace(tzinfo=tz)
    else:
        parsed_dt = dt_naive.astimezone(tz)
    if parsed_dt - now > timedelta(days=30):
        parsed_dt = parsed_dt.replace(year=parsed_dt.year - 1)
    return parsed_dt


@st.cache_data(ttl=900, show_spinner=False)
def fetch_observations_api(station, tz_name):
    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)
    start = datetime.combine(now.date(), time.min, tzinfo=tz)
    url = f"https://api.weather.gov/stations/{station}/observations"
    response = requests.get(
        url,
        headers=NWS_HEADERS,
        params={"start": start.isoformat(), "end": now.isoformat()},
        timeout=20,
    )
    response.raise_for_status()

    rows = []
    for feature in response.json().get("features", []):
        props = feature.get("properties", {})
        timestamp = props.get("timestamp")
        if not timestamp:
            continue

        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(tz)
        temp = c_to_f(get_nested_value(props, "temperature"))
        if temp is None:
            continue

        dew = c_to_f(get_nested_value(props, "dewpoint"))
        rh = safe_float(get_nested_value(props, "relativeHumidity"))
        wind = mps_to_mph(get_nested_value(props, "windSpeed"))
        gust = mps_to_mph(get_nested_value(props, "windGust"))
        wind_dir = degrees_to_compass(get_nested_value(props, "windDirection"))
        desc = props.get("textDescription") or "Observed"

        rows.append({
            "datetime": parsed,
            "date": parsed.date(),
            "hour": parsed.hour,
            "time": parsed.strftime("%a %-I:%M %p"),
            "source": "OBSERVED",
            "temp": temp,
            "dewpoint": dew,
            "heat_index": temp,
            "wind_mph": wind,
            "wind_dir": wind_dir,
            "gust_mph": gust,
            "sky_cover": None,
            "precip": None,
            "humidity": rh,
            "rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() else "-",
            "thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "description": desc,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("datetime").reset_index(drop=True)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_observations_for_day(station, tz_name, target_date):
    tz = ZoneInfo(tz_name)
    start = datetime.combine(target_date, time.min, tzinfo=tz)
    end = datetime.combine(target_date, time(23, 59), tzinfo=tz)
    url = f"https://api.weather.gov/stations/{station}/observations"
    response = requests.get(
        url,
        headers=NWS_HEADERS,
        params={"start": start.isoformat(), "end": end.isoformat(), "limit": 500},
        timeout=25,
    )
    response.raise_for_status()

    rows = []
    for feature in response.json().get("features", []):
        props = feature.get("properties", {})
        timestamp = props.get("timestamp")
        if not timestamp:
            continue
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(tz)
        temp = c_to_f(get_nested_value(props, "temperature"))
        if temp is None:
            continue
        rows.append({
            "datetime": parsed,
            "date": parsed.date(),
            "temp": temp,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("datetime").reset_index(drop=True)
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_obhistory(station, tz_name):
    url = OBSERVED_URLS_BY_STATION.get(station, f"https://forecast.weather.gov/data/obhistory/{station}.html")
    try:
        response = requests.get(url, headers={"User-Agent": NWS_HEADERS["User-Agent"]}, timeout=25)
        response.raise_for_status()
    except Exception:
        return pd.DataFrame()

    try:
        if "wrh/timeseries" in url:
            df = _parse_wrh_timeseries_html(response.text)
        else:
            df = _parse_obhistory_html(response.text)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]

    def find_col(options):
        for option in options:
            for col in df.columns:
                low = col.lower()
                if all(part in low for part in option):
                    return col
        return None

    date_col = find_col([["date", "time"], ["date"]])
    time_col = find_col([["time"]])
    temp_col = find_col([["temperature", "air"], ["temp", "air"], ["temp"], ["air"]])
    dew_col = find_col([["dew"]])
    rh_col = find_col([["relative", "humidity"], ["humidity"]])
    heat_col = find_col([["heat", "index"]])
    wind_dir_col = find_col([["wind", "direction"], ["wind", "dir"]])
    wind_speed_col = find_col([["wind", "speed"]])
    clouds_col = find_col([["cloud"]])
    weather_col = find_col([["weather"]])

    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)
    rows = []

    for _, r in df.iterrows():
        raw_dt = str(r.get(date_col, "")).strip() if date_col else ""
        if date_col and time_col and date_col != time_col and raw_dt and raw_dt.lower() != "nan":
            raw_time = str(r.get(time_col, "")).strip()
            if raw_time and raw_time.lower() != "nan" and raw_time not in raw_dt:
                raw_dt = f"{raw_dt} {raw_time}"
        if not raw_dt or raw_dt.lower() == "nan":
            continue

        parsed = parse_obhistory_datetime(raw_dt, now, tz)
        if parsed is None:
            continue

        temp = safe_float(r.get(temp_col)) if temp_col else None
        if temp is None:
            continue

        dew = safe_float(r.get(dew_col)) if dew_col else None
        rh = safe_float(r.get(rh_col)) if rh_col else None
        heat = safe_float(r.get(heat_col)) if heat_col else temp
        wind = safe_float(r.get(wind_speed_col)) if wind_speed_col else None
        desc = str(r.get(weather_col, "-")) if weather_col else "-"
        clouds = str(r.get(clouds_col, "-")) if clouds_col else "-"

        rows.append({
            "datetime": parsed,
            "date": parsed.date(),
            "hour": parsed.hour,
            "time": parsed.strftime("%a %-I:%M %p"),
            "source": "OBSERVED",
            "temp": temp,
            "dewpoint": dew,
            "heat_index": heat if heat is not None else temp,
            "wind_mph": wind,
            "wind_dir": str(r.get(wind_dir_col, "-")) if wind_dir_col else "-",
            "gust_mph": None,
            "sky_cover": None,
            "precip": None,
            "humidity": rh,
            "rain": "Yes" if "rain" in desc.lower() else "-",
            "thunder": "Yes" if "thunder" in desc.lower() else "-",
            "description": desc if desc not in ["nan", "", "None"] else clouds,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("datetime").reset_index(drop=True)
    else:
        out = pd.DataFrame()
    return out

# -----------------------------
# Analytics
# -----------------------------
def score_heat_regime(row, city_regime):
    if row is None or len(row) == 0:
        return "Neutral", 0, "neutral", "not enough data"

    score = 0
    reasons = []
    temp = safe_float(row.get("temp"))
    dew = safe_float(row.get("dewpoint"))
    heat_index = safe_float(row.get("heat_index"))
    wind = safe_float(row.get("wind_mph"))
    gust = safe_float(row.get("gust_mph"))
    sky = safe_float(row.get("sky_cover"))
    precip = safe_float(row.get("precip"))
    humidity = safe_float(row.get("humidity"))
    rain = str(row.get("rain", "-")).lower()
    thunder = str(row.get("thunder", "-")).lower()

    if dew is not None:
        if dew >= 70:
            score += 3; reasons.append("very high dewpoint")
        elif dew >= 65:
            score += 2; reasons.append("high dewpoint")
        elif dew <= 40:
            score -= 2; reasons.append("dry air")
        elif dew <= 50:
            score -= 1; reasons.append("moderately dry air")

    if humidity is not None:
        if humidity >= 85:
            score += 2; reasons.append("high humidity")
        elif humidity >= 70:
            score += 1; reasons.append("moderate humidity")
        elif humidity <= 40:
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

    if gust is not None and gust >= 20:
        score += 1; reasons.append("gust mixing")

    if precip is not None:
        if precip >= 50:
            score += 2; reasons.append("high precip risk")
        elif precip >= 25:
            score += 1; reasons.append("some precip risk")

    if rain not in ["-", "--", "none", "nan", ""]:
        score += 2; reasons.append("rain")
    if thunder not in ["-", "--", "none", "nan", ""]:
        score += 1; reasons.append("thunder")

    if heat_index is not None and temp is not None:
        if heat_index - temp >= 5:
            score += 2; reasons.append("heat index above temp")
        elif heat_index > temp:
            score += 1; reasons.append("humid heat index")

    if city_regime == "humid":
        score += 1; reasons.append("humid city")
    elif city_regime == "desert":
        score -= 1; reasons.append("desert city")
    elif city_regime == "marine":
        score += 1; reasons.append("marine layer")
    elif city_regime == "elevation":
        score -= 1; reasons.append("elevation cooling")

    if score >= 2:
        return "HEAT RETENTION", score, "retention", ", ".join(reasons[:4])
    if score <= -2:
        return "HEAT LOSS", score, "loss", ", ".join(reasons[:4])
    return "NEUTRAL", score, "neutral", ", ".join(reasons[:4]) if reasons else "mixed signals"


def confidence_for_event(event_dt, event_type, row, city_regime):
    if row is not None and str(row.get("source", "")).upper() == "OBSERVED":
        return 100

    now = local_now(event_dt.tzinfo.key if hasattr(event_dt.tzinfo, "key") else "UTC")
    hours = max(0, (event_dt - now).total_seconds() / 3600)
    if hours <= 2: base = 88
    elif hours <= 4: base = 84
    elif hours <= 8: base = 78
    elif hours <= 12: base = 72
    elif hours <= 18: base = 66
    elif hours <= 24: base = 60
    elif hours <= 36: base = 55
    else: base = 50

    label, score, _, _ = score_heat_regime(row, city_regime)
    adj = 0
    if event_type == "low":
        if label == "HEAT RETENTION": adj += 4
        elif label == "HEAT LOSS": adj -= 4
    else:
        # For highs, heat loss/retention is less direct. Keep adjustment small.
        if city_regime == "desert": adj -= 2
        if row is not None and safe_float(row.get("precip")) and safe_float(row.get("precip")) >= 40: adj -= 4
        if row is not None and safe_float(row.get("sky_cover")) and safe_float(row.get("sky_cover")) >= 70: adj -= 3

    return int(max(35, min(100, base + adj)))


def build_timeline(obs_df, fc_df, tz_name):
    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)
    start = datetime.combine(now.date(), time.min, tzinfo=tz)
    end = datetime.combine(now.date() + timedelta(days=1), time(23, 59), tzinfo=tz)

    # Observation history is sub-hourly. Keep raw observed rows for today's past, not aggregated only hourly.
    obs_today = obs_df[(obs_df["datetime"] >= start) & (obs_df["datetime"] <= now)].copy() if not obs_df.empty else pd.DataFrame()

    # Forecast future from next available hour forward through tomorrow.
    fc_future = fc_df[(fc_df["datetime"] > now) & (fc_df["datetime"] <= end)].copy() if not fc_df.empty else pd.DataFrame()

    timeline = pd.concat([obs_today, fc_future], ignore_index=True)
    if not timeline.empty:
        timeline = timeline.sort_values("datetime").reset_index(drop=True)
    return timeline


def extremes_for_date(timeline, target_date):
    day = timeline[timeline["date"] == target_date].copy()
    if day.empty:
        return None, None
    valid = day.dropna(subset=["temp"])
    if valid.empty:
        return None, None
    hi_row = valid.loc[valid["temp"].idxmax()].to_dict()
    lo_row = valid.loc[valid["temp"].idxmin()].to_dict()
    return hi_row, lo_row


def projected_extremes_for_date(obs_df, fc_df, target_date, tz_name):
    tz = ZoneInfo(tz_name)
    now = local_now(tz_name)
    start = datetime.combine(target_date, time.min, tzinfo=tz)
    end = datetime.combine(target_date, time(23, 59), tzinfo=tz)

    if target_date == now.date():
        observed_today = obs_df[
            (obs_df["datetime"] >= start) & (obs_df["datetime"] <= now)
        ].copy() if not obs_df.empty else pd.DataFrame()
        forecast_rest_today = fc_df[
            (fc_df["datetime"] > now) & (fc_df["datetime"] <= end)
        ].copy() if not fc_df.empty else pd.DataFrame()
        candidates = pd.concat([observed_today, forecast_rest_today], ignore_index=True)
    else:
        candidates = fc_df[
            (fc_df["datetime"] >= start) & (fc_df["datetime"] <= end)
        ].copy() if not fc_df.empty else pd.DataFrame()

    if candidates.empty:
        return None, None

    valid = candidates.dropna(subset=["temp"])
    if valid.empty:
        return None, None

    hi_row = valid.loc[valid["temp"].idxmax()].to_dict()
    lo_row = valid.loc[valid["temp"].idxmin()].to_dict()
    return hi_row, lo_row


def summary_row_for_city(city_name):
    cfg = CITIES[city_name]
    tz_name = cfg["tz"]
    now = local_now(tz_name)
    tomorrow = now.date() + timedelta(days=1)

    digital_df = fetch_digital_forecast(cfg["station"], tz_name)
    digital_rows = digital_df[digital_df["date"] == tomorrow].dropna(subset=["temp"]) if not digital_df.empty else pd.DataFrame()

    return {
        "City": display_city(city_name),
        "Digital Tomorrow Max": safe_int(digital_rows["temp"].max()) if not digital_rows.empty else None,
        "Digital Tomorrow Min": safe_int(digital_rows["temp"].min()) if not digital_rows.empty else None,
    }


def kalshi_url(city_name, side, contract_date):
    ticker, slug = KALSHI_MARKETS[city_name][side]
    date_code = clean_link_date(contract_date)
    return f"https://kalshi.com/markets/{ticker}/{slug}/{ticker}-{date_code}"


def kalshi_links_table(contract_date):
    rows = []
    for city_name in CITIES:
        name = display_city(city_name)
        rows.append({
            "City": name,
            "Low Tomorrow": f"{name} Low",
            "High Tomorrow": f"{name} High",
            "_Low Tomorrow URL": kalshi_url(city_name, "low", contract_date),
            "_High Tomorrow URL": kalshi_url(city_name, "high", contract_date),
        })
    return pd.DataFrame(rows)


def render_all_cities():
    now = local_now("America/New_York")
    left, center, right = st.columns([1, 2, 1])
    with left:
        st.markdown(
            f'<div style="text-align:left; color:#b8bec9; font-weight:700; padding-top:.4rem;">{now.strftime("%b %-d, %Y · %-I:%M %p %Z")}</div>',
            unsafe_allow_html=True,
        )
    with center:
        st.markdown('<h2 style="text-align:center; margin-top:0;">All cities</h2>', unsafe_allow_html=True)

    with st.spinner("Loading all cities from NWS..."):
        results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_city = {executor.submit(summary_row_for_city, city_name): city_name for city_name in CITIES}
            for future in as_completed(future_to_city):
                city_name = future_to_city[future]
                try:
                    results[city_name] = future.result()
                except Exception:
                    results[city_name] = {
                        "City": display_city(city_name),
                        "Digital Tomorrow Max": None,
                        "Digital Tomorrow Min": None,
                    }
        rows = [results[city_name] for city_name in CITIES]
    df = pd.DataFrame(rows)
    table_style = "width:100%; border-collapse:separate; border-spacing:0; font-size:0.95rem; overflow:hidden; border:1px solid #303746; border-radius:8px;"
    th = "background:#1b1f2a; border-bottom:1px solid #303746; padding:9px 10px; text-align:center; font-weight:800;"
    td = "border-bottom:1px solid #303746; padding:7px 10px; text-align:center; font-weight:700;"
    html = [
        f'<table style="{table_style}">',
        "<thead>",
        "<tr>",
        f'<th style="{th}">City</th>',
        f'<th style="{th}">Digital Tomorrow Max</th>',
        f'<th style="{th}">Digital Tomorrow Min</th>',
        "</tr>",
        "</thead>",
        "<tbody>",
    ]
    for _, row in df.iterrows():
        max_temp = "" if pd.isna(row["Digital Tomorrow Max"]) else int(row["Digital Tomorrow Max"])
        min_temp = "" if pd.isna(row["Digital Tomorrow Min"]) else int(row["Digital Tomorrow Min"])
        html.extend([
            "<tr>",
            f'<td style="{td}">{escape(str(row["City"]))}</td>',
            f'<td style="{td}">{max_temp}</td>',
            f'<td style="{td}">{min_temp}</td>',
            "</tr>",
        ])
    html.extend(["</tbody>", "</table>"])
    st.markdown("".join(html), unsafe_allow_html=True)


def render_links():
    st.markdown('<h2 style="text-align:center;">Links</h2>', unsafe_allow_html=True)
    contract_date = tomorrow_contract_date()
    date_code = clean_link_date(contract_date)
    st.markdown(
        f'<div style="text-align:center; color:#b8bec9; font-weight:700; margin-top:-.35rem; margin-bottom:1rem;">Tomorrow contract date: {contract_date.strftime("%b %-d, %Y")} · {date_code}</div>',
        unsafe_allow_html=True,
    )
    df = kalshi_links_table(contract_date)
    table_style = "width:100%; border-collapse:collapse; font-size:0.95rem; text-align:center;"
    th = "border:1px solid #303746; padding:4px; text-align:center;"
    td = "border:1px solid #303746; padding:3px; text-align:center;"
    html = [
        f'<table style="{table_style}">',
        "<thead>",
        "<tr>",
        f'<th style="{th}">City</th>',
        f'<th style="{th}">Low Tomorrow</th>',
        f'<th style="{th}">High Tomorrow</th>',
        "</tr>",
        "</thead>",
        "<tbody>",
    ]
    for _, row in df.iterrows():
        html.extend([
            "<tr>",
            f'<td style="{td}">{escape(str(row["City"]))}</td>',
            f'<td style="{td}"><a href="{escape(row["_Low Tomorrow URL"])}" target="_blank">{escape(row["Low Tomorrow"])}</a></td>',
            f'<td style="{td}"><a href="{escape(row["_High Tomorrow URL"])}" target="_blank">{escape(row["High Tomorrow"])}</a></td>',
            "</tr>",
        ])
    html.extend(["</tbody>", "</table>"])
    st.markdown("".join(html), unsafe_allow_html=True)


def plot_temperature(timeline, today_hi, today_lo, tomorrow_hi, tomorrow_lo):
    fig = go.Figure()
    for source, color in [("OBSERVED", "#ff5a3d"), ("FORECAST", "#5b6cff")]:
        d = timeline[timeline["source"] == source]
        if not d.empty:
            fig.add_trace(go.Scatter(
                x=d["datetime"], y=d["temp"], mode="lines+markers", name=source,
                line=dict(color=color, width=2), marker=dict(size=5)
            ))

    markers = [
        (today_hi, "H", "#10d0b0", "Today H"),
        (today_lo, "L", "#a855f7", "Today L"),
        (tomorrow_hi, "H", "#ff9f43", "Tomorrow H"),
        (tomorrow_lo, "L", "#25c7e8", "Tomorrow L"),
    ]
    for row, text, color, name in markers:
        if row:
            fig.add_trace(go.Scatter(
                x=[row["datetime"]], y=[row["temp"]], mode="markers+text", name=name,
                marker=dict(size=14, color=color), text=[text], textposition="top center",
                textfont=dict(size=13, color="white")
            ))

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#f5f5f5"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="#262b35"),
        yaxis=dict(title="Temperature (°F)", gridcolor="#262b35"),
    )
    return fig

# -----------------------------
# UI
# -----------------------------
st.title("NWS Weather Monitor")
st.caption("Fast monitor using official NWS station forecast + live station observation history.")

selected_view = choose_view()

if selected_view == "All cities":
    render_all_cities()
    st.stop()

if selected_view == "Links":
    render_links()
    st.stop()

selected_city = selected_view
city_cfg = CITIES[selected_city]

col_refresh, col_meta = st.columns([1, 4])
with col_refresh:
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

station = city_cfg["station"]
tz_name = city_cfg["tz"]
now = local_now(tz_name)
with col_meta:
    st.markdown(
        f'<div class="city-meta">Station: <b>{station}</b> · City: <b>{selected_city}</b> · Local time: {now.strftime("%Y-%m-%d %-I:%M %p %Z")}</div>',
        unsafe_allow_html=True,
    )

try:
    forecast_df = fetch_digital_forecast(station, tz_name)
except Exception as e:
    st.error(f"Forecast data is unavailable for {selected_city} / {station}.")
    forecast_df = pd.DataFrame()

try:
    observed_df = fetch_obhistory(station, tz_name)
except Exception:
    st.warning(f"Observed station history is unavailable for {selected_city} / {station}.")
    observed_df = pd.DataFrame()

try:
    current_df = fetch_observations_api(station, tz_name)
except Exception:
    current_df = pd.DataFrame()

timeline = build_timeline(observed_df, forecast_df, tz_name)
today = now.date()
tomorrow = today + timedelta(days=1)
today_hi, today_lo = projected_extremes_for_date(observed_df, forecast_df, today, tz_name)
tomorrow_hi, tomorrow_lo = projected_extremes_for_date(observed_df, forecast_df, tomorrow, tz_name)
chart_today_hi, chart_today_lo = extremes_for_date(timeline, today)
chart_tomorrow_hi, chart_tomorrow_lo = extremes_for_date(timeline, tomorrow)

st.subheader("Today projected temperatures")

c1, c2 = st.columns(2)
for col, title, row, event_type in [
    (c1, "Today High", today_hi, "high"),
    (c2, "Today Low", today_lo, "low"),
]:
    with col:
        if row:
            conf = confidence_for_event(row["datetime"], event_type, row, city_cfg["regime"])
            st.metric(title, fmt_temp(row["temp"]), f"{fmt_hour(row['datetime'])} · {conf}% · {row['source']}")
        else:
            st.metric(title, "N/A", "")

# Heat card based on today low row if available, otherwise latest observed/forecast row
base_row = today_lo or (timeline.iloc[-1].to_dict() if not timeline.empty else None)
label, score, cls, reasons = score_heat_regime(base_row, city_cfg["regime"])
st.markdown(
    f'<div class="heat-card {cls}">{label}<small>Score {score} · {reasons}</small></div>',
    unsafe_allow_html=True,
)

with st.expander("Tomorrow projected temperatures", expanded=False):
    t1, t2 = st.columns(2)
    for col, title, row, event_type in [
        (t1, "Tomorrow High", tomorrow_hi, "high"),
        (t2, "Tomorrow Low", tomorrow_lo, "low"),
    ]:
        with col:
            if row:
                conf = confidence_for_event(row["datetime"], event_type, row, city_cfg["regime"])
                st.metric(title, fmt_temp(row["temp"]), f"{fmt_hour(row['datetime'])} · {conf}% · {row['source']}")
            else:
                st.metric(title, "N/A", "")

if not timeline.empty:
    st.plotly_chart(
        plot_temperature(timeline, chart_today_hi, chart_today_lo, chart_tomorrow_hi, chart_tomorrow_lo),
        use_container_width=True,
    )
else:
    st.error("No timeline data available.")

st.subheader("Current conditions")
latest_obs = current_df.iloc[-1].to_dict() if not current_df.empty else None
if latest_obs:
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Current Temp", fmt_temp(latest_obs.get("temp")))
    cc2.metric("Dewpoint", fmt_temp(latest_obs.get("dewpoint")))
    cc3.metric("Humidity", f"{safe_int(latest_obs.get('humidity'))}%" if latest_obs.get("humidity") is not None else "N/A")
    cc4.metric("Wind", f"{safe_int(latest_obs.get('wind_mph'))} mph" if latest_obs.get("wind_mph") is not None else "N/A")
    st.caption(f"Latest observed: {latest_obs.get('datetime').strftime('%Y-%m-%d %-I:%M %p %Z')} · {latest_obs.get('description', '-')}")
else:
    st.info("Current observed station data unavailable.")

st.subheader("Observed + forecast table")
if not timeline.empty:
    display = timeline[[
        "time", "source", "temp", "dewpoint", "heat_index", "wind_mph", "wind_dir", "gust_mph",
        "sky_cover", "precip", "humidity", "rain", "thunder", "description"
    ]].copy()
    display.columns = [
        "Time", "Source", "Temp", "Dewpoint", "Heat Index", "Wind mph", "Wind Dir", "Gust mph",
        "Sky Cover %", "Precip %", "Humidity %", "Rain", "Thunder", "Description"
    ]
    st.dataframe(display, use_container_width=True, hide_index=True, height=420)
