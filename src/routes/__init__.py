# routes/__init__.py
"""
Sub-módulos de rotas da API.

Este diretório contém módulos separados por domínio.
O arquivo principal routes.py (em src/) importa estes módulos
e registra os blueprints no blueprint principal 'bp'.

ESTRUTURA:
- health.py       → /ping, /status, /debug/*
- lookups.py      → /cultures, /varieties, /consultants, /regions, /seasons
- auth.py         → /login, /me, /users
- clients.py      → /clients CRUD
- entities.py     → /properties, /plots, /plantings
- opportunities.py → /opportunities CRUD
"""

# Re-exporta os blueprints para facilitar importação
from .health import health_bp
from .lookups import lookups_bp
from .auth import auth_bp
from .clients import clients_bp
from .entities import entities_bp
from .opportunities import opportunities_bp

__all__ = [
    'health_bp',
    'lookups_bp',
    'auth_bp',
    'clients_bp',
    'entities_bp',
    'opportunities_bp',
]
