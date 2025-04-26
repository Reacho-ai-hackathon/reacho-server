# Storage Layer Overview

This directory contains the core storage logic for MongoDB integration using Motor (async MongoDB driver) and Pydantic models. It provides reusable utilities, models, and CRUD patterns for managing your application's data layer.

## File Structure

- **db_utils.py**: Core MongoDB utility functions and generic CRUD base class. Defines:
  - `PyObjectId`: Custom ObjectId type for Pydantic validation.
  - `MongoModel`: Base model for MongoDB documents with automatic ID handling.
  - `CRUDBase`: Generic async CRUD operations (create, get, update, delete, find) for any Pydantic model.
- **models.py**: Pydantic models representing MongoDB schemas for your domain (e.g., User, CallLog). Includes creation, update, and full document models.
- **db_example.py**: Example script demonstrating how to use the CRUD utilities and models for typical operations (create, get, update, list, find, delete users).

## Setup & Requirements

- Requires Motor (async MongoDB driver) and Pydantic.
- Expects a `db_config.py` module with `get_database`, `init_db`, and `close_mongo_connection` functions for DB connection management.

## How to Use

### 1. Define Your Models

Create Pydantic models for your MongoDB collections in `models.py`. Inherit from `MongoModel` for full documents, and use standard Pydantic models for creation/update schemas.

Example:

```python
class User(MongoModel, UserBase):
    expiry_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### 2. Create a CRUD Handler

Subclass `CRUDBase` for your model and specify the collection name:

```python
from db_utils import CRUDBase
from models import User

class UserCRUD(CRUDBase[User]):
    def __init__(self):
        super().__init__(User, "users")
```

### 3. Perform CRUD Operations

All operations are async. Example usage:

```python
user_crud = UserCRUD()

# Create a user
user = await user_crud.create(UserCreate(...))

# Get a user by ID
user = await user_crud.get(user_id)

# Update a user
updated_user = await user_crud.update(user_id, UserUpdate(...))

# Delete a user
success = await user_crud.delete(user_id)

# List users
users = await user_crud.get_multi(skip=0, limit=10)

# Find users by query
users = await user_crud.find_many({"company": "Example Corp"})
```

### 4. Example Script

See `db_example.py` for a full workflow, including DB initialization and teardown.

## Integration Points

- Import your CRUD handler and models wherever you need database access in your app.
- Use the async CRUD methods for all DB operations.
- Extend models and CRUD logic as needed for new collections or business logic.

## Notes

- All timestamps (`created_at`, `updated_at`) are handled automatically in CRUDBase.
- ObjectId fields are validated and serialized for API compatibility.
- You can add more models and CRUD handlers following the same pattern.

---

**This storage layer is designed for scalability and maintainability.**
If you add new collections or models, define them in `models.py` and create a corresponding CRUD handler using `CRUDBase`.
