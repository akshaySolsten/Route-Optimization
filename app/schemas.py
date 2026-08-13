from typing import List, Optional

from pydantic import BaseModel, Field


class SaveConsignmentsRequest(BaseModel):
    consignmentIds: Optional[List[str]] = None
    consignmentId: Optional[str] = None


class RunSortingRequest(BaseModel):
    drsno: Optional[str] = Field(default=None)
