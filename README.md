# Route Optimization

Single FastAPI service on Cloud Run that geocodes consignments and builds a delivery sequence for a DRS.

It replaces the previous two Cloud Functions (`save_consignments` and `run_sorting`) with one service and two HTTP endpoints.

## What it does

1. **Save** — load consignments from Firestore, geocode receiver addresses with Google Maps, and upsert rows into BigQuery. Firestore write-back of `consignments_routing` is currently commented out.
2. **Sort** — load active consignments for a DRS, solve an open-path TSP from the DRS starting point with OR-Tools, and write sequence/cluster fields to BigQuery. Firestore write-back is currently commented out.

Typical order: save consignments first, then run sorting when the driver/hub starting point exists.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `POST` | `/save-consignments` | Geocode and persist consignments |
| `POST` | `/run-sorting` | Optimize route order for a DRS |
| `GET` | `/docs` | OpenAPI / Swagger UI |
| `GET` | `/redoc` | ReDoc |

### Save consignments

```http
POST /save-consignments
Content-Type: application/json

{ "consignmentIds": ["id1", "id2"] }
```

A single id is also accepted: `{ "consignmentId": "id1" }`.

Success (`200`):

```json
{
  "status": "ok",
  "saved": 2,
  "failed": 0,
  "failures": [],
  "started_at": "...",
  "finished_at": "...",
  "duration_seconds": 1.23
}
```

`status` is `partial_success` when some ids fail geocoding or are missing. Failures are listed as `{ "consignmentId", "reason" }`. Missing body returns `400`; unexpected errors return `500`.

### Run sorting

```http
POST /run-sorting
Content-Type: application/json

{ "drsno": "DRS123" }
```

Query param `?drsno=` is also accepted.

Success (`200`):

```json
{
  "status": "ok",
  "drsNo": "DRS123",
  "optimized_count": 40,
  "starting_time": "...",
  "ending_time": "...",
  "duration_seconds": 4.56
}
```

If there are no active BigQuery rows for that DRS, `optimized_count` is `0` and a `message` is returned.

## Data stores

| Store | Use |
|-------|-----|
| Firestore `consignments` | Source consignment documents |
| Firestore `drs_starting_point` | Hub/depot lat/lon and address, keyed by DRS number |
| Firestore `consignments_routing` | Routing snapshot write-back (commented out in the pipelines) |
| BigQuery `consignments_routing` | System of record for geocode fields, sequence, and clusters |

Save writes geocode data and leaves grouping as `UNASSIGNED` with `starting_*` placeholders. Sort fills `geohash_group_id`, `planned_*` / `actual_*` sequence, and the real starting point.

## Layout

```
app/
  main.py                 FastAPI app, CORS, /health
  config.py               Environment variables
  schemas.py              Request models
  routers/                HTTP handlers
    save.py
    sorting.py
  services/               Business logic
    address.py            Address cleanup
    geocoding.py          Google Maps geocode
    save.py               Save pipeline
    tsp.py                OR-Tools open-path TSP
    sorting.py            Sort pipeline
  db/                     Data access
    clients.py            Shared BQ / Firestore clients
    firestore.py          Firestore reads/writes
    bigquery.py           BigQuery reads/writes
Dockerfile
requirements.txt
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_MAPS_API_KEY` | Yes (save) | — | Geocoding API key |
| `BQ_PROJECT` | No | `prj-dev-hermes` | GCP project for BigQuery |
| `BQ_DATASET` | No | `Hermes_Exports` | BigQuery dataset |
| `BQ_TABLE` | No | `consignments_routing_test` | BigQuery table |
| `FIRESTORE_PROJECT` | No | same as `BQ_PROJECT` | Firestore project |
| `PORT` | Cloud Run | `8080` | HTTP port |

The runtime service account needs BigQuery Data Editor (or equivalent query/update on the table) and Firestore read/write on the collections above.

## Local run

Python 3.11+ and Application Default Credentials (for example `gcloud auth application-default login`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:GOOGLE_MAPS_API_KEY = "YOUR_KEY"
$env:BQ_PROJECT = "prj-dev-hermes"
$env:BQ_DATASET = "Hermes_Exports"
$env:BQ_TABLE = "consignments_routing_test"
$env:FIRESTORE_PROJECT = "prj-dev-hermes"

uvicorn app.main:app --reload --port 8080
```

Then open http://localhost:8080/docs or:

```powershell
curl http://localhost:8080/health
curl -X POST http://localhost:8080/save-consignments -H "Content-Type: application/json" -d "{\"consignmentIds\":[\"id1\"]}"
curl -X POST http://localhost:8080/run-sorting -H "Content-Type: application/json" -d "{\"drsno\":\"DRS123\"}"
```

## Deploy to Cloud Run

From this directory:

```powershell
gcloud run deploy route-optimization `
  --source . `
  --region asia-south1 `
  --timeout 300 `
  --set-env-vars "BQ_PROJECT=prj-dev-hermes,BQ_DATASET=Hermes_Exports,BQ_TABLE=consignments_routing_test,FIRESTORE_PROJECT=prj-dev-hermes,GOOGLE_MAPS_API_KEY=YOUR_KEY"
```

Prefer Secret Manager for the Maps key in production instead of `--set-env-vars`. Raise `--timeout` and memory if DRS batches are large; sorting time grows with stop count (OR-Tools search is capped at 1–5 seconds internally).

After deploy, call:

- `https://<service-url>/save-consignments`
- `https://<service-url>/run-sorting`
