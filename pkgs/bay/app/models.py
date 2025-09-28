from sqlmodel import SQLModel, Field, Column, DateTime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timezone
import uuid


# Database Models
class ShipBase(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: int = Field(default=1, description="1: running, 0: stopped")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    container_id: Optional[str] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    ttl: int = Field(description="Time to live in seconds")


class Ship(ShipBase, table=True):
    __tablename__ = "ships"


# API Request/Response Models
class ShipSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpus: Optional[float] = Field(None, gt=0, description="CPU allocation")
    memory: Optional[str] = Field(
        None, description="Memory allocation, e.g., '512m', '1g'"
    )


class CreateShipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl: int = Field(..., gt=0, description="Time to live in seconds")
    spec: Optional[ShipSpec] = Field(None, description="Ship specifications")


class ShipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: int
    created_at: datetime
    updated_at: datetime
    container_id: Optional[str]
    ip_address: Optional[str]
    ttl: int


class ExecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "fs/create_file",
        "fs/read_file",
        "fs/write_file",
        "fs/delete_file",
        "fs/list_dir",
        "ipython/exec_code",
        "shell/exec",
    ] = Field(..., description="Operation endpoint")
    payload: Optional[Dict[str, Any]] = Field(None, description="Operation payload")


class ExecResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ExtendTTLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttl: int = Field(..., gt=0, description="New TTL in seconds")


class ErrorResponse(BaseModel):
    detail: str


class LogsResponse(BaseModel):
    logs: str
