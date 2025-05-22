from typing import List, Dict, Optional
import sqlite3
from datetime import datetime

class ChatMessage:
    def __init__(self, role: str, content: str):
        self.id = id
        self.thread_id = thread_id
        self.role = role
        self.content = content
        self.created_at = created_at


class ConversationDatabase:
    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        message: ChatMessage
    ) -> str:
        """Add a message to the conversation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, message.role, message.content)
            )
            
        return conversation_id

    def get_or_create_conversation_history(self, conversation_id: str, user_email: str) -> List[ChatMessage]:
        """Retrieve the conversation history for a given conversation ID."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if conversation exists
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            if cursor.fetchone() is None:
                # Create new conversation
                conn.execute(
                    "INSERT INTO conversations (id, user_email) VALUES (?, ?)",
                    (conversation_id, user_email)
                )
                return []
            
            cursor = conn.execute(
                """
                SELECT role, content 
                FROM messages 
                WHERE conversation_id = ? 
                ORDER BY created_at ASC
                """,
                (conversation_id,)
            )
            
            return [ChatMessage(row[0], row[1]) for row in cursor.fetchall()] 