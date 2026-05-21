# routes/messaging.py
"""
Webhooks e bindings de mensagens.
- /whatsapp/webhook
- /whatsapp/bindings
- /telegram/webhook
- /telegram/bindings
- /telegram/test-send
- /telegram/setup-link-codes

NOTA: Este módulo importa do routes.py original por enquanto.
Será migrado gradualmente.
"""

from flask import Blueprint

messaging_bp = Blueprint('messaging', __name__)

# Os endpoints são registrados pelo routes.py original por enquanto
