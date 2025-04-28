"""Call Metadata model for MongoDB schema validation.

This module defines the Pydantic models that represent the Call Metadata document schema.
"""

from typing import Literal, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field
from storage.db_utils import MongoModel, PyObjectId

RoleType = Literal["USER", "ASSISTANT", "SYSTEM"]

class CallChunk(BaseModel):
    timestamp: datetime
    role: RoleType
    content: str
    vector: Optional[List[float]] = None

class CallMetadataBase(BaseModel):
    call_id: PyObjectId
    summary: str
    chunks: List[CallChunk] = []


class CallMetadataCreate(CallMetadataBase):
    """Call Metadata creation model."""
    pass


class CallMetadataUpdate(BaseModel):
    """Call Metadata update model with all fields optional."""
    summary: Optional[str] = None
    chunks: Optional[List[CallChunk]] = None


class CallMetadata(MongoModel, CallMetadataBase):
    """Complete Call Metadata model with MongoDB ID and timestamps."""
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "call_id": "abc123",
                "summary": "Customer was satisfied after discussing pricing.",
                "chunks": [
                    {
                        "timestamp": "2025-04-26T10:00:00Z",
                        "role": "USER",
                        "content": "Hi, can I ask about pricing?",
                        "vector": [0.11, 0.23]
                    },
                    {
                        "timestamp": "2025-04-26T10:00:02Z",
                        "role": "ASSISTANT",
                        "content": "Sure! Let me help you with that.",
                        "vector": [0.09, 0.15]
                    }
                ]
            }
        }