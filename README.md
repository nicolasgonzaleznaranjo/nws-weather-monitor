# NWS Weather Monitor

This is a very simple one-page Streamlit app.

It shows a 48-hour weather timeline using only National Weather Service data.

The timeline starts at **12:00 AM today** and ends at **11:59 PM tomorrow**.

It combines:

- observed weather for hours that already happened today
- forecast weather for future hours

There is no trading, no database, no login, no Docker, and no paid API.

## Folder Created

I created one folder:

```text
nws-weather-monitor
```

Inside that folder are three files:

```text
nws-weather-monitor/
|-- streamlit_app.py
|-- requirements.txt
`-- README.md
```

## What Each File Does

### `streamlit_app.py`

This is the actual app.

It does these things:

- shows the page title
- lets you choose a city
- gets weather data from the National Weather Service
- builds the 48-hour table
- shows today and tomorrow high and low temperatures
- estimates a simple confidence percentage
- gives you a slider to inspect any hour
- refreshes automatically every 60 minutes

### `requirements.txt`

This tells Streamlit what Python packages to install.

The app needs:

- `streamlit` for the website
- `pandas` for tables
- `requests` for calling the National Weather Service
- `streamlit-autorefresh` for refreshing every 60 minutes

### `README.md`

This is the beginner instruction file you are reading now.

GitHub shows this file on the front page of your repository.

## Cities Included

The app includes:

- Atlanta
- Austin
- Boston
- Chicago
- Dallas
- Denver
- Houston
- Las Vegas
- Los Angeles
- Miami
- Minneapolis
- New Orleans
- New York City
- Oklahoma City
- Philadelphia
- Phoenix
- San Antonio
- San Francisco
- Seattle/Tacoma
- Washington DC

## Data Source

This app only uses National Weather Service data:

```text
https://api.weather.gov
```

The app uses:

- NWS point lookup
- NWS hourly forecast
- NWS observation stations
- NWS station observations

## How To Upload This To GitHub

### Step 1: Create a GitHub account

Go to:

```text
https://github.com
```

Create an account if you do not already have one.

### Step 2: Create a new repository

On GitHub:

1. Click the **+** button in the top-right corner.
2. Click **New repository**.
3. In **Repository name**, type:

```text
nws-weather-monitor
```

4. Choose **Public**.
5. Do not worry about the other settings.
6. Click **Create repository**.

### Step 3: Upload the files

Inside your new GitHub repository:

1. Click **uploading an existing file**.
2. Drag these three files into GitHub:

```text
streamlit_app.py
requirements.txt
README.md
```

3. Scroll down.
4. In the box that says **Commit changes**, type:

```text
First version of NWS Weather Monitor
```

5. Click **Commit changes**.

Now your app files are on GitHub.

## How To Deploy To Streamlit Community Cloud

### Step 1: Go to Streamlit

Open:

```text
https://share.streamlit.io
```

Sign in with your GitHub account.

### Step 2: Create a new app

1. Click **New app**.
2. Choose your GitHub repository:

```text
nws-weather-monitor
```

3. For **Branch**, choose:

```text
main
```

4. For **Main file path**, type:

```text
streamlit_app.py
```

5. Click **Deploy**.

Streamlit will install the packages from `requirements.txt` and run the app.

## What Buttons To Click In The App

### City dropdown

Use the city dropdown on the left side.

Pick the city you want to monitor.

### Refresh now

Click **Refresh now** if you want the newest National Weather Service data immediately.

The app also refreshes itself every 60 minutes.

### 48-hour slider

Move the slider under **Hourly Timeline**.

When you move it, the selected hour details update below the table.

## What Text To Paste

When GitHub asks for a commit message, paste:

```text
First version of NWS Weather Monitor
```

When Streamlit asks for the main file path, paste:

```text
streamlit_app.py
```

## How To Update The App Later

If you want to change the app later:

1. Go to your GitHub repository.
2. Click the file you want to change.
3. Click the pencil icon.
4. Edit the file.
5. Scroll down.
6. Click **Commit changes**.

Streamlit usually notices the change and updates the app automatically.

If it does not update:

1. Go to your Streamlit app dashboard.
2. Open your app settings.
3. Click **Reboot app**.

## Important Beginner Notes

You do not need Docker.

You do not need a database.

You do not need passwords or login pages.

You do not need a paid weather API.

You only need:

- GitHub
- Streamlit Community Cloud
- these three files

## If The App Shows An Error

The most common reason is that the National Weather Service is temporarily slow or unavailable.

Try this:

1. Click **Refresh now**.
2. Wait one minute.
3. Refresh your browser.

If it still fails, try again later.
