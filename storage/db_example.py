"""Example usage of MongoDB with Motor and Pydantic.

This module demonstrates basic CRUD operations using the new MongoDB setup.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any

from db_config import init_db, close_mongo_connection
from models import User, UserCreate, UserUpdate
from db_utils import CRUDBase


# Create a CRUD handler for the User model
class UserCRUD(CRUDBase[User]):
    def __init__(self):
        super().__init__(User, "users")


# Initialize the CRUD handler
user_crud = UserCRUD()


async def example_create_user() -> User:
    """Example of creating a user."""
    user_data = UserCreate(
        name="Example User",
        phone_number=9876543210,
        company="Example Corp",
        product_interest="AI Services",
        email="example@example.com"
    )
    
    user = await user_crud.create(user_data)
    print(f"Created user: {user.name} with ID: {user.id}")
    return user


async def example_get_user(user_id: str) -> User:
    """Example of retrieving a user by ID."""
    user = await user_crud.get(user_id)
    if user:
        print(f"Retrieved user: {user.name}")
    else:
        print(f"User with ID {user_id} not found")
    return user


async def example_update_user(user_id: str) -> User:
    """Example of updating a user."""
    update_data = UserUpdate(
        product_interest="Cloud and AI Services",
        expiry_date=datetime.utcnow()
    )
    
    updated_user = await user_crud.update(user_id, update_data)
    if updated_user:
        print(f"Updated user: {updated_user.name} with new product interest: {updated_user.product_interest}")
    else:
        print(f"User with ID {user_id} not found for update")
    return updated_user


async def example_list_users() -> List[User]:
    """Example of listing users with pagination."""
    users = await user_crud.get_multi(skip=0, limit=10)
    print(f"Retrieved {len(users)} users:")
    for user in users:
        print(f"- {user.name} ({user.company}): {user.product_interest}")
    return users


async def example_find_users_by_company(company_name: str) -> List[User]:
    """Example of finding users by company name."""
    users = await user_crud.find_many({"company": company_name})
    print(f"Found {len(users)} users from {company_name}:")
    for user in users:
        print(f"- {user.name}: {user.phone_number}")
    return users


async def example_delete_user(user_id: str) -> bool:
    """Example of deleting a user."""
    success = await user_crud.delete(user_id)
    if success:
        print(f"User with ID {user_id} deleted successfully")
    else:
        print(f"User with ID {user_id} not found for deletion")
    return success


async def run_examples():
    """Run all examples in sequence."""
    # Initialize the database
    print("Initializing database...")  # Add this print statement to indicate the initialization of the database
    await init_db()
    
    try:
        # Create a new user
        user = await example_create_user();
        print(f"Created user: {user.name} with ID: {user.id}")
        
        # Get the user by ID
        # retrieved_user = await example_get_user(str(user.id))
        
        # Update the user
        # updated_user = await example_update_user(str(user.id))
        
        # List all users
        # all_users = await example_list_users()
        
        # Find users by company
        # company_users = await example_find_users_by_company("Example Corp")
        
        # Delete the user
        # await example_delete_user(str(user.id))
        
    finally:
        # Close the database connection
        await close_mongo_connection()


# Run the examples if this file is executed directly
if __name__ == "__main__":
    asyncio.run(run_examples())