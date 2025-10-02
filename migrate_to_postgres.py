#!/usr/bin/env python3
"""
Migration von SQLite zu PostgreSQL für Todo-App
"""

import os
import sqlite3
import psycopg2
from datetime import datetime

def migrate_sqlite_to_postgres():
    # SQLite Verbindung
    sqlite_conn = sqlite3.connect('instance/todos.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL Verbindung
    pg_conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        database=os.getenv('POSTGRES_DB', 'todoapp'),
        user=os.getenv('POSTGRES_USER', 'todouser'),
        password=os.getenv('POSTGRES_PASSWORD', 'your_password')
    )
    pg_cursor = pg_conn.cursor()
    
    print("🔄 Starte Migration von SQLite zu PostgreSQL...")
    
    # 1. TaskGroup Migration
    print("📁 Migriere Gruppen...")
    sqlite_cursor.execute("SELECT id, name, created_at FROM task_group")
    groups = sqlite_cursor.fetchall()
    
    for group in groups:
        pg_cursor.execute("""
            INSERT INTO task_group (id, name, created_at) 
            VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING
        """, group)
    
    # 2. Todo Migration
    print("📝 Migriere Todos...")
    sqlite_cursor.execute("""
        SELECT id, title, description, completed, priority, 
               created_at, due_date, group_id, parent_id 
        FROM todo
    """)
    todos = sqlite_cursor.fetchall()
    
    for todo in todos:
        pg_cursor.execute("""
            INSERT INTO todo (id, title, description, completed, priority, 
                            created_at, due_date, group_id, parent_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
            ON CONFLICT (id) DO NOTHING
        """, todo)
    
    # 3. Notes Migration
    print("📋 Migriere Notizen...")
    sqlite_cursor.execute("SELECT id, title, content, created_at, updated_at FROM note")
    notes = sqlite_cursor.fetchall()
    
    for note in notes:
        pg_cursor.execute("""
            INSERT INTO note (id, title, content, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """, note)
    
    # Änderungen speichern
    pg_conn.commit()
    
    # Verbindungen schließen
    sqlite_conn.close()
    pg_conn.close()
    
    print("✅ Migration erfolgreich abgeschlossen!")

if __name__ == "__main__":
    migrate_sqlite_to_postgres()
