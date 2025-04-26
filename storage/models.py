"""Pydantic models for MongoDB schema validation.

This module defines the Pydantic models that represent the MongoDB document schemas.
This file is maintained for backward compatibility and imports from individual model files.
"""

# Import all models from the models package
from storage.models import (
    # User models
    User, UserBase, UserCreate, UserUpdate,
    # Call Log models
    CallLog, CallLogBase, CallLogCreate, CallLogUpdate,
    # Campaign models
    Campaign, CampaignBase, CampaignCreate, CampaignUpdate, CampaignStatus,
    # Call models
    Call, CallBase, CallCreate, CallUpdate, CallStatus,
    # Call Metadata models
    CallMetadata, CallMetadataBase, CallMetadataCreate, CallMetadataUpdate
)

# Re-export all models
__all__ = [
    # User models
    'User', 'UserBase', 'UserCreate', 'UserUpdate',
    # Call Log models
    'CallLog', 'CallLogBase', 'CallLogCreate', 'CallLogUpdate',
    # Campaign models
    'Campaign', 'CampaignBase', 'CampaignCreate', 'CampaignUpdate', 'CampaignStatus',
    # Call models
    'Call', 'CallBase', 'CallCreate', 'CallUpdate', 'CallStatus',
    # Call Metadata models
    'CallMetadata', 'CallMetadataBase', 'CallMetadataCreate', 'CallMetadataUpdate'
]