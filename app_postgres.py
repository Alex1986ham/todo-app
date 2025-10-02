from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import case
import argparse
import os

app = Flask(__name__)

# PostgreSQL Konfiguration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 
    'postgresql://todouser:your_password@localhost:5432/todoapp'
)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dein-geheimer-schluessel')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models bleiben gleich - nur die Datenbank-Engine ändert sich
class TaskGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    todos = db.relationship('Todo', backref='group', lazy=True, cascade='all, delete-orphan')

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default='medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('task_group.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('todo.id'), nullable=True)
    sub_todos = db.relationship('Todo', backref=db.backref('parent', remote_side=[id]), 
                              cascade='all, delete-orphan')

    @property
    def is_sub_todo(self):
        return self.parent_id is not None
    
    @property
    def deadline_category(self):
        if not self.due_date:
            return 'someday'
        
        now = datetime.utcnow()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        
        due_date = self.due_date.date()
        
        if due_date == today:
            return 'today'
        elif due_date < next_week:
            return 'upcoming'
        else:
            return 'someday'

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Neue Notiz')
    content = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Rest der App bleibt identisch...
# (Alle Routes und Funktionen bleiben gleich)
