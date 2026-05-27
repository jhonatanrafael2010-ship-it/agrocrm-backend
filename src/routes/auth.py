# src/routes/auth.py
# Rotas de autenticação (login, logout, me) e admin de usuários

from flask import Blueprint, request, jsonify, g
from functools import wraps
import jwt
import os
from datetime import datetime, timedelta

from models import db, User, Consultant

auth_bp = Blueprint('auth', __name__)

# Configurações
SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('JWT_SECRET', 'nutricrm-secret-key-change-in-production'))
TOKEN_EXPIRY_DAYS = 30


def generate_token(user: User) -> str:
    """Gera JWT token para o usuário."""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'consultant_id': user.consultant_id,
        'is_admin': user.is_admin,
        'exp': datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS),
        'iat': datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> dict | None:
    """Decodifica e valida o token. Retorna payload ou None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user() -> User | None:
    """Retorna o usuário atual baseado no token do header."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]  # Remove 'Bearer '
    payload = decode_token(token)
    if not payload:
        return None

    user = User.query.get(payload.get('user_id'))
    if not user or not user.active:
        return None

    return user


def login_required(f):
    """Decorator que exige autenticação."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Não autenticado'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator que exige autenticação de admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Não autenticado'}), 401
        if not user.is_admin:
            return jsonify({'error': 'Acesso negado'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


# ============================================================
# POST /api/auth/login
# ============================================================
@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """
    Autentica usuário por username + senha.
    Retorna token JWT válido por 30 dias.
    """
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Usuário e senha são obrigatórios'}), 400

    user = User.query.filter(db.func.lower(User.username) == username).first()

    if not user:
        return jsonify({'error': 'Usuário ou senha incorretos'}), 401

    if not user.active:
        return jsonify({'error': 'Usuário desativado'}), 401

    if not user.check_password(password):
        return jsonify({'error': 'Usuário ou senha incorretos'}), 401

    token = generate_token(user)

    return jsonify({
        'ok': True,
        'token': token,
        'user': user.to_dict(),
    })


# ============================================================
# POST /api/auth/logout
# ============================================================
@auth_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """
    Logout do usuário.
    Com JWT stateless, o logout é feito no frontend descartando o token.
    Este endpoint existe para compatibilidade e logs futuros.
    """
    return jsonify({'ok': True, 'message': 'Logout realizado'})


# ============================================================
# GET /api/auth/me
# ============================================================
@auth_bp.route('/auth/me', methods=['GET'])
@login_required
def me():
    """Retorna dados do usuário autenticado."""
    user = g.current_user
    return jsonify({
        'ok': True,
        'user': user.to_dict(),
    })


# ============================================================
# POST /api/admin/users
# ============================================================
@auth_bp.route('/admin/users', methods=['POST'])
@admin_required
def create_user():
    """
    Cria novo usuário (somente admin).
    Body: { username, password, consultant_id?, is_admin? }
    """
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    consultant_id = data.get('consultant_id')
    is_admin = bool(data.get('is_admin', False))

    if not username:
        return jsonify({'error': 'Username é obrigatório'}), 400
    if len(username) < 3:
        return jsonify({'error': 'Username deve ter pelo menos 3 caracteres'}), 400
    if not password:
        return jsonify({'error': 'Senha é obrigatória'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Senha deve ter pelo menos 4 caracteres'}), 400

    # Verifica se username já existe
    existing = User.query.filter(db.func.lower(User.username) == username).first()
    if existing:
        return jsonify({'error': 'Username já existe'}), 409

    # Verifica consultant_id se fornecido
    if consultant_id:
        consultant = Consultant.query.get(consultant_id)
        if not consultant:
            return jsonify({'error': 'Consultor não encontrado'}), 404
        # Verifica se já existe user para este consultant
        existing_user = User.query.filter_by(consultant_id=consultant_id).first()
        if existing_user:
            return jsonify({'error': f'Já existe usuário para o consultor {consultant.name}'}), 409

    user = User(
        username=username,
        consultant_id=consultant_id,
        is_admin=is_admin,
        active=True,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'ok': True,
        'user': user.to_dict(),
    }), 201


# ============================================================
# GET /api/admin/users
# ============================================================
@auth_bp.route('/admin/users', methods=['GET'])
@admin_required
def list_users():
    """Lista todos os usuários (somente admin)."""
    users = User.query.order_by(User.username).all()
    return jsonify({
        'ok': True,
        'users': [u.to_dict() for u in users],
    })


# ============================================================
# PUT /api/admin/users/:id (editar usuário)
# ============================================================
@auth_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id: int):
    """
    Edita usuário (somente admin).
    Body: { consultant_id?, is_admin? }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.get_json() or {}

    # Atualiza consultant_id se fornecido
    if 'consultant_id' in data:
        new_consultant_id = data.get('consultant_id')
        if new_consultant_id is not None:
            consultant = Consultant.query.get(new_consultant_id)
            if not consultant:
                return jsonify({'error': 'Consultor não encontrado'}), 404
            # Verifica se já existe outro user para este consultant
            existing_user = User.query.filter(
                User.consultant_id == new_consultant_id,
                User.id != user_id
            ).first()
            if existing_user:
                return jsonify({'error': f'Já existe usuário para o consultor {consultant.name}'}), 409
        user.consultant_id = new_consultant_id

    # Atualiza is_admin se fornecido
    if 'is_admin' in data:
        # Não permite remover admin de si mesmo
        if user.id == g.current_user.id and not data.get('is_admin'):
            return jsonify({'error': 'Não é possível remover seu próprio status de admin'}), 400
        user.is_admin = bool(data.get('is_admin'))

    db.session.commit()

    return jsonify({
        'ok': True,
        'message': f'Usuário {user.username} atualizado',
        'user': user.to_dict(),
    })


# ============================================================
# PUT /api/admin/users/:id/reset-password
# ============================================================
@auth_bp.route('/admin/users/<int:user_id>/reset-password', methods=['PUT'])
@admin_required
def reset_password(user_id: int):
    """
    Reseta senha do usuário (somente admin).
    Body: { password }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.get_json() or {}
    password = data.get('password') or ''

    if not password:
        return jsonify({'error': 'Nova senha é obrigatória'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Senha deve ter pelo menos 4 caracteres'}), 400

    user.set_password(password)
    db.session.commit()

    return jsonify({
        'ok': True,
        'message': f'Senha do usuário {user.username} resetada com sucesso',
    })


# ============================================================
# PUT /api/admin/users/:id/toggle-active
# ============================================================
@auth_bp.route('/admin/users/<int:user_id>/toggle-active', methods=['PUT'])
@admin_required
def toggle_user_active(user_id: int):
    """Ativa/desativa usuário (somente admin)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Não permite desativar a si mesmo
    if user.id == g.current_user.id:
        return jsonify({'error': 'Não é possível desativar seu próprio usuário'}), 400

    user.active = not user.active
    db.session.commit()

    status = 'ativado' if user.active else 'desativado'
    return jsonify({
        'ok': True,
        'message': f'Usuário {user.username} {status}',
        'user': user.to_dict(),
    })


# ============================================================
# DELETE /api/admin/users/:id
# ============================================================
@auth_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id: int):
    """Exclui usuário (somente admin)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Não permite excluir a si mesmo
    if user.id == g.current_user.id:
        return jsonify({'error': 'Não é possível excluir seu próprio usuário'}), 400

    username = user.username
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'ok': True,
        'message': f'Usuário {username} excluído',
    })


# ============================================================
# GET /api/admin/consultants (para dropdown ao criar usuário)
# ============================================================
@auth_bp.route('/admin/consultants', methods=['GET'])
@admin_required
def list_consultants_for_admin():
    """Lista consultores disponíveis para vincular a usuários."""
    consultants = Consultant.query.order_by(Consultant.name).all()

    # Marca quais já têm usuário
    user_consultant_ids = {u.consultant_id for u in User.query.filter(User.consultant_id.isnot(None)).all()}

    result = []
    for c in consultants:
        result.append({
            'id': c.id,
            'name': c.name,
            'has_user': c.id in user_consultant_ids,
        })

    return jsonify({
        'ok': True,
        'consultants': result,
    })


# ============================================================
# GET /api/auth/fix-db (corrige estrutura da tabela users)
# ============================================================
@auth_bp.route('/auth/fix-db', methods=['POST'])
def fix_database_structure():
    """
    Corrige a estrutura da tabela users para o novo sistema de login.
    Endpoint temporário - remover após uso.
    """
    try:
        # Torna email nullable
        db.session.execute(db.text('ALTER TABLE users ALTER COLUMN email DROP NOT NULL'))
        db.session.commit()
        return jsonify({'ok': True, 'message': 'Estrutura corrigida com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ============================================================
# GET /api/auth/setup (verifica se precisa setup)
# ============================================================
@auth_bp.route('/auth/setup', methods=['GET'])
def check_setup_needed():
    """Verifica se o sistema precisa de setup inicial."""
    # Verifica se existe algum admin com a nova estrutura (username)
    has_admin = User.query.filter(
        User.is_admin == True,
        User.username.isnot(None)
    ).count() > 0

    return jsonify({
        'ok': True,
        'needs_setup': not has_admin,
    })


# ============================================================
# POST /api/auth/setup (criar primeiro admin) - ATUALIZADO
# ============================================================
@auth_bp.route('/auth/setup', methods=['POST'])
def setup_first_admin():
    """
    Cria o primeiro usuário admin.
    SÓ FUNCIONA se não houver nenhum admin com username configurado.
    Body: { username, password }
    """
    # Verifica se já existe admin com nova estrutura
    has_admin = User.query.filter(
        User.is_admin == True,
        User.username.isnot(None)
    ).count() > 0

    if has_admin:
        return jsonify({'error': 'Sistema já configurado'}), 403

    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not username or len(username) < 3:
        return jsonify({'error': 'Username deve ter pelo menos 3 caracteres'}), 400
    if not password or len(password) < 4:
        return jsonify({'error': 'Senha deve ter pelo menos 4 caracteres'}), 400

    # Verifica se username já existe
    existing = User.query.filter(db.func.lower(User.username) == username).first()
    if existing:
        return jsonify({'error': 'Username já existe'}), 409

    user = User(
        username=username,
        is_admin=True,
        active=True,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    token = generate_token(user)

    return jsonify({
        'ok': True,
        'message': 'Admin criado com sucesso',
        'token': token,
        'user': user.to_dict(),
    }), 201
