"""Health check route.

The one endpoint Phase 1 exposes. It answers a single question — "is this API
process alive and serving?" — and deliberately contains no business logic, no
database access and no service call, because there is nothing for those layers
to do here.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response body for ``GET /api/v1/health``."""

    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API is up.

    Declaring a ``response_model`` rather than returning a bare dict means the
    shape is validated on the way out and appears in the generated OpenAPI
    schema, which is the pattern every later endpoint will follow.
    """
    return HealthResponse(status="ok")
