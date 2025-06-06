import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import json

class Database:
    def __init__(self, db_path: str = "conversations.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self._conn = None
        self._init_db()

    def _get_connection(self):
        """Get database connection, creating a new one if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            # Enable foreign key constraints
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def _init_db(self):
        """Initialize database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                user_name TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                available_slots TEXT,
                booked_slot TEXT,
                booking_link TEXT,
                event_type_slug TEXT
            )
        """)
        
        # Create chat_history table with foreign key to conversations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES conversations(thread_id) ON DELETE CASCADE
            )
        """)
        
        # Create index on thread_id for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_history_thread_id 
            ON chat_history(thread_id)
        """)
        
        conn.commit()

    def save_conversation(self, conversation_data: Dict[str, Any], messages: List[Tuple[str, str]]) -> None:
        """Save conversation state to database.
        
        Args:
            conversation_data: Dict containing thread_id, user_email, user_name, last_updated
            messages: List of (role, content) tuples for chat history
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Convert available_slots and booked_slot to JSON strings if they exist
        available_slots_json = None
        if 'available_slots' in conversation_data and conversation_data['available_slots']:
            available_slots_json = json.dumps([
                {'time': slot['time'], 'iso': slot['iso']}
                for slot in conversation_data['available_slots']
            ])
        
        booked_slot_json = None
        if 'booked_slot' in conversation_data and conversation_data['booked_slot']:
            booked_slot_json = json.dumps({
                'time': conversation_data['booked_slot']['time'],
                'iso': conversation_data['booked_slot']['iso']
            })
        
        # Save conversation details
        cursor.execute("""
            INSERT OR REPLACE INTO conversations 
            (thread_id, user_email, user_name, last_updated, available_slots, booked_slot, booking_link, event_type_slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_data['thread_id'],
            conversation_data['user_email'],
            conversation_data['user_name'],
            conversation_data['last_updated'],
            available_slots_json,
            booked_slot_json,
            conversation_data.get('booking_link'),
            conversation_data.get('event_type_slug')
        ))
        
        # Delete existing chat history for this thread
        cursor.execute("DELETE FROM chat_history WHERE thread_id = ?", (conversation_data['thread_id'],))
        
        # Insert new chat history with incremental timestamps
        base_time = datetime.now()
        chat_history_values = [
            (
                conversation_data['thread_id'],
                role,
                content,
                (base_time + timedelta(milliseconds=i)).isoformat()  # Incremental timestamps
            )
            for i, (role, content) in enumerate(messages)
        ]
        cursor.executemany("""
            INSERT INTO chat_history (thread_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, chat_history_values)
        
        conn.commit()

    def get_conversation(self, thread_id: str) -> Optional[Tuple[Dict[str, Any], List[Tuple[str, str]]]]:
        """Retrieve conversation state from database.
        
        Returns:
            Tuple of (conversation_data, messages) where:
            - conversation_data is a dict with thread_id, user_email, user_name, last_updated
            - messages is a list of (role, content) tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get conversation details
        cursor.execute("""
            SELECT thread_id, user_email, user_name, last_updated, 
                   available_slots, booked_slot, booking_link, event_type_slug
            FROM conversations
            WHERE thread_id = ?
        """, (thread_id,))
        conv_row = cursor.fetchone()
        
        if not conv_row:
            return None
        
        # Get chat history
        cursor.execute("""
            SELECT role, content
            FROM chat_history
            WHERE thread_id = ?
            ORDER BY id ASC
        """, (thread_id,))
        chat_rows = cursor.fetchall()
        
        # Parse available_slots and booked_slot from JSON if they exist
        available_slots = None
        if conv_row[4]:  # available_slots column
            available_slots = json.loads(conv_row[4])
        
        booked_slot = None
        if conv_row[5]:  # booked_slot column
            booked_slot = json.loads(conv_row[5])
        
        conversation_data = {
            'thread_id': conv_row[0],
            'user_email': conv_row[1],
            'user_name': conv_row[2],
            'last_updated': conv_row[3],
            'available_slots': available_slots,
            'booked_slot': booked_slot,
            'booking_link': conv_row[6],
            'event_type_slug': conv_row[7]
        }
        
        return conversation_data, chat_rows

    def delete_conversation(self, thread_id: str) -> None:
        """Delete conversation state from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Due to ON DELETE CASCADE, this will also delete related chat history
        cursor.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
        conn.commit()

    def list_active_conversations(self, days: int = 30) -> List[Tuple[Dict[str, Any], List[Tuple[str, str]]]]:
        """List all active conversations from the last N days."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all active conversations
        cursor.execute("""
            SELECT c.thread_id, c.user_email, c.user_name, c.last_updated,
                   c.available_slots, c.booked_slot, c.booking_link, c.event_type_slug
            FROM conversations c
            WHERE c.last_updated >= ?
            ORDER BY c.last_updated DESC
        """, (cutoff_date,))
        conv_rows = cursor.fetchall()
        
        conversations = []
        for conv_row in conv_rows:
            # Get chat history for each conversation
            cursor.execute("""
                SELECT role, content
                FROM chat_history
                WHERE thread_id = ?
                ORDER BY id ASC
            """, (conv_row[0],))
            chat_rows = cursor.fetchall()
            
            # Parse available_slots and booked_slot from JSON if they exist
            available_slots = None
            if conv_row[4]:  # available_slots column
                available_slots = json.loads(conv_row[4])
            
            booked_slot = None
            if conv_row[5]:  # booked_slot column
                booked_slot = json.loads(conv_row[5])
            
            conversation_data = {
                'thread_id': conv_row[0],
                'user_email': conv_row[1],
                'user_name': conv_row[2],
                'last_updated': conv_row[3],
                'available_slots': available_slots,
                'booked_slot': booked_slot,
                'booking_link': conv_row[6],
                'event_type_slug': conv_row[7]
            }
            
            conversations.append((conversation_data, chat_rows))
        
        return conversations

    def cleanup_old_states(self, days: int = 30) -> None:
        """Clean up old conversation states."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Delete old conversations (chat history will be deleted via CASCADE)
        cursor.execute("DELETE FROM conversations WHERE last_updated < ?", (cutoff_date,))
        conn.commit()

    def __del__(self):
        """Clean up database connection."""
        if self._conn is not None:
            self._conn.close() 