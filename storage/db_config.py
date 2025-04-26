"""MongoDB configuration using Motor for async operations and Pydantic for schema validation.

This module provides the core database connection functionality using Motor, the async driver
for MongoDB, along with Pydantic for schema validation.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from pydantic import BaseModel

# MongoDB connection string
CONNECTION_STRING = os.getenv('MONGO_CONNECTION_STRING')

# Database name
DATABASE_NAME = "reacho"

# Client instance
_client: Optional[AsyncIOMotorClient] = None


async def get_database():
    """Get a reference to the database.
    
    Returns:
        AsyncIOMotorDatabase: The database instance.
    """
    return get_client()[DATABASE_NAME]


def get_client() -> AsyncIOMotorClient:
    """Get the database client.
    
    Returns:
        AsyncIOMotorClient: The database client.
    """
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(CONNECTION_STRING)
    return _client


async def close_mongo_connection():
    """Close the MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def init_db():
    """Initialize the database connection."""
    db = await get_database()
    return db