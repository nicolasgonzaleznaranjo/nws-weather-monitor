from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import re
from html import escape
from urllib.parse import quote
from typing import Any

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from bs4 import BeautifulSoup

APP_NAME = "NWS Weather Monitor"
NWS_API = "https://api.weather.gov"
OBHISTORY_BASE = "https://forecast.weather.gov/data/obhistory"
TIMESERIES_BASE = "https://forecast.weather.gov/wrh/timeseries"
HEADERS = {
    "User-Agent": "NWS Weather Monitor (personal Streamlit app)",
    "Accept": "application/geo+json, text/html, */*",
}

# Airport/station coordinates, not downtown coordinates.
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
    v = float(value)
    if abs(v - round(v)) < 0.05:
        return f"{int(round(v))}°F"
    return f"{v:.1f}°F"


def parse_float(text: Any) -> float | None:
    if text is None:
        return None
    s = str(text).replace("°F", "").replace("M", "").strip()
    if s in {"", "-", "--", "NA", "N/A"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def number_from_text(text: Any) -> float | None:
    return parse_float(text)


def c_to_f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return (float(v) * 9 / 5) + 32
    except Exception:
        return None


def mps_to_mph(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v) * 2.23694
    except Exception:
        return None


def heat_index_f(temp_f: float | None, rh: float | None) -> float | None:
    if temp_f is None or rh is None:
        return temp_f
    if temp_f < 80 or rh < 40:
        return temp_f
    t, r = float(temp_f), float(rh)
    return (
        -42.379 + 2.04901523 * t + 10.14333127 * r - 0.22475541 * t * r
        - 0.00683783 * t * t - 0.05481717 * r * r
        + 0.00122874 * t * t * r + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )


def sky_from_text(text: str | None, pop: float | None = None) -> int | None:
    t = (text or "").lower()
    if "clear" in t or "sunny" in t or "clr" in t:
        return 10
    if "few" in t or "partly" in t or "sct" in t or "scattered" in t:
        return 45
    if "broken" in t or "mostly cloudy" in t or "bkn" in t:
        return 75
    if "cloudy" in t or "overcast" in t or "ovc" in t:
        return 90
    if pop is not None and pop >= 60:
        return 80
    return None


def clean_cell_text(cell) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def expanded_cells(tr) -> list[str]:
    out: list[str] = []
    for cell in tr.find_all(["th", "td"]):
        text = clean_cell_text(cell)
        span = int(cell.get("colspan", 1) or 1)
        out.extend([text] * span)
    return out


def parse_wind_compact(text: str) -> tuple[str, float | None]:
    s = text.strip()
    direction = "-"
    speed = None
    mdir = re.search(r"\b(N|S|E|W|NE|NW|SE|SW|NNE|NNW|ENE|ESE|SSE|SSW|WSW|WNW|CALM|VRB)\b", s, re.I)
    if mdir:
        direction = mdir.group(1).upper()
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if nums:
        speed = float(nums[-1])
    if "CALM" in s.upper():
        speed = 0.0
        direction = "CALM"
    return direction, speed


def nws_get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=900, show_spinner=False)
def load_obhistory(city_name: str, today_iso: str) -> pd.DataFrame:
    """Parse the live NWS station observation history page.

    This intentionally uses forecast.weather.gov/data/obhistory/{station}.html
    because that page contains the intrahour observations needed for live highs/lows.
    """
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    station = city["station"]
    today = datetime.fromisoformat(today_iso).date()
    url = f"{OBHISTORY_BASE}/{station}.html"

    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = [clean_cell_text(td) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue

        dt: datetime | None = None
        temp = dew = rh = heat_index = wind_speed = gust = None
        wind_dir = "-"
        desc = "Observed"
        sky_text = ""

        # Format A, current NWS obhistory:
        # Date | Time | Wind | Vis | Weather | Sky Cond | Air | Dwpt | 6h Max | 6h Min | RH | ...
        if re.fullmatch(r"\d{1,2}", cells[0]) and re.search(r"\d{1,2}:\d{2}", cells[1]):
            day = int(cells[0])
            hh, mm = [int(x) for x in re.search(r"(\d{1,2}):(\d{2})", cells[1]).groups()]
            dt = datetime(today.year, today.month, day, hh, mm, tzinfo=tz)
            # If page includes prior month near month boundary, adjust safely.
            if (dt.date() - today).days > 10:
                prev_month = today.month - 1 or 12
                year = today.year - 1 if prev_month == 12 else today.year
                dt = datetime(year, prev_month, day, hh, mm, tzinfo=tz)

            wind_dir, wind_speed = parse_wind_compact(cells[2]) if len(cells) > 2 else ("-", None)
            weather = cells[4] if len(cells) > 4 else ""
            sky_text = cells[5] if len(cells) > 5 else ""
            temp = parse_float(cells[6]) if len(cells) > 6 else None
            dew = parse_float(cells[7]) if len(cells) > 7 else None
            rh = parse_float(cells[10]) if len(cells) > 10 else None
            wind_chill = parse_float(cells[11]) if len(cells) > 11 else None
            heat_index = parse_float(cells[12]) if len(cells) > 12 else None
            desc = " / ".join([x for x in [weather, sky_text] if x and x not in {"-", "--"}]) or "Observed"
            if heat_index is None:
                heat_index = wind_chill or heat_index_f(temp, rh)

        # Format B, older compact data/obhistory page:
        # May 22, 4:05 am | Temp | Dew Point | RH | Heat Index | Wind Chill | Wind Dir | Wind Speed | Visibility | ...
        elif re.search(r"[A-Za-z]{3,9}\s+\d{1,2},\s+\d{1,2}:\d{2}\s*(am|pm)", cells[0], re.I):
            m = re.search(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s+(\d{1,2}:\d{2})\s*(am|pm)", cells[0], re.I)
            if m:
                raw = f"{m.group(1)} {m.group(2)} {today.year} {m.group(3)} {m.group(4)}"
                dt = datetime.strptime(raw, "%b %d %Y %I:%M %p").replace(tzinfo=tz)
            temp = parse_float(cells[1]) if len(cells) > 1 else None
            dew = parse_float(cells[2]) if len(cells) > 2 else None
            rh = parse_float(cells[3]) if len(cells) > 3 else None
            heat_index = parse_float(cells[4]) if len(cells) > 4 else None
            wind_chill = parse_float(cells[5]) if len(cells) > 5 else None
            wind_dir = cells[6] if len(cells) > 6 and cells[6] not in {"", "--"} else "-"
            wind_speed = parse_float(cells[7]) if len(cells) > 7 else None
            sky_text = cells[9] if len(cells) > 9 else ""
            desc = sky_text or "Observed"
            if heat_index is None:
                heat_index = wind_chill or heat_index_f(temp, rh)

        if dt is None or dt.date() != today or temp is None:
            continue

        rows.append({
            "Time": dt,
            "Source": "OBSERVED",
            "Temp": temp,
            "Dewpoint": dew,
            "Heat Index": heat_index,
            "Wind mph": wind_speed,
            "Wind Dir": wind_dir,
            "Gust mph": gust,
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
    return df.sort_values("Time").drop_duplicates(subset=["Time"], keep="last").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_timeseries_forecast(city_name: str) -> pd.DataFrame:
    """Parse the NWS WRH station timeseries table.

    This is preferred over generic gridpoint forecastHourly because it matches
    the station-specific NWS table the user manually checks.
    """
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    station = city["station"]
    now = datetime.now(tz)
    url = f"{TIMESERIES_BASE}?site={station}"

    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    wanted = {
        "date": ["date"],
        "hour": ["hour"],
        "temp": ["temperature"],
        "dew": ["dewpoint"],
        "heat": ["heat index"],
        "wind": ["surface wind"],
        "wind_dir": ["wind dir"],
        "gust": ["gust"],
        "sky": ["sky cover"],
        "pop": ["precipitation potential"],
        "rh": ["relative humidity"],
        "rain": ["rain"],
        "thunder": ["thunder"],
    }

    row_map: dict[str, list[str]] = {}
    for tr in soup.find_all("tr"):
        cells = expanded_cells(tr)
        if len(cells) < 3:
            continue
        label = cells[0].lower()
        label = re.sub(r"\s+", " ", label)
        for key, needles in wanted.items():
            if any(n in label for n in needles):
                row_map[key] = cells[1:]
                break

    if "hour" not in row_map or "temp" not in row_map:
        raise ValueError("Could not parse WRH timeseries table; falling back is required.")

    n = min(len(row_map.get("hour", [])), len(row_map.get("temp", [])))
    dates = row_map.get("date", [""] * n)
    hours = row_map.get("hour", [])

    # Fill date row because NWS often uses colspan or blanks.
    filled_dates: list[str] = []
    last_date = None
    for i in range(n):
        d = dates[i] if i < len(dates) else ""
        if re.search(r"\d{1,2}/\d{1,2}", d):
            last_date = re.search(r"\d{1,2}/\d{1,2}", d).group()
        filled_dates.append(last_date or now.strftime("%m/%d"))

    def get(row: str, i: int) -> Any:
        vals = row_map.get(row, [])
        return vals[i] if i < len(vals) else None

    rows: list[dict[str, Any]] = []
    for i in range(n):
        hour = parse_float(hours[i])
        temp = parse_float(get("temp", i))
        if hour is None or temp is None:
            continue
        month, day = [int(x) for x in filled_dates[i].split("/")[:2]]
        year = now.year
        dt = datetime(year, month, day, int(hour), 0, tzinfo=tz)
        # Handle New Year edge.
        if (dt - now).days < -300:
            dt = dt.replace(year=year + 1)

        dew = parse_float(get("dew", i))
        rh = parse_float(get("rh", i))
        heat = parse_float(get("heat", i)) or heat_index_f(temp, rh)
        pop = parse_float(get("pop", i))
        sky = parse_float(get("sky", i))
        rain = get("rain", i) or "-"
        thunder = get("thunder", i) or "-"
        rows.append({
            "Time": dt,
            "Source": "FORECAST",
            "Temp": temp,
            "Dewpoint": dew,
            "Heat Index": heat,
            "Wind mph": parse_float(get("wind", i)),
            "Wind Dir": get("wind_dir", i) or "-",
            "Gust mph": parse_float(get("gust", i)),
            "Sky Cover %": sky,
            "Precip %": pop,
            "Humidity %": rh,
            "Rain": rain if rain not in {"", "--"} else "-",
            "Thunder": thunder if thunder not in {"", "--"} else "-",
            "Description": "NWS station forecast",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("WRH timeseries produced no forecast rows.")
    return df.sort_values("Time").drop_duplicates(subset=["Time"], keep="first").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_api_forecast_fallback(city_name: str) -> pd.DataFrame:
    city = CITIES[city_name]
    tz = ZoneInfo(city["tz"])
    point = nws_get_json(f"{NWS_API}/points/{city['lat']:.4f},{city['lon']:.4f}")
    periods = nws_get_json(point["properties"]["forecastHourly"])["properties"]["periods"]
    rows = []
    for p in periods:
        ts = datetime.fromisoformat(p["startTime"]).astimezone(tz).replace(minute=0, second=0, microsecond=0)
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        rh = (p.get("relativeHumidity") or {}).get("value")
        dew = c_to_f((p.get("dewpoint") or {}).get("value"))
        temp = p.get("temperature")
        desc = p.get("shortForecast") or "Forecast"
        rows.append({
            "Time": ts,
            "Source": "FORECAST",
            "Temp": float(temp) if temp is not None else None,
            "Dewpoint": dew,
            "Heat Index": heat_index_f(float(temp), rh) if temp is not None else None,
            "Wind mph": number_from_text(p.get("windSpeed")),
            "Wind Dir": p.get("windDirection") or "-",
            "Gust mph": number_from_text(p.get("windGust")),
            "Sky Cover %": sky_from_text(desc, pop),
            "Precip %": pop,
            "Humidity %": rh,
            "Rain": "Yes" if "rain" in desc.lower() or "shower" in desc.lower() or (pop or 0) >= 50 else "-",
            "Thunder": "Yes" if "thunder" in desc.lower() or "storm" in desc.lower() else "-",
            "Description": desc,
        })
    return pd.DataFrame(rows)


def load_forecast(city_name: str) -> tuple[pd.DataFrame, str]:
    try:
        return load_timeseries_forecast(city_name), "NWS WRH station timeseries"
    except Exception:
        return load_api_forecast_fallback(city_name), "NWS API forecastHourly fallback"


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
    sky = 50 if sky is None or pd.isna(sky) else float(sky)
    pop = row.get("Precip %") or 0
    rh = row.get("Humidity %") or 50
    dew = row.get("Dewpoint") or 50
    wind = row.get("Wind mph") or 5

    if event_type == "high":
        if pop >= 40 or sky >= 75:
            score -= 5
        if sky <= 35 and pop <= 20:
            score += 4
        if climate in {"desert", "hot_humid"}:
            score -= 2
        if climate in {"marine", "coastal"}:
            score += 2
    else:
        if rh >= 70 and sky >= 60:
            score += 4
        if rh <= 45 and wind <= 6 and sky <= 35:
            score -= 5
        if dew <= 45:
            score -= 2
    return int(max(45, min(100, score)))




def classify_heat_regime(row: pd.Series | None, climate: str) -> tuple[str, int, str, str]:
    """Simple heat retention / heat loss classifier from NWS variables."""
    if row is None:
        return "Neutral", 0, "neutral", "No current data"

    def val(name: str, default=None):
        x = row.get(name, default)
        if x is None or pd.isna(x):
            return default
        try:
            return float(x)
        except Exception:
            return default

    temp = val("Temp")
    dew = val("Dewpoint")
    heat = val("Heat Index")
    wind = val("Wind mph")
    gust = val("Gust mph")
    sky = val("Sky Cover %")
    pop = val("Precip %")
    rh = val("Humidity %")
    rain = str(row.get("Rain", "-")).lower()
    thunder = str(row.get("Thunder", "-")).lower()

    score = 0
    reasons: list[str] = []

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
            score += 1; reasons.append("partial cloud cover")
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
        score += 1; reasons.append("gusty mixing")

    if pop is not None:
        if pop >= 50:
            score += 2; reasons.append("high precip risk")
        elif pop >= 25:
            score += 1; reasons.append("some precip risk")
    if rain not in {"", "-", "--", "none", "nan"}:
        score += 2; reasons.append("rain")
    if thunder not in {"", "-", "--", "none", "nan"}:
        score += 1; reasons.append("thunder risk")

    if heat is not None and temp is not None:
        if heat - temp >= 5:
            score += 2; reasons.append("heat index premium")
        elif heat > temp:
            score += 1; reasons.append("humid heat")

    if climate in {"humid", "hot_humid", "tropical"}:
        score += 1; reasons.append("humid city")
    elif climate in {"desert", "dry"}:
        score -= 1; reasons.append("dry city")
    elif climate in {"marine", "coastal"}:
        score += 1; reasons.append("marine/coastal cap")

    if score >= 2:
        return "Heat Retention", score, "retention", ", ".join(reasons[:4]) or "Moist/stable setup"
    if score <= -2:
        return "Heat Loss", score, "loss", ", ".join(reasons[:4]) or "Dry/cooling setup"
    return "Neutral", score, "neutral", ", ".join(reasons[:4]) or "Mixed setup"


def heat_badge_html(label: str, score: int, kind: str, reasons: str) -> str:
    if kind == "retention":
        bg = "linear-gradient(135deg, #7f1d1d, #b45309)"
        border = "#f59e0b"
    elif kind == "loss":
        bg = "linear-gradient(135deg, #0f172a, #1d4ed8)"
        border = "#38bdf8"
    else:
        bg = "linear-gradient(135deg, #27272a, #52525b)"
        border = "#a1a1aa"
    return f"""
    <div class="heat-badge" style="background:{bg}; border:1px solid {border};">
        <div class="heat-badge-title">{label}</div>
        <div class="heat-badge-sub">Score {score} · {reasons}</div>
    </div>
    """

def build_merged_timeline(observed: pd.DataFrame, forecast: pd.DataFrame, now: datetime) -> pd.DataFrame:
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    end = start + timedelta(days=2)
    next_forecast_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    parts = []
    if not observed.empty:
        obs = observed[(observed["Time"] >= start) & (observed["Time"] <= now)].copy()
        parts.append(obs)
    if not forecast.empty:
        fc = forecast[(forecast["Time"] >= next_forecast_hour) & (forecast["Time"] < end)].copy()
        parts.append(fc)

    if not parts:
        return pd.DataFrame()
    merged = pd.concat(parts, ignore_index=True).sort_values("Time")
    return merged.reset_index(drop=True)


def extreme(df: pd.DataFrame, date_value, kind: str, now: datetime, climate: str):
    if df.empty or "Time" not in df or "Temp" not in df:
        return None
    d = df[(df["Time"].dt.date == date_value) & df["Temp"].notna()]
    if d.empty:
        return None
    idx = d["Temp"].idxmax() if kind == "high" else d["Temp"].idxmin()
    row = d.loc[idx]
    return row, confidence(row, kind, now, climate)


def current_temp(observed: pd.DataFrame, forecast: pd.DataFrame, now: datetime):
    if not observed.empty and observed["Temp"].notna().any():
        row = observed.sort_values("Time").iloc[-1]
        return row, "OBSERVED"
    if not forecast.empty:
        fc = forecast[forecast["Time"] <= now.replace(minute=0, second=0, microsecond=0)]
        if not fc.empty:
            row = fc.sort_values("Time").iloc[-1]
            return row, "FORECAST"
    return None, None


def metric_card(label: str, item) -> None:
    if item is None:
        st.metric(label, "N/A", "No data")
        return
    row, conf = item
    st.metric(label, fmt_temp(row["Temp"]), f"{safe_time(row['Time'])} · {conf}% · {row['Source']}")


def make_chart(df: pd.DataFrame, today_high, today_low, tomorrow_high, tomorrow_low):
    chart_df = df[df["Temp"].notna()].copy()
    if chart_df.empty:
        return None
    fig = go.Figure()
    for source, group in chart_df.groupby("Source"):
        fig.add_trace(go.Scatter(
            x=group["Time"], y=group["Temp"], mode="lines+markers", name=source,
            hovertemplate="%{x|%a %m/%d %I:%M %p}<br>%{y:.1f}°F<extra></extra>",
        ))
    for label, item in [("H", today_high), ("L", today_low), ("H", tomorrow_high), ("L", tomorrow_low)]:
        if item is None:
            continue
        row, _ = item
        fig.add_trace(go.Scatter(
            x=[row["Time"]], y=[row["Temp"]], mode="markers+text", text=[label], textposition="top center",
            marker=dict(size=14), name=label,
            hovertemplate=f"{label}: %{{y:.1f}}°F<br>%{{x|%a %m/%d %I:%M %p}}<extra></extra>",
        ))
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=25, b=10),
        template="plotly_dark",
        xaxis_title="",
        yaxis_title="Temperature (°F)",
        legend_orientation="h",
        legend_y=1.08,
    )
    return fig


def display_table(df: pd.DataFrame, height: int = 560):
    if df.empty:
        st.write("No data.")
        return
    show = df.copy()
    show["Time"] = show["Time"].dt.strftime("%a %m/%d %I:%M %p")
    cols = ["Temp", "Dewpoint", "Heat Index", "Wind mph", "Gust mph", "Sky Cover %", "Precip %", "Humidity %"]
    for col in cols:
        if col in show:
            show[col] = show[col].apply(lambda x: "-" if x is None or pd.isna(x) else round(float(x), 1))
    st.dataframe(show, use_container_width=True, height=height)



st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.0rem; padding-bottom: 1rem; max-width: 1500px;}
    h1 {font-size: 1.65rem !important; margin-bottom: 0.15rem !important;}
    h2, h3 {margin-top: 0.75rem !important;}
    [data-testid="stMetric"] {background: #111827; border: 1px solid #283142; border-radius: 14px; padding: 12px 14px;}
    [data-testid="stMetricLabel"] {font-size: 0.78rem; color: #cbd5e1;}
    [data-testid="stMetricValue"] {font-size: 1.7rem;}
    .heat-badge {border-radius: 16px; padding: 14px 16px; margin: 6px 0 10px 0; box-shadow: 0 8px 24px rgba(0,0,0,.22);}
    .heat-badge-title {font-weight: 800; font-size: 1.0rem; letter-spacing: .04em; text-transform: uppercase; color: white;}
    .heat-badge-sub {font-size: .82rem; color: rgba(255,255,255,.84); margin-top: 3px;}
    @media (max-width: 768px) {
        .block-container {padding-left: .75rem; padding-right: .75rem; padding-top: .55rem;}
        h1 {font-size: 1.35rem !important;}
        [data-testid="stMetric"] {padding: 10px 11px;}
        [data-testid="stMetricValue"] {font-size: 1.45rem;}
        .heat-badge {padding: 12px; border-radius: 14px;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_NAME)
st.caption("Fast monitor using official NWS station forecast + live station observation history.")

def get_query_city() -> str:
    try:
        value = st.query_params.get("city", "Atlanta")
        if isinstance(value, list):
            value = value[0] if value else "Atlanta"
        return value if value in CITIES else "Atlanta"
    except Exception:
        return "Atlanta"

city_name = get_query_city()

# Native browser dropdown. This avoids opening the phone keyboard,
# unlike Streamlit's searchable selectbox on mobile.
options_html = "".join(
    f'<option value="{quote(name)}" {"selected" if name == city_name else ""}>{escape(name)}</option>'
    for name in CITIES.keys()
)
select_html = f"""
<form method="get" style="margin: 0 0 0.75rem 0;">
    <label for="city-select" style="display:block; font-size:0.85rem; font-weight:700; margin-bottom:0.35rem; color:#e5e7eb;">City</label>
    <select id="city-select" name="city" onchange="this.form.submit()"
        style="width:100%; background:#1f2430; color:#ffffff; border:1px solid #374151; border-radius:10px; padding:0.75rem 0.85rem; font-size:1rem; appearance:auto; -webkit-appearance:menulist;">
        {options_html}
    </select>
</form>
"""
st.markdown(select_html, unsafe_allow_html=True)

city = CITIES[city_name]
tz = ZoneInfo(city["tz"])
now = datetime.now(tz)
today = now.date()
tomorrow = today + timedelta(days=1)

ctrl1, ctrl2 = st.columns([1, 3])
with ctrl1:
    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with ctrl2:
    st.caption(f"Station: {city['station']} · Local time: {now.strftime('%Y-%m-%d %I:%M %p %Z')}")

try:
    forecast_df, forecast_source = load_forecast(city_name)
    observed_df = load_obhistory(city_name, today.isoformat())
    df = build_merged_timeline(observed_df, forecast_df, now)
except Exception as e:
    st.error("NWS data failed to load. Try Refresh now or check Streamlit logs.")
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("No observed/forecast data available for this city right now.")
    st.stop()

cur_row, cur_source = current_temp(observed_df, forecast_df, now)
regime_label, regime_score, regime_kind, regime_reasons = classify_heat_regime(cur_row, city["climate"])

today_high = extreme(df, today, "high", now, city["climate"])
today_low = extreme(df, today, "low", now, city["climate"])
tomorrow_high = extreme(df, tomorrow, "high", now, city["climate"])
tomorrow_low = extreme(df, tomorrow, "low", now, city["climate"])

st.subheader("Today projected temperatures")
mobile_a, mobile_b = st.columns(2)
with mobile_a:
    metric_card("Today High", today_high)
with mobile_b:
    metric_card("Today Low", today_low)

st.markdown(heat_badge_html(regime_label, regime_score, regime_kind, regime_reasons), unsafe_allow_html=True)

with st.expander("Tomorrow projected temperatures", expanded=False):
    t1, t2 = st.columns(2)
    with t1:
        metric_card("Tomorrow High", tomorrow_high)
    with t2:
        metric_card("Tomorrow Low", tomorrow_low)

fig = make_chart(df, today_high, today_low, tomorrow_high, tomorrow_low)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Current conditions")
if cur_row is not None:
    c0, c1, c2, c3 = st.columns(4)
    with c0:
        st.metric("Current Temperature", fmt_temp(cur_row["Temp"]), f"{safe_time(cur_row['Time'])} · {cur_source}")
    with c1:
        st.metric("Dewpoint", fmt_temp(cur_row.get("Dewpoint")))
    with c2:
        st.metric("Humidity", "N/A" if pd.isna(cur_row.get("Humidity %")) else f"{round(float(cur_row.get('Humidity %')))}%")
    with c3:
        st.metric("Description", str(cur_row.get("Description", "-"))[:28])
else:
    st.metric("Current Temperature", "N/A")

st.caption(f"Forecast source: {forecast_source}. Observed source: forecast.weather.gov/data/obhistory/{city['station']}.html")
st.subheader("Observed + forecast table")
display_table(df)

with st.expander("Debug: raw observed rows"):
    display_table(observed_df, height=400)
