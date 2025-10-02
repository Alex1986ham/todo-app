from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import case
import argparse
import os
from dotenv import load_dotenv

# Environment-Variablen laden
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///todos.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dein-geheimer-schluessel')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    picture = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
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
        return User.query.get(session['user']['id'])
    return None

# Einfacher Login ohne OAuth
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', 'test@example.com')
        name = request.form.get('name', 'Test User')
        
        # User suchen oder erstellen
        user = User.query.filter_by(email=email).first()
        
        if not user:
            user = User(
                email=email,
                name=name,
                google_id=None
            )
            db.session.add(user)
            db.session.commit()
            
            # Standard-Gruppen erstellen
            default_groups = ['Arbeit', 'Privat', 'Einkaufen']
            for group_name in default_groups:
                group = TaskGroup(name=group_name, user_id=user.id)
                db.session.add(group)
            db.session.commit()
        
        # User in Session speichern
        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture or ''
        }
        
        return redirect(url_for('index'))
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Todo App - Login</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h3>Todo App - Anmelden</h3>
                        </div>
                        <div class="card-body">
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="email" class="form-label">E-Mail</label>
                                    <input type="email" class="form-control" id="email" name="email" value="test@example.com" required>
                                </div>
                                <div class="mb-3">
                                    <label for="name" class="form-label">Name</label>
                                    <input type="text" class="form-control" id="name" name="name" value="Test User" required>
                                </div>
                                <button type="submit" class="btn btn-primary">Anmelden</button>
                            </form>
                            <hr>
                            <p class="text-muted small">Temporärer Login ohne Google OAuth</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Template-Funktion für globale Gruppen
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

# Alle anderen Routen hier einfügen (new_group, edit_group, etc.)
# ... (Rest der Routen wie in der originalen app.py)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    
    app.run(debug=True, port=args.port)
