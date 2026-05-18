"""
File: database_tool.py
Author: Christopher John Macabenta Medina
Email: [Your Email]
Course: COMPE 475 – Microprocessors
Institution: San Diego State University
Module: 11 – System Prompts (Section 3)
Version: 1.0
License: Educational Use

Description:
    Custom LangGraph tool providing SQLite CRUD operations for 
    persistent file storage in the Korra AI agent.
    Demonstrates fundamental data manipulation patterns:
        • Create: Save new files to the database
        • Read/List: Retrieve file contents or list all files
        • Update: Modify existing files
        • Delete: Remove files from storage
"""

# ============================================================
# IMPORTS
# ============================================================

import os
import sqlite3
from datetime import datetime
from langchain_core.tools import tool

# ============================================================
# CONFIGURATION CONSTANTS
# ============================================================

import os

# Create a dedicated data directory for the Docker volume
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

# Save the database inside the mapped volume
DB_NAME = os.path.join(DATA_DIR, "korra_storage.db")

# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Creates the files table if it does not already exist."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@tool
def manage_files(operation: str, filename: str = None, content: str = None) -> str:
    """
    Manages a SQLite database for file storage.
    
    Args:
        operation: The CRUD action ('create', 'read', 'update', 'delete', 'list').
        filename: The name of the file to manage.
        content: The text content (required for 'create' and 'update').
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if operation == "create":
            cursor.execute(
                "INSERT INTO files (filename, content) VALUES (?, ?)", 
                (filename, content)
            )
            conn.commit()
            return f"[SUCCESS] Saved file: {filename}"

        elif operation == "read":
            cursor.execute("SELECT content FROM files WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            return row["content"] if row else f"[ERROR] File '{filename}' not found."

        elif operation == "update":
            cursor.execute(
                "UPDATE files SET content = ?, updated_at = ? WHERE filename = ?",
                (content, datetime.now(), filename)
            )
            if cursor.rowcount == 0:
                return f"[ERROR] File '{filename}' not found for update."
            conn.commit()
            return f"[SUCCESS] Updated file: {filename}"

        elif operation == "delete":
            cursor.execute("DELETE FROM files WHERE filename = ?", (filename,))
            if cursor.rowcount == 0:
                return f"[ERROR] File '{filename}' not found."
            conn.commit()
            return f"[SUCCESS] Deleted file: {filename}"

        elif operation == "list":
            cursor.execute("SELECT filename FROM files")
            files = [row["filename"] for row in cursor.fetchall()]
            return f"Stored files: {', '.join(files)}" if files else "Database is empty."

        else:
            return f"[ERROR] Unsupported operation '{operation}'."

    except sqlite3.IntegrityError:
        return f"[ERROR] File '{filename}' already exists. Use 'update' instead."
    except Exception as e:
        return f"[DATABASE ERROR] {str(e)}"
    finally:
        conn.close()