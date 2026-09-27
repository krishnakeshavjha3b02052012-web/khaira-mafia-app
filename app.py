import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'khaira-mafia-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default='Member')

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_dms')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_dms')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/poker')
@login_required
def poker():
    return render_template('poker.html')

@app.route('/ludo')
@login_required
def ludo():
    return render_template('ludo.html')

@app.route('/dm')
@login_required
def dm_inbox():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('dm.html', users=users, active_recipient=None, messages=[])

@app.route('/dm/<int:user_id>', methods=['GET', 'POST'])
@login_required
def private_chat(user_id):
    recipient = User.query.get_or_404(user_id)
    users = User.query.filter(User.id != current_user.id).all()

    if request.method == 'POST':
        content = request.form.get('message')
        if content:
            dm = PrivateMessage(sender_id=current_user.id, recipient_id=recipient.id, content=content)
            db.session.add(dm)
            db.session.commit()
        return redirect(url_for('private_chat', user_id=user_id))

    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == current_user.id) & (PrivateMessage.recipient_id == recipient.id)) |
        ((PrivateMessage.sender_id == recipient.id) & (PrivateMessage.recipient_id == current_user.id))
    ).order_by(PrivateMessage.timestamp.asc()).all()

    return render_template('dm.html', users=users, active_recipient=recipient, messages=messages)

# Authentication Handlers
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))
        flash('Username already exists')
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Place this outside the if statement so Gunicorn creates database tables on Render
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
