# routes/chatbot.py
"""
Endpoints do chatbot (preview/suggest/resolve/commit).
- /chatbot/preview-visit
- /chatbot/suggest-pending-visits
- /chatbot/resolve-confirmation
- /chatbot/commit-visit

NOTA: Este módulo importa do routes.py original por enquanto.
Será migrado gradualmente.
"""

from flask import Blueprint

chatbot_bp = Blueprint('chatbot', __name__)

# Os endpoints são registrados pelo routes.py original por enquanto
