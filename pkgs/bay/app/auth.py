from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify access token"""
    if credentials.credentials != settings.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def get_ship_id_from_header(x_ship_id: str) -> str:
    """Get ship ID from X-Ship-ID header"""
    if not x_ship_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Ship-ID header is required",
        )
    return x_ship_id
