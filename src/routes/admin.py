# routes/admin.py
"""
Endpoints administrativos e cron jobs.
- /admin/diseases
- /admin/diseases/<slug>/image
- /admin/diseases/upload-batch
- /admin/generate-seed
- /admin/seed-stats
- /cron/daily-reminders
- /cron/test-reminder/<id>
- /insights/<id>
- /reports/monthly.xlsx

NOTA: Este módulo importa do routes.py original por enquanto.
Será migrado gradualmente.
"""

from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# Os endpoints são registrados pelo routes.py original por enquanto
