from flask import Blueprint, jsonify, request
from sqlalchemy import text
from models import db, User

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello from Flask!")


@bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email} for u in users])


@bp.route('/db-test', methods=['GET'])
def db_test():
    """Simple endpoint to test DB connectivity and return user count."""
    try:
        # run a trivial select to verify connection
        result = None
        with db.engine.connect() as conn:
            row = conn.execute(text('SELECT 1')).fetchone()
            result = row[0] if row is not None else None

        # also give a user count
        user_count = User.query.count()
        return jsonify(status='ok', ping=result, users=user_count), 200
    except Exception as e:
        return jsonify(status='error', error=str(e)), 500


@bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user. Expects JSON: {username, email, password}"""
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password:
        return jsonify(message='username, email and password are required'), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify(message='user with that username or email already exists'), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(message='user created', id=user.id), 201


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify(message='username and password are required'), 400

    user = User.query.filter((User.username == username) | (User.email == username)).first()
    if not user or not user.check_password(password):
        return jsonify(message='invalid credentials'), 401

    return jsonify(message='ok', id=user.id, username=user.username), 200
