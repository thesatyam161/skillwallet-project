# Skillwallet Project

Skillwallet Project is a Flask and Plotly analytics dashboard for retail product positioning analysis. It helps explore how pricing, promotions, product placement, foot traffic, seasonality, and customer demographics influence sales.

## Highlights

- Responsive dashboard and story pages designed to work cleanly on desktop and mobile
- CSV upload pipeline with schema validation and column-name normalization
- Interactive Plotly charts for pricing, promotions, traffic, and category performance
- SQLite-backed data flow for simple local use and lightweight deployment
- Flask-only deployment path with Render support

## Project structure

- `app.py`: main Flask application and routes
- `pipeline.py`: CSV validation, normalization, and SQLite loading
- `visualizations.py`: metrics, chart generation, and story insights
- `paths.py`: runtime path handling for local and deployed environments
- `base.html`: shared layout and navigation
- `style.css`: shared visual system and responsive UI styles
- `render.yaml`: Render deployment configuration
- `Procfile`: production process definition

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Deployment

Deploy this project as a **Render Web Service**.

### Recommended Render settings

- Environment: `Python`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment Variable: `PYTHON_VERSION=3.11.11`
- Environment Variable: `DATA_DIR=/var/data`

Attach a persistent disk and mount it at `/var/data` so uploaded CSV files and the SQLite database survive restarts.

### Blueprint deploy

This repository includes `render.yaml`, so you can also deploy it through Render Blueprint support.

## Runtime storage

The app writes runtime data to disk:

- uploaded CSV files
- the SQLite database file

By default, data is stored in the project directory. In production, set `DATA_DIR` to persistent storage.

## Upload schema

The uploader expects these logical columns:

- `Product ID`
- `Product Category`
- `Product Position`
- `Price`
- `Promotion`
- `Foot Traffic`
- `Consumer Demographics`
- `Seasonal`
- `Competitor Price`
- `Sales Volume`

The pipeline also accepts common name variants such as `Competitor's Price`.

## Production note

Use `gunicorn app:app` in production. Flask's built-in development server should only be used locally.

## Future improvements

If you want to harden this project for production, the next practical upgrades are:

1. move from SQLite to PostgreSQL
2. store uploads in object storage
3. add authentication and per-user dataset isolation
