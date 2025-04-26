"""Repository implementations for MongoDB collections.

This module provides concrete repository implementations for specific collections.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from storage.models import User, UserCreate, UserUpdate, CallLog, CallLogCreate, CallLogUpdate
from storage.db_utils import CRUDBase


class UserRepository(CRUDBase[User]):
    """Repository for User collection operations."""
    
    def __init__(self):
        super().__init__(User, "users")
    
    async def find_by_phone(self, phone_number: int) -> Optional[User]:
        """Find a user by phone number.
        
        Args:
            phone_number: The phone number to search for
            
        Returns:
            The user if found, None otherwise
        """
        return await self.find_one({"phone_number": phone_number})
    
    async def find_by_company(self, company: str) -> List[User]:
        """Find users by company name.
        
        Args:
            company: The company name to search for
            
        Returns:
            List of users from the specified company
        """
        return await self.find_many({"company": company})
    
    async def find_by_product_interest(self, product_interest: str) -> List[User]:
        """Find users by product interest.
        
        Args:
            product_interest: The product interest to search for
            
        Returns:
            List of users interested in the specified product
        """
        # Use regex to find partial matches in product_interest field
        return await self.find_many({"product_interest": {"$regex": product_interest, "$options": "i"}})


class CallLogRepository(CRUDBase[CallLog]):
    """Repository for CallLog collection operations."""
    
    def __init__(self):
        super().__init__(CallLog, "call_logs")
    
    async def find_by_user(self, user_id: str) -> List[CallLog]:
        """Find call logs for a specific user.
        
        Args:
            user_id: The user ID to search for
            
        Returns:
            List of call logs for the specified user
        """
        return await self.find_many({"user_id": user_id})
    
    async def find_by_status(self, status: str) -> List[CallLog]:
        """Find call logs by status.
        
        Args:
            status: The call status to search for
            
        Returns:
            List of call logs with the specified status
        """
        return await self.find_many({"status": status})
    
    async def find_recent_calls(self, limit: int = 10) -> List[CallLog]:
        """Find recent calls, sorted by creation date.
        
        Args:
            limit: Maximum number of calls to return
            
        Returns:
            List of recent call logs
        """
        collection = await self.get_collection()
        cursor = collection.find().sort("created_at", -1).limit(limit)
        
        results = []
        async for doc in cursor:
            # Convert _id to id for the model
            if '_id' in doc:
                doc['id'] = doc.pop('_id')
            results.append(self.model(**doc))
            
        return results


# Create singleton instances for repositories
user_repository = UserRepository()
call_log_repository = CallLogRepository()