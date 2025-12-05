# WaterFX

A Flask web app for searching, selecting, and viewing detailed information about Texas public water systems, including metrics, mapping, facilities, and colonias served.

---

## Features
- Search for public water systems by name
- Select from matching systems
- View detailed dashboard: entity info, contact, service connection, demographic metrics, facilities, violations, map, and colonias served

---

## Prerequisites
- **Python 3.8+**
- **pip** (Python package manager)
- **Chrome browser** (for Selenium scraping)
- **ChromeDriver** (must match your Chrome version; [download here](https://chromedriver.chromium.org/downloads) and ensure it's in your PATH)
- **GeoPandas** and spatial libraries (see requirements.txt)

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd Water_FX
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   If you have issues with GeoPandas or spatial libraries, see [GeoPandas install docs](https://geopandas.org/en/stable/getting_started/install.html).

---

## Data Setup

- Place the following shapefiles in the project root (or as already structured):
  - `PWS_shapefile/` (with `PWS_Export.shp` and related files)
  - `COLONIAS_COMMUNITIES_/` (with `COLONIAS_COMMUNITIES.shp` and related files)
  - `tl_2024_48_tract/` (with `tl_2024_48_tract.shp` and related files)
- These are required for mapping, metrics, and colonia extraction.

---

## Running the App

1. **Start the Flask app:**
   ```bash
   python3 app.py
   ```
   The app will run in debug mode by default.

2. **Open your browser:**
   - Go to [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Usage
- **Search:** Enter a water system name on the home page.
- **Select:** Choose from the list of matching systems.
- **Details:** View the dashboard with all system info, map, metrics, facilities, violations, and colonias served.

---