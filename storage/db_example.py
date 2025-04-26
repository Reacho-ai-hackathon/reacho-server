"""Example usage of MongoDB with Motor and Pydantic.

This module demonstrates basic CRUD operations using the new MongoDB setup for all major models.
"""

import asyncio
from datetime import datetime
from typing import List

from storage.db_config import init_db, close_mongo_connection
from models import User, UserCreate, UserUpdate, Campaign, CampaignCreate, CampaignUpdate, Call, CallCreate, CallUpdate, CallMetadata, CallMetadataCreate, CallMetadataUpdate
from db_utils import CRUDBase

# CRUD handlers for each model
class UserCRUD(CRUDBase[User]):
    def __init__(self):
        super().__init__(User, "users")

class CampaignCRUD(CRUDBase[Campaign]):
    def __init__(self):
        super().__init__(Campaign, "campaigns")

class CallCRUD(CRUDBase[Call]):
    def __init__(self):
        super().__init__(Call, "calls")


class CallMetadataCRUD(CRUDBase[CallMetadata]):
    def __init__(self):
        super().__init__(CallMetadata, "call_metadata")

user_crud = UserCRUD()
campaign_crud = CampaignCRUD()
call_crud = CallCRUD()
call_metadata_crud = CallMetadataCRUD()

# Example CRUD operations for User
async def example_create_user() -> User:
    user_data = UserCreate(
        name="Example User",
        age=28,
        gender="male",
        phno="9876543210",
        email="example@example.com",
        organisation="Example Corp",
        designation="Engineer"
    )
    user = await user_crud.create(user_data)
    print(f"Created user: {user.name} with ID: {user.id}")
    return user

# Example CRUD operations for Campaign
async def example_create_campaign() -> Campaign:
    campaign_data = CampaignCreate(
        name="Summer Promo",
        description="Summer campaign",
        status="active",
        start_date=datetime.utcnow()
    )
    campaign = await campaign_crud.create(campaign_data)
    print(f"Created campaign: {campaign.name} with ID: {campaign.id}")
    return campaign

# Example CRUD operations for Call
async def example_create_call(user_id, campaign_id) -> Call:
    call_data = CallCreate(
        user_id=user_id,
        call_sid="CA123456789abcdef",
        stream_sid="ST123456789abcdef",
        phno="+1234567890",
        campaign_id=campaign_id,
        status="initiated"
    )
    call = await call_crud.create(call_data)
    print(f"Created call with ID: {call.id}")
    return call


# Example CRUD operations for CallMetadata
async def example_create_call_metadata(call_id) -> CallMetadata:
    call_metadata_data = CallMetadataCreate(
        call_id=call_id,
        summary="Test summary",
        chunks=["chunk1", "chunk2"]
    )
    call_metadata = await call_metadata_crud.create(call_metadata_data)
    print(f"Created call metadata with ID: {call_metadata.id}")
    return call_metadata

async def run_examples():
    print("Initializing database...")
    await init_db()
    try:
        user = await example_create_user()
        campaign = await example_create_campaign()
        call = await example_create_call(user.id, campaign.id)
        call_log = await example_create_call_log(user.id)
        call_metadata = await example_create_call_metadata(call.id)
        # Add more CRUD operations as needed for update, get, list, delete
    finally:
        await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(run_examples())