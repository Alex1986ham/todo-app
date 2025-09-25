from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import case
import argparse

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SECRET_KEY'] = 'dein-geheimer-schluessel'
db = SQLAlchemy(app)

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
    group_id = db.Column(db.Integer, db.ForeignKey('task_group.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('todo.id'), nullable=True)
    sub_todos = db.relationship('Todo', backref=db.backref('parent', remote_side=[id]), 
                              cascade='all, delete-orphan')

    @property
    def is_sub_todo(self):
        return self.parent_id is not None

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    groups = TaskGroup.query.all()
    selected_group_id = request.args.get('group_id', type=int)
    selected_group = None
    todos_by_group = {}
    
    # Wenn keine Gruppe ausgewählt ist, nehmen wir die erste
    if not selected_group_id and groups:
        selected_group_id = groups[0].id
    
    if selected_group_id:
        selected_group = TaskGroup.query.get_or_404(selected_group_id)
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
                         groups=groups, 
                         selected_group=selected_group,
                         todos_by_group=todos_by_group)

@app.route('/group/new', methods=['GET', 'POST'])
def new_group():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            group = TaskGroup(name=name)
            db.session.add(group)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('group_form.html')

@app.route('/group/<int:id>/edit', methods=['GET', 'POST'])
def edit_group(id):
    group = TaskGroup.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            group.name = name
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('group_form.html', group=group)

@app.route('/group/<int:id>/delete')
def delete_group(id):
    group = TaskGroup.query.get_or_404(id)
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/todo/new', methods=['GET', 'POST'])
def new_todo():
    groups = TaskGroup.query.all()
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
        
        if title and group_id:
            # Haupttodo erstellen
            todo = Todo(
                title=title,
                description=description,
                group_id=group_id,
                priority=priority,
                parent_id=parent_id
            )
            db.session.add(todo)
            db.session.flush()  # Um die ID des Haupttodos zu erhalten
            
            # Sub-Todos hinzufügen
            if not parent_id:  # Nur für Haupttodos
                sub_todo_titles = request.form.getlist('sub_todo_title[]')
                sub_todo_descriptions = request.form.getlist('sub_todo_description[]')
                
                for title, description in zip(sub_todo_titles, sub_todo_descriptions):
                    if title.strip():  # Nur Sub-Todos mit Titel hinzufügen
                        sub_todo = Todo(
                            title=title,
                            description=description,
                            group_id=group_id,
                            parent_id=todo.id,
                            priority=priority
                        )
                        db.session.add(sub_todo)
            
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('todo_form.html', groups=groups, selected_group_id=group_id, parent_todo=parent_todo)

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
            
            # Bestehende Sub-Todos löschen
            Todo.query.filter_by(parent_id=todo.id).delete()
            
            # Neue Sub-Todos hinzufügen
            sub_todo_titles = request.form.getlist('sub_todo_title[]')
            sub_todo_descriptions = request.form.getlist('sub_todo_description[]')
            
            for title, description in zip(sub_todo_titles, sub_todo_descriptions):
                if title.strip():  # Nur Sub-Todos mit Titel hinzufügen
                    sub_todo = Todo(
                        title=title,
                        description=description,
                        group_id=todo.group_id,
                        parent_id=todo.id,
                        priority=todo.priority
                    )
                    db.session.add(sub_todo)
            
            db.session.commit()
            return redirect(url_for('index'))
            
    return render_template('todo_form.html', todo=todo, groups=groups)

@app.route('/todo/<int:id>/toggle')
def toggle_todo(id):
    todo = Todo.query.get_or_404(id)
    todo.completed = not todo.completed
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/todo/<int:id>/delete')
def delete_todo(id):
    todo = Todo.query.get_or_404(id)
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for('index'))

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