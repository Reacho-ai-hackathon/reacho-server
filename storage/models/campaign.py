"""Campaign model for MongoDB schema validation.

This module defines the Pydantic models that represent the Campaign document schema.
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel
from storage.db_utils import MongoModel, PyObjectId


# Define campaign status type
CampaignStatus = Literal["active", "inactive", "completed", "scheduled"]


class CampaignBase(BaseModel):
    """Base Campaign model with common fields."""
    name: str
    description: str
    status: CampaignStatus
    start_date: datetime
    end_date: Optional[datetime] = None


class CampaignCreate(CampaignBase):
    """Campaign creation model."""
    pass


class CampaignUpdate(BaseModel):
    """Campaign update model with all fields optional."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


from pydantic import Field
from typing import Optional

class Campaign(MongoModel, CampaignBase):
    """Complete Campaign model with MongoDB ID and timestamps."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Summer Promotion",
                "description": "Campaign for summer product promotion",
                "status": "active",
                "start_date": "2023-06-01T00:00:00.000Z",
                "end_date": "2023-08-31T00:00:00.000Z"
            }
        }