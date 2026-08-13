import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import SaveConsignmentsRequest
from app.services.save import save_consignments_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/save-consignments")
def save_consignments(payload: SaveConsignmentsRequest):
    consignment_ids = payload.consignmentIds
    if not consignment_ids:
        consignment_ids = [payload.consignmentId] if payload.consignmentId else []

    if not consignment_ids:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "consignmentIds (or consignmentId) is required"},
        )

    if not all(isinstance(c, str) for c in consignment_ids):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "consignmentIds must be a list of strings"},
        )

    try:
        result = save_consignments_pipeline(consignment_ids)
        status = "ok" if result["failed"] == 0 else "partial_success"
        return {"status": status, **result}
    except Exception as e:
        logger.exception("save_consignments pipeline failed")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
