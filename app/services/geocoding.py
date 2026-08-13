import logging
import time

import requests

from app.config import GEOCODE_URL, GOOGLE_MAPS_API_KEY

logger = logging.getLogger(__name__)

ERR_MISSING_ADDRESS = "MISSING_ADDRESS"
ERR_ADDRESS_NOT_FOUND = "ADDRESS_NOT_FOUND"
ERR_SERVICE_UNREACHABLE = "GEOCODING_SERVICE_UNREACHABLE"
ERR_API_ERROR = "GEOCODING_API_ERROR"


def _get_component(components, component_type, name_field="long_name"):
    return next(
        (c.get(name_field) for c in components if component_type in c.get("types", [])),
        None,
    )


def geocode_address(address: str, max_retries: int = 3):
    if not address or not address.strip():
        return None, "No geocode address provided for this consignment.", ERR_MISSING_ADDRESS

    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(GEOCODE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(
                "Geocoding HTTP error for '%s' on attempt %d/%d: %s",
                address, attempt, max_retries, e,
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None, "Geocoding service unreachable. Please try again.", ERR_SERVICE_UNREACHABLE

        status = data.get("status")

        if status == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            components = result.get("address_components", [])
            return {
                "latitude": location["lat"],
                "longitude": location["lng"],
                "pincode": _get_component(components, "postal_code"),
                "locality": _get_component(components, "sublocality_level_1"),
                "area": _get_component(components, "sublocality_level_2"),
                "location_type": result.get("geometry", {}).get("location_type"),
                "partial_match": result.get("partial_match", False),
                "types": result.get("types", []),
                "formatted_address": result.get("formatted_address"),
                "place_id": result.get("place_id"),
                "street_number": _get_component(components, "street_number"),
                "route_name": _get_component(components, "route"),
                "district": _get_component(components, "administrative_area_level_2"),
                "state": _get_component(components, "administrative_area_level_1"),
                "country_code": _get_component(components, "country", "short_name"),
            }, None, None

        if status == "ZERO_RESULTS":
            return None, "Address could not be found. Please check and correct the address.", ERR_ADDRESS_NOT_FOUND

        if status in ("OVER_QUERY_LIMIT", "UNKNOWN_ERROR"):
            logger.error(
                "Geocoding transient failure for '%s' on attempt %d/%d: status=%s",
                address, attempt, max_retries, status,
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None, (
                f"Address lookup failed ({status}) after {max_retries} attempts. "
                "Please try again shortly."
            ), ERR_SERVICE_UNREACHABLE

        logger.error(
            "Geocoding failed for '%s': status=%s error=%s",
            address, status, data.get("error_message"),
        )
        return None, f"Address lookup failed ({status}). Please verify the address.", ERR_API_ERROR

    return None, "Address lookup failed after multiple attempts.", ERR_SERVICE_UNREACHABLE


def derive_exception_flag(geocode_result: dict):
    if geocode_result.get("partial_match"):
        return "PARTIAL_MATCH"
    location_type = geocode_result.get("location_type")
    if location_type == "APPROXIMATE":
        return "APPROXIMATE_LOCATION"
    if location_type == "GEOMETRIC_CENTER":
        return "GEOMETRIC_CENTER_ONLY"
    return None


def derive_is_commercial(geocode_result: dict):
    types = geocode_result.get("types", [])
    return "establishment" in types or "point_of_interest" in types
