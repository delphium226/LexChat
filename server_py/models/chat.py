from datetime import datetime
from typing import Optional, List, Union
from .auth import CamelModel

class Chat(CamelModel):
    id: int
    user_id: int
    title: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime

class CreateChatRequest(CamelModel):
    title: Optional[str] = None
    model: str

class UpdateChatRequest(CamelModel):
    title: str

class Message(CamelModel):
    id: int
    chat_id: int
    role: str
    content: str
    rating: Optional[int] = None
    feedback_comment: Optional[str] = None
    created_at: datetime

class CreateMessageRequest(CamelModel):
    role: str
    content: str
    num_ctx: Optional[int] = None # Added for chat params
    deep_research: Optional[bool] = False

class ToolStatus(CamelModel):
    type: str # 'token', 'tool_start', 'tool_end', 'result', 'error'
    content: Optional[str] = None
    message: Optional[str] = None
    tool: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
