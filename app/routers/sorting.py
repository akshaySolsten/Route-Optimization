import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.schemas import RunSortingRequest
from app.services.sorting import run_sorting_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run-sorting")
def run_sorting(
    payload: RunSortingRequest = RunSortingRequest(),
    drsno: Optional[str] = Query(default=None),
):
    start_perf = time.perf_counter()
    starting_time = datetime.now(timezone.utc)

    drs_no = payload.drsno or drsno
    if not drs_no:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "drsno is required"},
        )

    logger.info("run_sorting STARTED for DRS %s at %s", drs_no, starting_time.isoformat())

    try:
        result = run_sorting_pipeline(drs_no)
        ending_time = datetime.now(timezone.utc)
        duration_seconds = round(time.perf_counter() - start_perf, 3)
        logger.info("run_sorting COMPLETED for DRS %s | duration=%ss | %s", drs_no, duration_seconds, result)
        return {
            "status": "ok",
            "drsNo": drs_no,
            "starting_time": starting_time.isoformat(),
            "ending_time": ending_time.isoformat(),
            "duration_seconds": duration_seconds,
            **result,
        }
    except Exception as e:
        ending_time = datetime.now(timezone.utc)
        duration_seconds = round(time.perf_counter() - start_perf, 3)
        logger.exception("run_sorting FAILED for DRS %s", drs_no)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "drsNo": drs_no,
                "starting_time": starting_time.isoformat(),
                "ending_time": ending_time.isoformat(),
                "duration_seconds": duration_seconds,
            },
        )
