"""MongoDB utility functions for common database operations.

This module provides utility functions for common database operations using Motor and Pydantic.
"""

from typing import List, Dict, Any, TypeVar, Generic, Type, Optional, Union
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from datetime import datetime

from db_config import get_database

# Type variable for generic model operations
ModelType = TypeVar('ModelType', bound=BaseModel)


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid ObjectId')
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, _schema_generator, _field_schema):
        return {"type": "string"}


class MongoModel(BaseModel):
    """Base model for MongoDB documents with ID handling."""
    id: Optional[PyObjectId] = None

    model_config = {
        "json_encoders": {
            ObjectId: str
        },
        "populate_by_name": True
    }

    def dict(self, **kwargs):
        """Convert model to dict with proper ObjectId handling."""
        doc = super().dict(**kwargs)
        # Convert id to str if it exists
        if doc.get('id'):
            doc['_id'] = doc.pop('id')
        return doc


class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations."""
    
    def __init__(self, model: Type[ModelType], collection_name: str):
        """Initialize with model class and collection name.
        
        Args:
            model: The Pydantic model class
            collection_name: Name of the MongoDB collection
        """
        self.model = model
        self.collection_name = collection_name
    
    async def get_collection(self) -> AsyncIOMotorCollection:
        """Get the collection for this model."""
        db = await get_database()
        return db[self.collection_name]
    
    async def create(self, obj_in: Union[ModelType, Dict[str, Any]]) -> ModelType:
        """Create a new document.
        
        Args:
            obj_in: The object to create, either as a Pydantic model or dict
            
        Returns:
            The created object as a Pydantic model
        """
        if isinstance(obj_in, dict):
            obj_data = obj_in
        else:
            obj_data = obj_in.dict(exclude_unset=True)
            
        # Add creation timestamp
        obj_data['created_at'] = datetime.utcnow()
        obj_data['updated_at'] = obj_data['created_at']
        
        collection = await self.get_collection()
        result = await collection.insert_one(obj_data)
        
        # Get the created document
        created_doc = await collection.find_one({'_id': result.inserted_id})
        
        # Convert _id to id for the model
        if created_doc and '_id' in created_doc:
            created_doc['id'] = created_doc.pop('_id')
            
        return self.model(**created_doc)
    
    async def get(self, id: str) -> Optional[ModelType]:
        """Get a document by ID.
        
        Args:
            id: The document ID
            
        Returns:
            The document as a Pydantic model or None if not found
        """
        collection = await self.get_collection()
        doc = await collection.find_one({'_id': ObjectId(id)})
        
        if doc is None:
            return None
            
        # Convert _id to id for the model
        if '_id' in doc:
            doc['id'] = doc.pop('_id')
            
        return self.model(**doc)
    
    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get multiple documents with pagination.
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            
        Returns:
            List of documents as Pydantic models
        """
        collection = await self.get_collection()
        cursor = collection.find().skip(skip).limit(limit)
        
        results = []
        async for doc in cursor:
            # Convert _id to id for the model
            if '_id' in doc:
                doc['id'] = doc.pop('_id')
            results.append(self.model(**doc))
            
        return results
    
    async def update(self, id: str, obj_in: Union[ModelType, Dict[str, Any]]) -> Optional[ModelType]:
        """Update a document.
        
        Args:
            id: The document ID
            obj_in: The update data, either as a Pydantic model or dict
            
        Returns:
            The updated document as a Pydantic model or None if not found
        """
        collection = await self.get_collection()
        
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        # Remove id if present in update data
        if 'id' in update_data:
            del update_data['id']
            
        # Add update timestamp
        update_data['updated_at'] = datetime.utcnow()
        
        await collection.update_one(
            {'_id': ObjectId(id)},
            {'$set': update_data}
        )
        
        return await self.get(id)
    
    async def delete(self, id: str) -> bool:
        """Delete a document.
        
        Args:
            id: The document ID
            
        Returns:
            True if document was deleted, False otherwise
        """
        collection = await self.get_collection()
        result = await collection.delete_one({'_id': ObjectId(id)})
        return result.deleted_count > 0
    
    async def find_one(self, query: Dict[str, Any]) -> Optional[ModelType]:
        """Find a single document by query.
        
        Args:
            query: The query filter
            
        Returns:
            The document as a Pydantic model or None if not found
        """
        collection = await self.get_collection()
        doc = await collection.find_one(query)
        
        if doc is None:
            return None
            
        # Convert _id to id for the model
        if '_id' in doc:
            doc['id'] = doc.pop('_id')
            
        return self.model(**doc)
    
    async def find_many(self, query: Dict[str, Any], *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Find multiple documents by query with pagination.
        
        Args:
            query: The query filter
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            
        Returns:
            List of documents as Pydantic models
        """
        collection = await self.get_collection()
        cursor = collection.find(query).skip(skip).limit(limit)
        
        results = []
        async for doc in cursor:
            # Convert _id to id for the model
            if '_id' in doc:
                doc['id'] = doc.pop('_id')
            results.append(self.model(**doc))
            
        return results