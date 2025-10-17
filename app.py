import os
from urllib.parse import quote_plus
from flask import Flask
from flask_cors import CORS
from models import db, Culture, Variety
from routes import bp as api_bp  # ✅ importa as rotas

# =====================================================
# 🌱 Função de Seed: cria Culturas e Variedades fixas
# =====================================================
def seed_cultures_and_varieties():
    """Popula Culturas e Variedades fixas se ainda não existirem"""
    data = {
        "Milho": ["AS 1820 PRO4", "AS 1868 PRO4", "AS 1877 PRO4"],
        "Soja": [
            "AS 3800 12X", "AS 3840 12X", "AS 3790 12X",
            "AS 3815 12X", "AS 3707 12X", "AS 3700 XTD",
            "AS 3640 12X", "AS 3715 12X"
        ],
        "Algodão": ["TMG 41"]
    }

    for culture_name, varieties in data.items():
        culture = Culture.query.filter_by(name=culture_name).first()
        if not culture:
            culture = Culture(name=culture_name)
            db.session.add(culture)
            db.session.commit()

        for vname in varieties:
            exists = Variety.query.filter_by(name=vname, culture_id=culture.id).first()
            if not exists:
                db.session.add(Variety(name=vname, culture_id=culture.id))

    db.session.commit()
    print("✅ Culturas e variedades fixas populadas!")


# =====================================================
# 🚀 Criação da Aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app)

    # ------------------------------------------
    # Configuração do banco (Postgres ou SQLite)
    # ------------------------------------------
    internal_url = os.environ.get('INTERNAL_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if internal_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = internal_url
    else:
        db_user = os.environ.get('DB_USERNAME')
        db_pass = os.environ.get('DB_PASSWORD')
        db_host = os.environ.get('DB_HOST')
        db_port = os.environ.get('DB_PORT')
        db_name = os.environ.get('DB_NAME')

        if db_user and db_pass and db_host and db_name:
            db_pass_enc = quote_plus(db_pass)
            port_part = f":{db_port}" if db_port else ""
            app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_pass_enc}@{db_host}{port_part}/{db_name}"
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # ------------------------------------------
    # Registro das rotas principais /api
    # ------------------------------------------
    app.register_blueprint(api_bp)

    # ------------------------------------------
    # Endpoint raiz para teste rápido
    # ------------------------------------------
    @app.route("/")
    def index():
        return "✅ API do AgroCRM rodando com sucesso!"

    # ------------------------------------------
    # Inicialização do banco e seed
    # ------------------------------------------
    with app.app_context():
        db.create_all()
        seed_cultures_and_varieties()

    return app


# =====================================================
# 👟 Execução local ou Render
# =====================================================
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
