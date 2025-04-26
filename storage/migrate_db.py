"""Migration script to transition from PyMongo to Motor+Pydantic.

This script helps migrate existing data from the old PyMongo setup to the new
Motor+Pydantic setup. It reads data from the old database and inserts it into
the new database with proper schema validation.
"""

import asyncio
import logging
from datetime import datetime

# Import old database setup
from storage.db_initialisation import get_database as get_old_db

# Import new database setup
from storage.db_config import init_db, close_mongo_connection
from storage.models import User, UserCreate
from storage.repositories import user_repository

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_users():
    """Migrate users from old database to new database."""
    logger.info("Starting user migration...")
    
    # Get old database
    old_db = get_old_db()
    old_users = old_db["users"].find()
    
    # Initialize new database
    await init_db()
    
    migrated_count = 0
    error_count = 0
    
    try:
        for old_user in old_users:
            try:
                # Convert old user to new user model
                user_data = {
                    "name": old_user.get("name", ""),
                    "phno": old_user.get("phno", 0),
                    "company": old_user.get("company", ""),
                    "product_interest": old_user.get("product_interest", "")
                }
                
                # Add optional fields if they exist
                if "email" in old_user:
                    user_data["email"] = old_user["email"]
                
                # Create user model
                user_create = UserCreate(**user_data)
                
                # Create user in new database
                new_user = await user_repository.create(user_create)
                
                # If expiry_date exists, update the user with it
                if "expiry_date" in old_user:
                    await user_repository.update(str(new_user.id), {"expiry_date": old_user["expiry_date"]})
                
                logger.info(f"Migrated user: {new_user.name}")
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"Error migrating user {old_user.get('name', 'Unknown')}: {str(e)}")
                error_count += 1
    
    finally:
        # Close database connection
        await close_mongo_connection()
    
    logger.info(f"User migration complete. Migrated: {migrated_count}, Errors: {error_count}")


async def main():
    """Run all migrations."""
    logger.info("Starting database migration...")
    await migrate_users()
    logger.info("Database migration complete.")


if __name__ == "__main__":
    asyncio.run(main())