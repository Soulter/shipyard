from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    message: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="ok", message="Bay service is running")


@router.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return HealthResponse(status="ok", message="Welcome to Bay API")
