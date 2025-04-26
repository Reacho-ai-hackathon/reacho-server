"""User model for MongoDB schema validation.

This module defines the Pydantic model that represents the User document schema.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from storage.db_utils import MongoModel, PyObjectId

class UserBase(BaseModel):
    name: str
    age: int
    gender: str
    phno: str
    email: str
    organisation: str
    designation: str

class UserCreate(UserBase):
    """User creation model."""
    pass

class UserUpdate(BaseModel):
    """User update model with all fields optional."""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    phno: Optional[str] = None
    email: Optional[str] = None
    organisation: Optional[str] = None
    designation: Optional[str] = None

class User(MongoModel, UserBase):
    """Complete User model with MongoDB ID and timestamps."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "John Doe",
                "age": 30,
                "gender": "male",
                "phno": "9381273567",
                "email": "john@example.com",
                "organisation": "Example Corp",
                "designation": "Engineer",
                "created_at": "2023-12-31T00:00:00.000Z",
                "updated_at": "2023-12-31T00:00:00.000Z"
            }
        }