import datetime
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'khaira-mafia-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    user = db.relationship('User', backref='group_messages')

class Command(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issued_by = db.Column(db.String(80), nullable=False)
    assigned_to = db.Column(db.String(80), nullable=False)
    command_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.String(50), nullable=False)
    created_by = db.Column(db.String(80), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- AUTH & DASHBOARD ROUTES ---

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please pick another one or log in.')
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        # Support both hashed passwords and legacy unhashed plain passwords (for existing entries)
        if user and (check_password_hash(user.password, password) or user.password == password):
            login_user(user)
            return redirect(url_for('index'))

        flash('Invalid username or password. Please try again.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/poker')
@login_required
def poker():
    return render_template('poker.html')

@app.route('/ludo')
@login_required
def ludo():
    return render_template('ludo.html')

# --- DIRECT MESSAGING ---

@app.route('/dm')
@login_required
def dm_inbox():
    users = User.query.filter(User.id != current_user.id).all()
    if users:
        return redirect(url_for('private_chat', user_id=users[0].id))
    return render_template('dm.html', users=[], active_recipient=None, messages=[])

@app.route('/dm/<int:user_id>', methods=['GET', 'POST'])
@login_required
def private_chat(user_id):
    recipient = User.query.get_or_404(user_id)
    users = User.query.filter(User.id != current_user.id).all()

    if request.method == 'POST':
        content = request.form.get('message')
        if content and content.strip():
            dm = PrivateMessage(
                sender_id=current_user.id, 
                recipient_id=recipient.id, 
                content=content.strip()
            )
            db.session.add(dm)
            db.session.commit()
        return redirect(url_for('private_chat', user_id=user_id))

    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == current_user.id) & (PrivateMessage.recipient_id == recipient.id)) |
        ((PrivateMessage.sender_id == recipient.id) & (PrivateMessage.recipient_id == current_user.id))
    ).order_by(PrivateMessage.timestamp.asc()).all()

    return render_template('dm.html', users=users, active_recipient=recipient, messages=messages)

# --- GROUP CHAT ---

@app.route('/group-chat', methods=['GET', 'POST'])
@login_required
def group_chat():
    if request.method == 'POST':
        content = request.form.get('content')
        if content and content.strip():
            msg = GroupMessage(user_id=current_user.id, content=content.strip())
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('group_chat'))
    messages = GroupMessage.query.order_by(GroupMessage.timestamp.asc()).all()
    return render_template('group_chat.html', messages=messages)

# --- COMMAND CENTER ---

@app.route('/commands', methods=['GET', 'POST'])
@login_required
def commands():
    if request.method == 'POST':
        assigned_to = request.form.get('assigned_to')
        command_text = request.form.get('command_text')
        if assigned_to and command_text:
            cmd = Command(issued_by=current_user.username, assigned_to=assigned_to, command_text=command_text)
            db.session.add(cmd)
            db.session.commit()
            return redirect(url_for('commands'))
    users = User.query.filter(User.id != current_user.id).all()
    all_commands = Command.query.order_by(Command.timestamp.desc()).all()
    return render_template('commands.html', users=users, commands=all_commands)

@app.route('/commands/complete/<int:command_id>', methods=['POST'])
@login_required
def complete_command(command_id):
    cmd = Command.query.get_or_404(command_id)
    if cmd.assigned_to == current_user.username:
        cmd.status = 'Completed'
        db.session.commit()
    return redirect(url_for('commands'))

# --- CALENDAR & CALL ROOM ---

@app.route('/calendar', methods=['GET', 'POST'])
@login_required
def calendar():
    if request.method == 'POST':
        title = request.form.get('title')
        event_date = request.form.get('event_date')
        if title and event_date:
            event = CalendarEvent(title=title, event_date=event_date, created_by=current_user.username)
            db.session.add(event)
            db.session.commit()
            return redirect(url_for('calendar'))
    events = CalendarEvent.query.order_by(CalendarEvent.event_date.asc()).all()
    return render_template('calendar.html', events=events)

@app.route('/call')
@login_required
def group_call():
    return render_template('call.html', room_name="KhairaMafiaHQ")

# --- INITIALIZATION ---

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
