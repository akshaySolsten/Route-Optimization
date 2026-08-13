import logging
from collections import defaultdict

from app.db.bigquery import (
    fetch_active_rows_for_drs,
    # fetch_assigned_rows_for_drs,
    write_group_assignments,
)
from app.db.firestore import get_drs_starting_point
# from app.db.firestore import upsert_consignments_routing
from app.services.tsp import solve_route_order

logger = logging.getLogger(__name__)


def compute_groups_and_sequence(rows, drs_no, start_meta):
    usable_rows = [
        r for r in rows
        if r.latitude is not None and r.longitude is not None and r.geohash_exact_loc
    ]
    skipped = len(rows) - len(usable_rows)
    if skipped:
        logger.warning("Skipping %d row(s) missing lat/lon/geohash for DRS %s.", skipped, drs_no)
    if not usable_rows:
        return []

    start_lat = start_meta.get("latitude") if start_meta else None
    start_lon = start_meta.get("longitude") if start_meta else None
    start_addr = start_meta.get("starting_address") if start_meta else "UNKNOWN"

    if not start_lat or not start_lon:
        logger.warning(
            "DRS %s has no starting coordinates in drs_starting_point. Using first stop as hub.",
            drs_no,
        )
        start_lat = usable_rows[0].latitude
        start_lon = usable_rows[0].longitude
        start_addr = start_addr or "UNKNOWN"

    ordered_rows = solve_route_order(start_lat, start_lon, usable_rows)
    inside_cluster_counts = defaultdict(int)
    updates = []

    for sequence_order, row in enumerate(ordered_rows, start=1):
        group_id = f"{drs_no}_{row.geohash_locality_loc}"
        inside_cluster_counts[group_id] += 1
        cluster_seq = inside_cluster_counts[group_id]
        updates.append({
            "sorting_id": row.sorting_id,
            "geohash_group_id": group_id,
            "starting_address": str(start_addr or "UNKNOWN"),
            "starting_latitude": float(start_lat),
            "starting_longitude": float(start_lon),
            "planned_inside_cluster_sequence": cluster_seq,
            "planned_sequence_order": sequence_order,
            "actual_inside_cluster_sequence": cluster_seq,
            "actual_sequence_order": sequence_order,
        })
    return updates


def run_sorting_pipeline(drs_no):
    start_meta = get_drs_starting_point(drs_no)
    rows = fetch_active_rows_for_drs(drs_no)

    if not rows:
        return {"optimized_count": 0, "message": f"No active consignments found in BQ for DRS {drs_no}."}

    updates = compute_groups_and_sequence(rows, drs_no, start_meta or {})
    if updates:
        write_group_assignments(updates)
        # Firestore write disabled — routing data stays in BigQuery only.
        # upsert_consignments_routing(fetch_assigned_rows_for_drs(drs_no))

    return {"optimized_count": len(updates)}
