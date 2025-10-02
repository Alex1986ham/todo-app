#!/usr/bin/env python3
"""
Datenbank-Migration für User-Support
Fügt user_id Spalten zu bestehenden Tabellen hinzu
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    db_path = 'instance/todos.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Datenbank {db_path} nicht gefunden!")
        return False
    
    print(f"🔄 Starte Migration von {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Prüfen ob user Tabelle existiert
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            print("📝 Erstelle user Tabelle...")
            cursor.execute('''
                CREATE TABLE user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_id VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    picture VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Prüfen ob task_group bereits user_id hat
        cursor.execute("PRAGMA table_info(task_group)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_id' not in columns:
            print("📝 Füge user_id zu task_group hinzu...")
            cursor.execute('ALTER TABLE task_group ADD COLUMN user_id INTEGER')
            
            # Standard-User erstellen (für bestehende Daten)
            cursor.execute('''
                INSERT INTO user (google_id, email, name, picture, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('temp_user_1', 'temp@example.com', 'Bestehender User', '', 
                  datetime.utcnow(), datetime.utcnow()))
            
            user_id = cursor.lastrowid
            
            # Alle bestehenden Gruppen diesem User zuweisen
            cursor.execute('UPDATE task_group SET user_id = ? WHERE user_id IS NULL', (user_id,))
            print(f"✅ {cursor.rowcount} Gruppen dem Standard-User zugewiesen")
        
        # Prüfen ob note Tabelle existiert und user_id hinzufügen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='note'")
        if not cursor.fetchone():
            print("📝 Erstelle note Tabelle...")
            cursor.execute('''
                CREATE TABLE note (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) DEFAULT 'Neue Notiz',
                    content TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            ''')
        else:
            # Prüfen ob note bereits user_id hat
            cursor.execute("PRAGMA table_info(note)")
            note_columns = [column[1] for column in cursor.fetchall()]
            
            if 'user_id' not in note_columns:
                print("📝 Füge user_id zu note hinzu...")
                cursor.execute('ALTER TABLE note ADD COLUMN user_id INTEGER')
                # Alle bestehenden Notizen dem ersten User zuweisen
                cursor.execute('UPDATE note SET user_id = 1 WHERE user_id IS NULL')
        
        conn.commit()
        conn.close()
        
        print("✅ Migration erfolgreich abgeschlossen!")
        return True
        
    except Exception as e:
        print(f"❌ Fehler bei Migration: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    migrate_database()
