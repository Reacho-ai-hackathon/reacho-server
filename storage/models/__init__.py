"""Models package for MongoDB schema validation.

This package exports all the Pydantic models for MongoDB document schemas.
"""

from storage.models.user import User, UserBase, UserCreate, UserUpdate
from storage.models.campaign import Campaign, CampaignBase, CampaignCreate, CampaignUpdate, CampaignStatus
from storage.models.call import Call, CallBase, CallCreate, CallUpdate, CallStatus
from storage.models.call_metadata import CallMetadata, CallMetadataBase, CallMetadataCreate, CallMetadataUpdate

__all__ = [
    # User models
    'User', 'UserBase', 'UserCreate', 'UserUpdate',
    # Campaign models
    'Campaign', 'CampaignBase', 'CampaignCreate', 'CampaignUpdate', 'CampaignStatus',
    # Call models
    'Call', 'CallBase', 'CallCreate', 'CallUpdate', 'CallStatus',
    # Call Metadata models
    'CallMetadata', 'CallMetadataBase', 'CallMetadataCreate', 'CallMetadataUpdate'
]