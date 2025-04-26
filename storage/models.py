"""Pydantic models for MongoDB schema validation.

This module defines the Pydantic models that represent the MongoDB document schemas.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from db_utils import MongoModel, PyObjectId


class UserBase(BaseModel):
    """Base User model with common fields."""
    name: str
    phone_number: int
    company: str
    product_interest: str
    email: Optional[str] = None


class UserCreate(UserBase):
    """User creation model."""
    pass


class UserUpdate(BaseModel):
    """User update model with all fields optional."""
    name: Optional[str] = None
    phone_number: Optional[int] = None
    company: Optional[str] = None
    product_interest: Optional[str] = None
    email: Optional[str] = None
    expiry_date: Optional[datetime] = None


class User(MongoModel, UserBase):
    """Complete User model with MongoDB ID and timestamps."""
    expiry_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "phone_number": 9381273567,
                "company": "Example Corp",
                "product_interest": "Cloud Services",
                "email": "john@example.com",
                "expiry_date": "2023-12-31T00:00:00.000Z"
            }
        }


class CallLogBase(BaseModel):
    """Base Call Log model with common fields."""
    user_id: PyObjectId = Field(..., alias="user_id")
    call_sid: str
    status: str
    duration: Optional[int] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None


class CallLogCreate(CallLogBase):
    """Call Log creation model."""
    pass


class CallLogUpdate(BaseModel):
    """Call Log update model with all fields optional."""
    status: Optional[str] = None
    duration: Optional[int] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None


class CallLog(MongoModel, CallLogBase):
    """Complete Call Log model with MongoDB ID and timestamps."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "call_sid": "CA123456789abcdef",
                "status": "completed",
                "duration": 120,
                "recording_url": "https://example.com/recordings/123",
                "notes": "Customer interested in cloud services"
            }
        }