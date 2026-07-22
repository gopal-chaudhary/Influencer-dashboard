# Influencer Discovery Dashboard

A modular Streamlit application for discovering, scoring, ranking, and exporting
influencer profiles from CSV/XLSX datasets.

## What the project does

1. Upload a CSV or Excel file.
2. Parse and validate influencer rows in the repository layer.
3. Build domain `Influencer` objects.
4. Analyze each influencer with xAI Grok.
5. Convert the AI output into a structured `AIAnalysis` model.
6. Score each influencer with a rule-based scoring engine.
7. Rank and filter the results.
8. Export the filtered ranking to CSV and Excel.

## Main features

- CSV and Excel ingestion
- Data validation and duplicate handling
- Grok-powered AI analysis
- Rule-based, weighted scoring engine
- Interactive dashboard with filters and search
- Detailed row-level inspection
- CSV / Excel export with AI analysis and score breakdowns
- Timestamped export files
- Filter metadata preserved in exports
- Standard Python logging
- Unit tests for core workflow components

## Project structure

```text
Influencer-dashboard/
├── app.py
├── config/
├── data/
├── docs/
├── example/
├── models/
├── repositories/
├── services/
├── tests/
├── ui/
└── utils/
```

### Layer overview

- `repositories/` — file ingestion and row validation
- `models/` — domain entities and result objects
- `services/` — Grok integration, scoring, workflow orchestration, exports
- `ui/` — Streamlit components only
- `utils/` — shared helpers such as logging and exceptions

## Setup

### 1) Create a virtual environment

```bash
python -m venv .venv
```

### 2) Activate it

```bash
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Configure environment variables

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
```

Required variables:

- `XAI_API_KEY`
- `XAI_BASE_URL`
- `XAI_MODEL`

Optional tuning variables:

- `XAI_TEMPERATURE`
- `XAI_MAX_TOKENS`
- `XAI_TIMEOUT_SECONDS`
- `XAI_MAX_RETRIES`
- `XAI_RETRY_INITIAL_DELAY_SECONDS`
- `XAI_RETRY_MAX_DELAY_SECONDS`
- `LOG_LEVEL`

## Run the dashboard

```bash
streamlit run app.py
```

## Run the tests

```bash
python -m unittest discover -s tests
```

## Export behavior

The dashboard export includes:

- rank
- influencer fields
- AI analysis fields
- score breakdown fields
- applied filters
- export timestamp

Both CSV and Excel downloads preserve the filtered dashboard view.

## Logging

Logging is configured through `utils/logging_config.py`.

Set `LOG_LEVEL` to control verbosity, for example:

```bash
export LOG_LEVEL=DEBUG
```

## Screenshots

Screenshots are not bundled in this environment, but the project includes a
placeholder folder at `docs/screenshots/`.

Add captures such as:

- `docs/screenshots/dashboard-overview.png`
- `docs/screenshots/filters-and-export.png`
- `docs/screenshots/detail-expander.png`

If you add them, reference them here with standard Markdown image links.

## Deployment instructions

### Local deployment

1. Clone the repository.
2. Create and configure `.env`.
3. Install dependencies.
4. Run `streamlit run app.py`.

### Streamlit Community Cloud

1. Push the repository to GitHub.
2. Add the `.env` values as Streamlit secrets or environment variables.
3. Set the app entrypoint to `app.py`.
4. Deploy from the Streamlit dashboard.

### Production notes

- Keep the xAI API key out of source control.
- Use a dedicated `.env` or secret manager for deployment.
- Set a reasonable `LOG_LEVEL` for the runtime environment.

## Clean architecture notes

- UI code stays in `ui/`
- business logic stays in `services/`
- domain objects stay in `models/`
- file parsing stays in `repositories/`
- shared utilities stay in `utils/`

This keeps the codebase SOLID and easy to extend with future integrations.

## Sample data

A sample workbook is available at:

- `example/sample_influencers.xlsx`

## Troubleshooting

- **Missing API key**: verify `XAI_API_KEY` is set in `.env`.
- **No results after upload**: check whether filters are too restrictive.
- **Export looks empty**: confirm that the filtered result list contains rows.
