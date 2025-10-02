from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import case
import argparse
import os
from authlib.integrations.flask_client import OAuth
import requests
from dotenv import load_dotenv

# Environment-Variablen laden
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///todos.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dein-geheimer-schluessel')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Google OAuth Konfiguration
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

db = SQLAlchemy(app)

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

class TaskGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    picture = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Beziehungen zu anderen Modellen
    groups = db.relationship('TaskGroup', backref='user', lazy=True, cascade='all, delete-orphan')
    notes = db.relationship('Note', backref='user', lazy=True, cascade='all, delete-orphan')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Neue Notiz')
    content = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# Hilfsfunktionen für Authentifizierung
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user' in session:
        user_id = session['user']['id']
        user_email = session['user']['email']
        user = User.query.get(user_id)
        if user:
            print(f"👤 Current User: {user.email} (ID: {user.id}) - Session: {user_email}")
        return user
    return None

# Authentication Routes
@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if user_info:
        print(f"🔍 OAuth Callback - User Info: {user_info['email']} (ID: {user_info['sub']})")
        
        # User in Datenbank suchen oder erstellen
        user = User.query.filter_by(google_id=user_info['sub']).first()
        
        if not user:
            print(f"✅ Neuen User erstellen: {user_info['email']}")
            # Neuen User erstellen
            user = User(
                google_id=user_info['sub'],
                email=user_info['email'],
                name=user_info['name'],
                picture=user_info.get('picture', '')
            )
            db.session.add(user)
            db.session.commit()
            
            # Standard-Gruppen für neuen User erstellen
            default_groups = ['Arbeit', 'Privat', 'Einkaufen']
            for group_name in default_groups:
                group = TaskGroup(name=group_name, user_id=user.id)
                db.session.add(group)
            db.session.commit()
        else:
            print(f"🔄 Bestehenden User aktualisieren: {user_info['email']} (DB ID: {user.id})")
            # Letzten Login aktualisieren
            user.last_login = datetime.utcnow()
            user.name = user_info['name']  # Name aktualisieren falls geändert
            user.picture = user_info.get('picture', '')
            db.session.commit()
        
        # Session komplett leeren und neu setzen
        session.clear()
        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture or ''
        }
        
        print(f"💾 Session gesetzt für User ID: {user.id} ({user.email})")
        
        return redirect(url_for('index'))
    
    print("❌ Kein user_info erhalten")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    if 'user' in session:
        print(f"🚪 User logout: {session['user']['email']}")
    session.clear()  # Komplette Session leeren
    return redirect(url_for('login'))

# Template-Funktion für globale Gruppen (nur für eingeloggte User)
@app.context_processor
def inject_groups():
    user = get_current_user()
    if user:
        groups = TaskGroup.query.filter_by(user_id=user.id).all()
        return dict(groups=groups, current_user=user)
    return dict(groups=[], current_user=None)

@app.route('/')
@login_required
def index():
    user = get_current_user()
    groups = TaskGroup.query.filter_by(user_id=user.id).all()
    selected_group_id = request.args.get('group_id', type=int)
    selected_group = None
    todos_by_group = {}
    
    # Wenn keine Gruppe ausgewählt ist, nehmen wir die erste
    if not selected_group_id and groups:
        selected_group_id = groups[0].id
    
    if selected_group_id:
        selected_group = TaskGroup.query.filter_by(id=selected_group_id, user_id=user.id).first_or_404()
        todos = Todo.query.filter_by(group_id=selected_group_id, parent_id=None).order_by(
            Todo.completed,
            case(
                (Todo.priority == 'urgent', 1),
                (Todo.priority == 'high', 2),
                (Todo.priority == 'medium', 3),
                (Todo.priority == 'low', 4)
            ),
            Todo.created_at.desc()
        ).all()
        todos_by_group[selected_group_id] = todos
    
    return render_template('index.html', 
                         selected_group=selected_group,
                         todos_by_group=todos_by_group)

@app.route('/group/new', methods=['GET', 'POST'])
@login_required
def new_group():
    user = get_current_user()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            group = TaskGroup(name=name, user_id=user.id)
            db.session.add(group)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('group_form.html')

@app.route('/group/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    user = get_current_user()
    group = TaskGroup.query.filter_by(id=id, user_id=user.id).first_or_404()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            group.name = name
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('group_form.html', group=group)

@app.route('/group/<int:id>/delete')
@login_required
def delete_group(id):
    user = get_current_user()
    group = TaskGroup.query.filter_by(id=id, user_id=user.id).first_or_404()
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/todo/new', methods=['GET', 'POST'])
@login_required
def new_todo():
    user = get_current_user()
    parent_id = request.args.get('parent_id')
    group_id = request.args.get('group_id')
    parent_todo = None
    if parent_id:
        parent_todo = Todo.query.get_or_404(parent_id)
        group_id = parent_todo.group_id

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        group_id = request.form.get('group_id')
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date')
        
        # Deadline parsen
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        if title and group_id:
            # Haupttodo erstellen
            todo = Todo(
                title=title,
                description=description,
                group_id=group_id,
                priority=priority,
                parent_id=parent_id,
                due_date=due_date
            )
            db.session.add(todo)
            db.session.flush()  # Um die ID des Haupttodos zu erhalten
            
            # Sub-Todos hinzufügen
            if not parent_id:  # Nur für Haupttodos
                sub_todo_titles = request.form.getlist('sub_todo_title[]')
                
                for title in sub_todo_titles:
                    if title.strip():  # Nur Sub-Todos mit Titel hinzufügen
                        sub_todo = Todo(
                            title=title,
                            description=None,  # Keine Beschreibung für Sub-Todos
                            group_id=group_id,
                            parent_id=todo.id,
                            priority=priority
                        )
                        db.session.add(sub_todo)
            
            db.session.commit()
            return redirect(url_for('index', group_id=group_id))
    return render_template('todo_form.html', 
                         selected_group_id=group_id, parent_todo=parent_todo)

@app.route('/todo/<int:id>/edit', methods=['GET', 'POST'])
def edit_todo(id):
    todo = Todo.query.get_or_404(id)
    groups = TaskGroup.query.all()
    
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            todo.title = request.form.get('title')
            todo.description = request.form.get('description')
            db.session.commit()
            return jsonify({'success': True})
        else:
            # Haupttodo aktualisieren
            todo.title = request.form.get('title')
            todo.description = request.form.get('description')
            todo.group_id = request.form.get('group_id')
            todo.priority = request.form.get('priority', 'medium')
            todo.completed = 'completed' in request.form
            
            # Deadline aktualisieren
            due_date_str = request.form.get('due_date')
            if due_date_str:
                try:
                    todo.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            else:
                todo.due_date = None
            
            # Bestehende Sub-Todos löschen
            Todo.query.filter_by(parent_id=todo.id).delete()
            
            # Neue Sub-Todos hinzufügen
            sub_todo_titles = request.form.getlist('sub_todo_title[]')
            
            for title in sub_todo_titles:
                if title.strip():  # Nur Sub-Todos mit Titel hinzufügen
                    sub_todo = Todo(
                        title=title,
                        description=None,  # Keine Beschreibung für Sub-Todos
                        group_id=todo.group_id,
                        parent_id=todo.id,
                        priority=todo.priority
                    )
                    db.session.add(sub_todo)
            
            db.session.commit()
            return redirect(url_for('index', group_id=todo.group_id))
            
    return render_template('todo_form.html', todo=todo, groups=groups)

@app.route('/todo/<int:id>/toggle')
def toggle_todo(id):
    todo = Todo.query.get_or_404(id)
    todo.completed = not todo.completed
    db.session.commit()
    return redirect(url_for('index', group_id=todo.group_id))

@app.route('/todo/<int:id>/delete')
def delete_todo(id):
    todo = Todo.query.get_or_404(id)
    group_id = todo.group_id  # Gruppe vor dem Löschen speichern
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for('index', group_id=group_id))

@app.route('/deadlines')
def deadlines():
    # Alle nicht erledigten Haupttodos nach Deadline kategorisieren
    todos = Todo.query.filter_by(completed=False, parent_id=None).all()
    
    categories = {
        'today': [],
        'upcoming': [],
        'someday': []
    }
    
    for todo in todos:
        category = todo.deadline_category
        categories[category].append(todo)
    
    # Sortiere innerhalb jeder Kategorie nach Priorität
    for category in categories:
        categories[category].sort(key=lambda x: (
            x.priority == 'urgent',
            x.priority == 'high',
            x.priority == 'medium',
            x.priority == 'low'
        ), reverse=True)
    
    return render_template('deadlines.html', categories=categories)

@app.route('/notes')
def notes():
    return render_template('notes.html')

@app.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    if request.method == 'GET':
        # Notizen aus der Datenbank laden
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        return jsonify([{
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat()
        } for note in notes])
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if 'id' in data and data['id']:
            # Bestehende Notiz aktualisieren
            note = Note.query.get_or_404(data['id'])
            note.title = data.get('title', '')
            note.content = data.get('content', '')
            note.updated_at = datetime.utcnow()
        else:
            # Neue Notiz erstellen
            note = Note(
                title=data.get('title', ''),
                content=data.get('content', '')
            )
            db.session.add(note)
        
        db.session.commit()
        
        return jsonify({
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat()
        })

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def api_delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/matrix')
def priority_matrix():
    # Alle nicht erledigten Haupttodos (keine Sub-Todos) nach Priorität gruppieren
    todos = Todo.query.filter_by(completed=False, parent_id=None).all()
    
    matrix = {
        'urgent_important': [],    # Dringend & Wichtig (urgent)
        'important': [],           # Wichtig (high)
        'urgent': [],              # Dringend (medium)
        'neither': []              # Weder noch (low)
    }
    
    for todo in todos:
        if todo.priority == 'urgent':
            matrix['urgent_important'].append(todo)
        elif todo.priority == 'high':
            matrix['important'].append(todo)
        elif todo.priority == 'medium':
            matrix['urgent'].append(todo)
        else:  # low
            matrix['neither'].append(todo)
            
    return render_template('priority_matrix.html', matrix=matrix)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    
    app.run(debug=True, port=args.port)