# Storage Layer Overview

This directory contains the core storage logic for MongoDB integration using Motor (async MongoDB driver) and Pydantic models. It provides reusable utilities, models, and CRUD patterns for managing your application's data layer.

## File Structure

- **db_utils.py**: Core MongoDB utility functions and generic CRUD base class. Defines:
  - `PyObjectId`: Custom ObjectId type for Pydantic validation.
  - `MongoModel`: Base model for MongoDB documents with automatic ID handling.
  - `CRUDBase`: Generic async CRUD operations (create, get, update, delete, find) for any Pydantic model.
- **models.py**: Pydantic models representing MongoDB schemas for your domain (e.g., User, CallLog, Campaign, Call, CallMetadata). Includes creation, update, and full document models. All models are now organized in the `models/` package and imported in `models.py` for backward compatibility.
- **db_example.py**: Example script demonstrating how to use the CRUD utilities and models for typical operations (create, get, update, list, find, delete users).

## Setup & Requirements

- Requires Motor (async MongoDB driver) and Pydantic.
- Expects a `db_config.py` module with `get_database`, `init_db`, and `close_mongo_connection` functions for DB connection management.

## How to Use

### 1. Define Your Models

Create Pydantic models for your MongoDB collections in the `models/` directory. Inherit from `MongoModel` for full documents, and use standard Pydantic models for creation/update schemas. All models are exported via `models/__init__.py` and re-exported in `models.py` for easy import.

Example:

```python
from storage.models import User

user = User(
    name="John Doe",
    age=30,
    gender="male",
    phno="9381273567",
    email="john@example.com",
    organisation="Example Corp",
    designation="Engineer"
)
```

### 2. Create a CRUD Handler

Subclass `CRUDBase` for your model and specify the collection name:

```python
from storage.db_utils import CRUDBase
from storage.models import User

class UserCRUD(CRUDBase[User]):
    def __init__(self):
        super().__init__(User, "users")

user_crud = UserCRUD()
```

### 3. Perform CRUD Operations

Use the CRUD handler to perform async operations:

```python
# Create a user
user_data = UserCreate(name="Jane", ...)
user = await user_crud.create(user_data)

# Get a user
user = await user_crud.get(user_id)

# Update a user
update_data = UserUpdate(email="new@example.com")
updated_user = await user_crud.update(user_id, update_data)

# List users
users = await user_crud.get_multi(skip=0, limit=10)

# Delete a user
await user_crud.delete(user_id)
```

### 4. Example Integration

See `db_example.py` for a complete, runnable example covering all CRUD operations and integration patterns. You can adapt these patterns in your main application files (e.g., `main.py`, `call_orchestrator.py`).

---

For more details, refer to the docstrings in each model and utility file. All models are validated using Pydantic and support MongoDB's ObjectId via the custom `PyObjectId` type.
