import re
from io import StringIO
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="NWS Weather Monitor", layout="wide", initial_sidebar_state="collapsed")

NWS_HEADERS = {
    "User-Agent": "nws-weather-monitor/1.0 (personal weather monitor)",
    "Accept": "application/geo+json, application/json, text/html",
}

CITIES = {
    "Atlanta": {"station": "KATL", "lat": 33.6407, "lon": -84.4277, "tz": "America/New_York", "regime": "humid"},
    "Austin": {"station": "KAUS", "lat": 30.1945, "lon": -97.6699, "tz": "America/Chicago", "regime": "humid"},
    "Boston": {"station": "KBOS", "lat": 42.3656, "lon": -71.0096, "tz": "America/New_York", "regime": "northeast"},
    "Chicago": {"station": "KMDW", "lat": 41.7868, "lon": -87.7522, "tz": "America/Chicago", "regime": "lake"},
    "Dallas": {"station": "KDFW", "lat": 32.8998, "lon": -97.0403, "tz": "America/Chicago", "regime": "humid"},
    "Denver": {"station": "KDEN", "lat": 39.8561, "lon": -104.6737, "tz": "America/Denver", "regime": "elevation"},
    "Houston": {"station": "KHOU", "lat": 29.6454, "lon": -95.2789, "tz": "America/Chicago", "regime": "humid"},
    "Las Vegas": {"station": "KLAS", "lat": 36.0840, "lon": -115.1537, "tz": "America/Los_Angeles", "regime": "desert"},
    "Los Angeles": {"station": "KLAX", "lat": 33.9416, "lon": -118.4085, "tz": "America/Los_Angeles", "regime": "marine"},
    "Miami": {"station": "KMIA", "lat": 25.7959, "lon": -80.2870, "tz": "America/New_York", "regime": "humid"},
    "Minneapolis": {"station": "KMSP", "lat": 44.8848, "lon": -93.2223, "tz": "America/Chicago", "regime": "northern"},
    "New Orleans": {"station": "KMSY", "lat": 29.9934, "lon": -90.2580, "tz": "America/Chicago", "regime": "humid"},
    "New York City": {"station": "KNYC", "lat": 40.7794, "lon": -73.9692, "tz": "America/New_York", "regime": "northeast"},
    "Oklahoma City": {"station": "KOKC", "lat": 35.3931, "lon": -97.6007, "tz": "America/Chicago", "regime": "plains"},
    "Philadelphia": {"station": "KPHL", "lat": 39.8744, "lon": -75.2424, "tz": "America/New_York", "regime": "northeast"},
    "Phoenix": {"station": "KPHX", "lat": 33.4278, "lon": -112.0035, "tz": "America/Phoenix", "regime": "desert"},
    "San Antonio": {"station": "KSAT", "lat": 29.5337, "lon": -98.4698, "tz": "America/Chicago", "regime": "humid"},
    "San Francisco": {"station": "KSFO", "lat": 37.6213, "lon": -122.3790, "tz": "America/Los_Angeles", "regime": "marine"},
    "Seattle/Tacoma": {"station": "KSEA", "lat": 47.4502, "lon": -122.3088, "tz": "America/Los_Angeles", "regime": "marine"},
    "Washington DC": {"station": "KDCA", "lat": 38.8512, "lon": -77.0402, "tz": "America/New_York", "regime": "northeast"},
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
    iframe[title="city_selector"] { display: block; }
    @media (max-width: 700px) {
        .block-container { padding-left: .85rem; padding-right: .85rem; padding-top: .6rem; }
        h1 { font-size: 1.55rem !important; }
        h2 { font-size: 1.28rem !important; }
        div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
        div[data-testid="stMetricValue"] { font-size: 1.9rem; }
        .stButton button { width: 100%; }
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


def sync_selected_city():
    query_city = get_query_city()
    if "selected_city" not in st.session_state:
        st.session_state.selected_city = query_city or "Atlanta"
    elif query_city and query_city != st.session_state.selected_city:
        st.session_state.selected_city = query_city

    if st.session_state.selected_city not in CITIES:
        st.session_state.selected_city = "Atlanta"

    if query_city != st.session_state.selected_city:
        set_query_city(st.session_state.selected_city)

    return st.session_state.selected_city


def render_city_dropdown(selected_city):
    options_html = "\n".join(
        f'<option value="{city}" {"selected" if city == selected_city else ""}>{city}</option>'
        for city in CITIES
    )
    components.html(
        f"""
        <form id="city-form" method="get" target="_parent" style="margin:0;">
            <label for="city-select" style="
                display:block;
                color:#f5f5f5;
                font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                font-size:14px;
                font-weight:700;
                margin:0 0 8px 0;
            ">City</label>
            <select id="city-select" name="city" style="
                width:100%;
                min-height:44px;
                border-radius:8px;
                border:1px solid #303746;
                background:#262730;
                color:#ffffff;
                font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                font-size:16px;
                font-weight:600;
                padding:10px 12px;
            ">
                {options_html}
            </select>
            <button id="city-submit" type="submit" style="
                margin-top:8px;
                border:1px solid #303746;
                border-radius:8px;
                background:#111827;
                color:#ffffff;
                font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                font-size:14px;
                font-weight:700;
                padding:8px 12px;
            ">Apply city</button>
        </form>
        <script>
        const form = document.getElementById("city-form");
        const select = document.getElementById("city-select");
        function selectedCityUrl() {{
            const parentUrl = document.referrer || window.parent.location.href;
            const url = new URL(parentUrl);
            url.searchParams.set("city", select.value);
            return url.toString();
        }}
        form.action = selectedCityUrl();
        select.addEventListener("change", function() {{
            form.action = selectedCityUrl();
            try {{
                window.open(form.action, "_parent");
            }} catch (error) {{
                form.submit();
            }}
        }});
        form.addEventListener("submit", function() {{
            form.action = selectedCityUrl();
        }});
        </script>
        """,
        height=124,
    )


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


def get_nested_value(obj, key):
    val = obj.get(key)
    if isinstance(val, dict):
        val = val.get("value")
    return val

# -----------------------------
# NWS fetchers
# -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hourly_forecast(lat, lon, tz_name):
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points = requests.get(points_url, headers=NWS_HEADERS, timeout=20)
    points.raise_for_status()
    hourly_url = points.json()["properties"]["forecastHourly"]

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
        if "date/time" in joined and "temp" in joined:
            return table
    return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_obhistory(station, tz_name):
    url = f"https://forecast.weather.gov/data/obhistory/{station}.html"
    response = requests.get(url, headers={"User-Agent": NWS_HEADERS["User-Agent"]}, timeout=25)
    response.raise_for_status()

    try:
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

    date_col = find_col([["date/time"], ["date"]])
    temp_col = find_col([["temp"], ["air"]])
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
        if not raw_dt or raw_dt.lower() == "nan":
            continue

        parsed = None
        cleaned_dt = re.sub(r"\s+", " ", raw_dt)
        for fmt in ["%B %d, %I:%M %p", "%b %d, %I:%M %p"]:
            try:
                dt_naive = datetime.strptime(cleaned_dt, fmt)
                parsed = dt_naive.replace(year=now.year, tzinfo=tz)
                if parsed - now > timedelta(days=30):
                    parsed = parsed.replace(year=now.year - 1)
                break
            except Exception:
                continue
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

selected_city = sync_selected_city()
render_city_dropdown(selected_city)
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
    forecast_df = fetch_hourly_forecast(city_cfg["lat"], city_cfg["lon"], tz_name)
except Exception as e:
    st.error(f"Forecast data is unavailable for {selected_city} / {station}.")
    forecast_df = pd.DataFrame()

try:
    observed_df = fetch_obhistory(station, tz_name)
except Exception:
    st.warning(f"Observed station history is unavailable for {selected_city} / {station}.")
    observed_df = pd.DataFrame()

timeline = build_timeline(observed_df, forecast_df, tz_name)
today = now.date()
tomorrow = today + timedelta(days=1)
today_hi, today_lo = extremes_for_date(timeline, today)
tomorrow_hi, tomorrow_lo = extremes_for_date(timeline, tomorrow)

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
    st.plotly_chart(plot_temperature(timeline, today_hi, today_lo, tomorrow_hi, tomorrow_lo), use_container_width=True)
else:
    st.error("No timeline data available.")

st.subheader("Current conditions")
latest_obs = observed_df.iloc[-1].to_dict() if not observed_df.empty else None
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
