"""
Script de migração automática para corrigir colunas ausentes na tabela 'visits'.
Detecta e cria 'culture' e 'variety' caso não existam.
"""

import sys, os
# adiciona o caminho da pasta src ao Python
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from app import app
from models import db
from sqlalchemy import inspect, text

def ensure_visit_columns():
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('visits')]

        added = []
        if 'culture' not in columns:
            db.engine.execute(text('ALTER TABLE visits ADD COLUMN culture VARCHAR(120);'))
            added.append('culture')

        if 'variety' not in columns:
            db.engine.execute(text('ALTER TABLE visits ADD COLUMN variety VARCHAR(200);'))
            added.append('variety')

        if added:
            print(f"✅ Colunas adicionadas com sucesso: {', '.join(added)}")
        else:
            print("⚙️  As colunas 'culture' e 'variety' já existem — nada foi alterado.")

if __name__ == "__main__":
    ensure_visit_columns()
