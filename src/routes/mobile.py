# routes/mobile.py
"""
Endpoints do app mobile.
- /mobile/chat (assistente IA - principal)
- /mobile/pdf-proxy
- /mobile/transcribe

NOTA: Este módulo importa do routes.py original por enquanto.
Será migrado gradualmente. O endpoint /mobile/chat tem ~1200 linhas.
"""

from flask import Blueprint

mobile_bp = Blueprint('mobile', __name__)

# Os endpoints são registrados pelo routes.py original por enquanto
