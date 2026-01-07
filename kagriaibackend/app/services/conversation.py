from typing import Dict, List, Any
from dataclasses import dataclass, field
from app.core.config import settings

@dataclass
class Turn:
    user: str
    ai: str

@dataclass
class Conversation:
    session_id: str
    turns: List[Turn] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=lambda: {"last_product_code": None})

class ConversationManager:
    def __init__(self, max_turns: int = 5):
        self.conversations: Dict[str, Conversation] = {}
        self.max_turns = max_turns

    def get_conversation(self, session_id: str) -> Conversation:
        if session_id not in self.conversations:
            self.conversations[session_id] = Conversation(session_id=session_id)
        return self.conversations[session_id]

    def add_turn(self, session_id: str, user_msg: str, ai_msg: str):
        conv = self.get_conversation(session_id)
        conv.turns.append(Turn(user=user_msg, ai=ai_msg))
        # Enforce max turns limit
        if len(conv.turns) > self.max_turns:
            conv.turns.pop(0)

    def get_history(self, session_id: str) -> List[dict]:
        conv = self.get_conversation(session_id)
        return [{"user": t.user, "ai": t.ai} for t in conv.turns]
    
    def update_meta(self, session_id: str, key: str, value: Any):
        conv = self.get_conversation(session_id)
        conv.meta[key] = value

    def get_meta(self, session_id: str, key: str) -> Any:
        conv = self.get_conversation(session_id)
        return conv.meta.get(key)
    
    def clear_session(self, session_id: str):
        if session_id in self.conversations:
            del self.conversations[session_id]

# Singleton instance with default setting
conversation_manager = ConversationManager(max_turns=settings.MAX_TURNS)
