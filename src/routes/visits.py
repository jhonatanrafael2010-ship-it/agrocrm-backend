# routes/visits.py
"""
CRUD de visitas e relacionados.
- /visits (GET, POST)
- /visits/<id> (GET, PUT, DELETE)
- /visits/<id>/photos
- /visits/<id>/pdf
- /visits/<id>/products
- /visits/<id>/link-planting
- /visits/bulk
- /phenology/schedule
- /photos/<id>
- /products/<id>
- /view/visit/<id>
- /orphan-visits
- /fix-orphan-visits

NOTA: Este módulo importa do routes.py original por enquanto.
Será migrado gradualmente.
"""

from flask import Blueprint

visits_bp = Blueprint('visits', __name__)

# Importação tardia para evitar dependências circulares
# Os endpoints são registrados pelo routes.py original por enquanto
