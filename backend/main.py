# main.py
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator, EmailStr
from fastapi.responses import JSONResponse
import secrets
import hashlib
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="TODO API with Auth", version="1.0.0")
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Ye frontend ko allow karega
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "healthy"}
    
# In-memory storage
user_todos: Dict[int, Dict] = {}  # {user_id: {todo_id: todo_data}}
users_db: Dict[str, Dict] = {}    # {username: user_data}
sessions: Dict[str, int] = {}     # {token: user_id}

current_user_id = 1
current_todo_id: Dict[int, int] = {}  # {user_id: next_todo_id}

# Password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Authentication models
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# TODO models
class TodoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    due_date: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    completed: bool = Field(default=False)
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError('Title cannot be empty or just whitespace')
        return trimmed

class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    due_date: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    completed: Optional[bool] = None

class TodoResponse(TodoBase):
    id: int
    user_id: int
    created_at: str

# Authentication dependency
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    if token.credentials not in sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = sessions[token.credentials]
    if user_id not in [user['id'] for user in users_db.values()]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return {"id": user_id, "username": next((u['username'] for u in users_db.values() if u['id'] == user_id), None)}

# Get user-specific todos
def get_user_todos(user_id: int):
    if user_id not in user_todos:
        user_todos[user_id] = {}
    if user_id not in current_todo_id:
        current_todo_id[user_id] = 1
    return user_todos[user_id], current_todo_id[user_id]

# ========== AUTHENTICATION ENDPOINTS ==========
@app.post("/register", response_model=Token)
async def register(user: UserRegister):
    """Register a new user"""
    global current_user_id
    
    if user.username in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create user
    user_data = {
        "id": current_user_id,
        "username": user.username,
        "email": user.email,
        "password": hash_password(user.password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    users_db[user.username] = user_data
    
    # Generate token
    token = secrets.token_hex(32)
    sessions[token] = current_user_id
    
    # Initialize user's todos
    user_todos[current_user_id] = {}
    current_todo_id[current_user_id] = 1
    
    current_user_id += 1
    
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
async def login(user: UserLogin):
    """Login user"""
    if user.username not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    stored_user = users_db[user.username]
    
    # Verify password
    if stored_user["password"] != hash_password(user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Generate new token
    token = secrets.token_hex(32)
    sessions[token] = stored_user["id"]
    
    return {"access_token": token, "token_type": "bearer"}

@app.post("/logout")
async def logout(token: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user"""
    if token.credentials in sessions:
        del sessions[token.credentials]
    
    return {"message": "Logged out successfully"}

@app.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    username = current_user["username"]
    user_data = users_db[username]
    return {
        "id": user_data["id"],
        "username": user_data["username"],
        "email": user_data["email"],
        "created_at": user_data["created_at"]
    }

# ========== TODO ENDPOINTS (PROTECTED) ==========
@app.get("/")
async def root():
    return {"message": "TODO API with Authentication", "status": "healthy"}

@app.post("/todos", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(
    todo: TodoCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new TODO item"""
    user_id = current_user["id"]
    todos, next_id = get_user_todos(user_id)
    
    new_todo = {
        "id": next_id,
        "user_id": user_id,
        "title": todo.title,
        "description": todo.description,
        "due_date": todo.due_date,
        "priority": todo.priority,
        "completed": todo.completed,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    todos[next_id] = new_todo
    current_todo_id[user_id] = next_id + 1
    
    return new_todo

@app.get("/todos", response_model=List[TodoResponse])
async def list_todos(current_user: dict = Depends(get_current_user)):
    """List all TODO items for current user"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    return list(todos.values())

@app.get("/todos/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific TODO item"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    
    if todo_id not in todos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TODO with id {todo_id} not found"
        )
    
    return todos[todo_id]

@app.put("/todos/{todo_id}", response_model=TodoResponse)
async def replace_todo(
    todo_id: int,
    todo: TodoCreate,
    current_user: dict = Depends(get_current_user)
):
    """Replace an entire TODO item"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    
    if todo_id not in todos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TODO with id {todo_id} not found"
        )
    
    updated_todo = {
        "id": todo_id,
        "user_id": user_id,
        "title": todo.title,
        "description": todo.description,
        "due_date": todo.due_date,
        "priority": todo.priority,
        "completed": todo.completed,
        "created_at": todos[todo_id]["created_at"]
    }
    
    todos[todo_id] = updated_todo
    return updated_todo

@app.patch("/todos/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    todo_update: TodoUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Partially update a TODO item"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    
    if todo_id not in todos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TODO with id {todo_id} not found"
        )
    
    current_todo = todos[todo_id].copy()
    
    update_data = todo_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            current_todo[field] = value
    
    todos[todo_id] = current_todo
    return current_todo

@app.patch("/todos/{todo_id}/toggle", response_model=TodoResponse)
async def toggle_todo_status(
    todo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Toggle the completed status"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    
    if todo_id not in todos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TODO with id {todo_id} not found"
        )
    
    todos[todo_id]["completed"] = not todos[todo_id]["completed"]
    return todos[todo_id]

@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a TODO item"""
    user_id = current_user["id"]
    todos, _ = get_user_todos(user_id)
    
    if todo_id not in todos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TODO with id {todo_id} not found"
        )
    
    del todos[todo_id]
    return None
