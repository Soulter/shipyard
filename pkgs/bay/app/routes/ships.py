from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.models import (
    CreateShipRequest,
    ShipResponse,
    ExecRequest,
    ExecResponse,
    ExtendTTLRequest,
    LogsResponse,
)
from app.services.ship_service import ship_service
from app.auth import verify_token

router = APIRouter()


@router.post("/ship", response_model=ShipResponse, status_code=status.HTTP_201_CREATED)
async def create_ship(
    request: CreateShipRequest,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Create a new ship environment"""
    try:
        ship = await ship_service.create_ship(request, x_session_id)
        return ShipResponse.model_validate(ship)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/ship/{ship_id}", response_model=ShipResponse)
async def get_ship(ship_id: str, token: str = Depends(verify_token)):
    """Get ship information"""
    ship = await ship_service.get_ship(ship_id)
    if not ship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )

    return ShipResponse.model_validate(ship)


@router.delete("/ship/{ship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ship(ship_id: str, token: str = Depends(verify_token)):
    """Delete ship environment"""
    success = await ship_service.delete_ship(ship_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )


@router.post("/ship/{ship_id}/exec", response_model=ExecResponse)
async def execute_operation(
    ship_id: str,
    request: ExecRequest,
    token: str = Depends(verify_token),
    x_session_id: str = Header(..., alias="X-SESSION-ID"),
):
    """Execute operation on ship"""
    response = await ship_service.execute_operation(ship_id, request, x_session_id)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=response.error
        )

    return response


@router.get("/ship/logs/{ship_id}", response_model=LogsResponse)
async def get_ship_logs(ship_id: str, token: str = Depends(verify_token)):
    """Get ship container logs"""
    logs = await ship_service.get_logs(ship_id)
    return LogsResponse(logs=logs)


@router.post("/ship/{ship_id}/extend-ttl", response_model=ShipResponse)
async def extend_ship_ttl(
    ship_id: str, request: ExtendTTLRequest, token: str = Depends(verify_token)
):
    """Extend ship TTL"""
    ship = await ship_service.extend_ttl(ship_id, request.ttl)
    if not ship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found"
        )

    return ShipResponse.model_validate(ship)
