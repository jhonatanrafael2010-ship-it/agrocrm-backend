# utils/auth_helper.py
"""
Helpers de autenticação para uso em múltiplas rotas.
"""

from flask import request, g
from functools import wraps
import jwt
import os

from models import User


SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('JWT_SECRET', 'nutricrm-secret-key-change-in-production'))


def get_current_user_from_token() -> User | None:
    """
    Obtém o usuário atual a partir do token JWT.
    Retorna None se não autenticado ou token inválido.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

    user = User.query.get(payload.get('user_id'))
    if not user or not user.active:
        return None

    return user


def get_consultant_id_filter() -> int | None:
    """
    Retorna o consultant_id para filtrar dados.
    - Retorna None se usuário é admin (acesso total)
    - Retorna consultant_id se usuário tem um vinculado
    - Retorna -1 se usuário não-admin sem consultant (não vê nada)
    """
    user = get_current_user_from_token()
    if not user:
        return None  # Sem auth, sem filtro (comportamento legado)

    if user.is_admin:
        return None  # Admin vê tudo

    if user.consultant_id:
        return user.consultant_id

    # Usuário não-admin sem consultant_id não deve ver nada
    return -1


def optional_auth(f):
    """
    Decorator que carrega o usuário atual se token fornecido.
    Não bloqueia se não autenticado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = get_current_user_from_token()
        return f(*args, **kwargs)
    return decorated


def apply_consultant_filter(query, consultant_id_column):
    """
    Aplica filtro por consultant_id na query.
    Retorna a query modificada.
    """
    filter_id = get_consultant_id_filter()

    if filter_id is None:
        return query  # Sem filtro

    if filter_id == -1:
        # Usuário não-admin sem consultant - retorna vazio
        return query.filter(consultant_id_column == -999999)

    return query.filter(consultant_id_column == filter_id)
