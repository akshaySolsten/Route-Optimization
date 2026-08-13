import logging
import time
from datetime import datetime, timezone

import pygeohash as pgh

from app.config import GEOHASH_BUILDING_LEN, GEOHASH_LOCALITY_LEN, GOOGLE_MAPS_API_KEY
from app.db.bigquery import fetch_rows_by_consignment_ids, merge_routing_rows
from app.db.firestore import get_consignments_by_id, upsert_consignments_routing
from app.services.address import (
    clean_address_for_geocoding,
    format_geocode_address,
    normalize_to_single_line,
)
from app.services.geocoding import (
    derive_exception_flag,
    derive_is_commercial,
    geocode_address,
)

logger = logging.getLogger(__name__)


def build_row(
    drs_no,
    drs_id,
    driver_numeric_id,
    consignment_id,
    receiver_address,
    receiver_name,
    geocode_address_str,
    latitude,
    longitude,
    locality,
    area,
    geohash_exact,
    pincode,
    exception_flag,
    is_commercial,
    formatted_address=None,
    place_id=None,
    location_type=None,
    street_number=None,
    route_name=None,
    district=None,
    state=None,
    country_code=None,
    geocode_status="success",
    geocode_error=None,
):
    return {
        "drsNo": drs_no,
        "drsId": drs_id,
        "driverNumericId": str(driver_numeric_id) if driver_numeric_id is not None else "0",
        "consignmentId": consignment_id,
        "receiverAddress": receiver_address,
        "receiverName": receiver_name,
        "geocode_address": geocode_address_str,
        "starting_address": "PENDING_OPTIMIZATION",
        "starting_latitude": 0.0,
        "starting_longitude": 0.0,
        "latitude": latitude,
        "longitude": longitude,
        "locality": locality or "UNKNOWN",
        "area": area or "UNKNOWN",
        "geohash_locality_loc": geohash_exact[:GEOHASH_LOCALITY_LEN] if geohash_exact else None,
        "geohash_building_loc": geohash_exact[:GEOHASH_BUILDING_LEN] if geohash_exact else None,
        "geohash_exact_loc": geohash_exact,
        "pincode": pincode,
        "exception_flag": exception_flag,
        "is_commercial": is_commercial,
        "formatted_address": formatted_address,
        "place_id": place_id,
        "location_type": location_type,
        "street_number": street_number,
        "route_name": route_name,
        "district": district,
        "state": state,
        "country_code": country_code,
        "geocode_status": geocode_status,
        "geocode_error": geocode_error,
    }


def _failed_row(
    drs_no, drs_id, driver_numeric_id, consignment_id,
    receiver_address, receiver_name, geocode_address_str, reason,
):
    return build_row(
        drs_no, drs_id, driver_numeric_id, consignment_id,
        receiver_address, receiver_name, geocode_address_str,
        None, None, None, None, None, None, None, False,
        geocode_status="failed",
        geocode_error=reason,
    )


def save_consignments_pipeline(consignment_ids):
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY environment variable is not set.")

    start_dt = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    logger.info(
        "save_consignments_pipeline started at %s for %d requested consignment id(s)",
        start_dt.isoformat(), len(consignment_ids),
    )

    seen = set()
    deduped_ids = []
    for cid in consignment_ids:
        if cid and cid not in seen:
            seen.add(cid)
            deduped_ids.append(cid)

    docs, not_found_ids = get_consignments_by_id(deduped_ids)
    rows_to_merge = []
    failures = [{"consignmentId": cid, "reason": "Consignment not found."} for cid in not_found_ids]
    saved_count = 0

    for doc in docs:
        data = doc.to_dict() or {}
        consignment_id = data.get("consignmentId") or doc.id
        receiver = data.get("receiver") or {}

        receiver_name = clean_address_for_geocoding(normalize_to_single_line(str(receiver.get("name") or "")))
        receiver_address = clean_address_for_geocoding(normalize_to_single_line(str(receiver.get("address") or "")))
        drs_no = str(data.get("drsNo") or "").strip()
        drs_id = str(data.get("drsId") or "").strip()
        driver_numeric_id = data.get("driverNumericId")

        if receiver_name and receiver_address:
            geocode_address_str = format_geocode_address(receiver_name, receiver_address)
        else:
            geocode_address_str = receiver_address or receiver_name

        if not geocode_address_str:
            reason = "Receiver address and name are both missing."
            failures.append({"consignmentId": consignment_id, "reason": reason})
            rows_to_merge.append(_failed_row(
                drs_no, drs_id, driver_numeric_id, consignment_id,
                receiver_address, receiver_name, geocode_address_str, reason,
            ))
            continue

        geocode_result, error_reason, _error_code = geocode_address(geocode_address_str)
        if geocode_result is None:
            logger.warning("Geocoding failed for consignment %s: %s", consignment_id, error_reason)
            failures.append({"consignmentId": consignment_id, "reason": error_reason})
            rows_to_merge.append(_failed_row(
                drs_no, drs_id, driver_numeric_id, consignment_id,
                receiver_address, receiver_name, geocode_address_str, error_reason,
            ))
            continue

        geohash_exact = pgh.encode(geocode_result["latitude"], geocode_result["longitude"], precision=8)
        rows_to_merge.append(build_row(
            drs_no, drs_id, driver_numeric_id, consignment_id,
            receiver_address, receiver_name, geocode_address_str,
            geocode_result["latitude"], geocode_result["longitude"],
            geocode_result.get("locality"), geocode_result.get("area"),
            geohash_exact, geocode_result.get("pincode"),
            derive_exception_flag(geocode_result),
            derive_is_commercial(geocode_result),
            formatted_address=geocode_result.get("formatted_address"),
            place_id=geocode_result.get("place_id"),
            location_type=geocode_result.get("location_type"),
            street_number=geocode_result.get("street_number"),
            route_name=geocode_result.get("route_name"),
            district=geocode_result.get("district"),
            state=geocode_result.get("state"),
            country_code=geocode_result.get("country_code"),
        ))
        saved_count += 1

    if rows_to_merge:
        merge_routing_rows(rows_to_merge)
        bq_rows = fetch_rows_by_consignment_ids([r["consignmentId"] for r in rows_to_merge])
        upsert_consignments_routing(bq_rows)

    end_dt = datetime.now(timezone.utc)
    duration_seconds = round(time.perf_counter() - start_perf, 3)
    logger.info(
        "save_consignments_pipeline finished at %s (duration: %.3fs) - saved=%d failed=%d synced_rows=%d",
        end_dt.isoformat(), duration_seconds, saved_count, len(failures), len(rows_to_merge),
    )

    return {
        "saved": saved_count,
        "failed": len(failures),
        "failures": failures,
        "started_at": start_dt.isoformat(),
        "finished_at": end_dt.isoformat(),
        "duration_seconds": duration_seconds,
    }
