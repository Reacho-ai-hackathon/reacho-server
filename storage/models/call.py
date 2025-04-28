"""Call model for MongoDB schema validation.

This module defines the Pydantic models that represent the Call document schema.
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel,Field
from storage.db_utils import MongoModel, PyObjectId


# Define call status type
CallStatus = Literal["initiated", "ringing", "in-progress", "completed", "failed", "busy", "no-answer", "canceled"]


class CallBase(BaseModel):
    user_id: PyObjectId = Field(..., description="Foreign key reference to User.id")
    call_sid: str
    stream_sid: str
    phno: str
    campaign_id: PyObjectId = Field(..., description="Foreign key reference to Campaign.id")
    status: CallStatus
    call_start_time: Optional[datetime] = None
    call_end_time: Optional[datetime] = None
    sentiment: Optional[str] = None


class CallCreate(CallBase):
    """Call creation model."""
    pass


class CallUpdate(BaseModel):
    """Call update model with all fields optional."""
    status: Optional[CallStatus] = None
    call_start_time: Optional[datetime] = None
    call_end_time: Optional[datetime] = None
    sentiment: Optional[str] = None


class Call(MongoModel, CallBase):
    """Complete Call model with MongoDB ID and timestamps."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "call_sid": "CA123456789abcdef",
                "stream_sid": "ST123456789abcdef",
                "phno": "+1234567890",
                "campaign_id": "507f1f77bcf86cd799439022",
                "status": "completed",
                "call_start_time": "2023-06-01T10:00:00.000Z",
                "call_end_time": "2023-06-01T10:05:30.000Z",
                "sentiment": "positive"
            }
        }