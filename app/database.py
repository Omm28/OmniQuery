import sqlite3

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "omniquery.db")

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def create_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        query TEXT NOT NULL,
        answer TEXT NOT NULL,
        source TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

def save_conversation(conversation_id, query, answer, source):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO conversations (conversation_id, query, answer, source)
    VALUES (?, ?, ?, ?)
    """, (conversation_id, query, answer, source))

    conn.commit()
    conn.close()

def get_conversations(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.conversation_id,
           MIN(c.timestamp) as first_time,
           (SELECT query FROM conversations 
            WHERE conversation_id = c.conversation_id 
            ORDER BY timestamp ASC LIMIT 1) as first_query,
           MAX(c.timestamp) as last_updated
    FROM conversations c
    GROUP BY c.conversation_id
    ORDER BY last_updated DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "conversation_id": row[0],
            "first_query": row[2],
            "last_updated": row[3]
        }
        for row in rows
    ]

def get_messages_by_conversation(conversation_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT query, answer, source, timestamp
    FROM conversations
    WHERE conversation_id = ?
    ORDER BY timestamp ASC
    """, (conversation_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "query": row[0],
            "answer": row[1],
            "source": row[2],
            "timestamp": row[3]
        }
        for row in rows
    ]