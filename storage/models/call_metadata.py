"""Call Metadata model for MongoDB schema validation.

This module defines the Pydantic models that represent the Call Metadata document schema.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from storage.db_utils import MongoModel, PyObjectId


class CallMetadataBase(BaseModel):
    call_id: PyObjectId
    summary: str
    chunks: List[str] = []


class CallMetadataCreate(CallMetadataBase):
    """Call Metadata creation model."""
    pass


class CallMetadataUpdate(BaseModel):
    """Call Metadata update model with all fields optional."""
    summary: Optional[str] = None
    chunks: Optional[List[str]] = None


class CallMetadata(MongoModel, CallMetadataBase):
    """Complete Call Metadata model with MongoDB ID and timestamps."""
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "call_id": "507f1f77bcf86cd799439033",
                "summary": "Customer expressed interest in cloud services and requested a follow-up call next week.",
                "chunks": ["chunk_id_1", "chunk_id_2", "chunk_id_3"]
            }
        }