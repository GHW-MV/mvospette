# Territory Mapping Starter

Lightweight pipeline that follows the Codex directive in `ref/chatgpt convo with directive.txt` to join ZIP metadata with rep activity, infer prospective owners, and persist everything to a local SQLite database and CSV export.

## What it does
- Normalizes ZIPs to 5-digit strings and loads the ZIP master (`static/uszips.csv`).
- Loads rep/ZIP activity (`static/Zipcodes_Deal_Count_By_Rep.csv`), aggregates by ZIP + email, and keeps only valid ZIPs.
- Assigns active owners directly; infers prospective owners for unowned ZIPs using magnitude + dominance scoring (per directive Section 5).
- Writes three tables into `data/territory.db` and exports `data/territory_assignments.csv` for mapping/reporting.

## Quickstart
```bash
python src/territory_pipeline.py \
  --radius-miles 25 \
  --max-neighbors 15
```
- Inputs: `static/uszips.csv`, `static/Zipcodes_Deal_Count_By_Rep.csv`
- Outputs: `data/territory.db`, `data/territory_assignments.csv`
- Adjust `--radius-miles` / `--max-neighbors` to tune inference breadth.

### Interactive map (Streamlit)
```bash
pip install -r requirements.txt
streamlit run src/streamlit_app.py
```
- Live filter by ZIP prefix or city name.
- Toggle Active / Prospective / All.
- Includes scatter layers for active/prospective and a heat layer driven by `deal_count`.

## Milestones (progress + testing)
- Data ingestion wired: ZIP master + rep activity normalization (done).
- Local persistence: SQLite schema + CSV export generated (done).
- Inference: magnitude/dominance prospective-owner engine implemented (done).
- Validation: smoke tests for normalization/selection/inference via `python -m unittest` (ready to run).
- Next: map UX layer (Mapbox/Leaflet/Streamlit) once dataset is validated.

## Testing
- Run unit tests: `python -m unittest discover -s tests -p "test*.py"`
- Quick data sanity checks:
  - Confirm DB tables exist: `sqlite3 data/territory.db '.tables'`
  - Spot-check sample rows: `sqlite3 data/territory.db 'SELECT * FROM territory_assignments LIMIT 5;'`

## Outputs to expect
- `data/territory.db`
  - `zip_master`: authoritative ZIP metadata
  - `rep_activity`: normalized rep/ZIP counts with statuses
  - `territory_assignments`: one row per ZIP with active or prospective owner + inference reason
- `data/territory_assignments.csv`: flattened export mirroring `territory_assignments`

## Notes
- Directive alignment: mirrors Sections 1–8 near the tail of `ref/chatgpt convo with directive.txt` (source data, normalization, fusion, inference, outputs).
- Re-running the pipeline is idempotent; tables are cleared and repopulated each run.
