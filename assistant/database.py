from typing import List, Dict, Optional
import sqlite3
from datetime import datetime
import json

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

    def save_conversation(
        self,
        conversation_id: Optional[str],
        user_email: str,
        message: str,
        response: str
    ) -> str:
        """Save a new message and response to the conversation."""
        with sqlite3.connect(self.db_path) as conn:
            if not conversation_id:
                # Create new conversation
                conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                conn.execute(
                    "INSERT INTO conversations (id, user_email) VALUES (?, ?)",
                    (conversation_id, user_email)
                )
            
            # Save user message
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, "user", message)
            )
            
            # Save assistant response
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, "assistant", response)
            )
            
            return conversation_id

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Retrieve the conversation history for a given conversation ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT role, content 
                FROM messages 
                WHERE conversation_id = ? 
                ORDER BY created_at ASC
                """,
                (conversation_id,)
            )
            
            return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()] 