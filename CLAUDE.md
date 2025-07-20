# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit-based web application that displays hazard maps for Japanese addresses. It allows users to input an address, visualize it on an interactive map, and view various disaster risk overlays (flood, tsunami, landslide) from Japan's Geospatial Information Authority (GSI).

## Common Development Commands

```bash
# Set up Python environment with mise
mise install

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py

# The app will automatically open in your browser at http://localhost:8501
```

## Architecture

The application is intentionally simple with a single-file architecture (`app.py`) containing:

1. **Address Geocoding**: Converts Japanese addresses to coordinates using GSI's geocoding API
2. **Map Visualization**: Uses Folium to create interactive maps with hazard overlays
3. **Hazard Data Layers**: Integrates GSI's hazard map tile services for:
   - 洪水浸水想定区域 (Flood hazard areas)
   - 津波浸水想定 (Tsunami hazard areas)
   - 土砂災害警戒区域 (Sediment disaster warning areas)
4. **Risk Assessment**: Currently displays demo values (not connected to real data)

## Key APIs and Data Sources

- **Geocoding**: `https://msearch.gsi.go.jp/address-search/AddressSearch?q={address}`
- **Hazard Map Tiles**: 
  - Flood: `https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png`
  - Tsunami: `https://disaportaldata.gsi.go.jp/raster/04_tsunami_newlegend_data/{z}/{x}/{y}.png`
  - Landslide: `https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png`

## Development Notes

- This is a prototype following KISS and YAGNI principles
- The risk assessment feature currently shows fixed demo values
- All text and UI is in Japanese as this targets Japanese addresses and hazard data
- The `.mise.toml` file specifies Python 3.11 for consistency