import os
from urllib.parse import quote_plus
from flask import Flask, jsonify
from flask_cors import CORS
from models import db, Culture, Variety, PhenologyStage, User
from flask_migrate import Migrate
from routes import bp as api_bp
from werkzeug.security import generate_password_hash
from flask import send_from_directory

# =====================================================
# 🌱 Seeds iniciais — Culturas, Variedades, Fenologia e Usuário padrão
# =====================================================

def seed_cultures_and_varieties():
    """Popula Culturas e Variedades fixas se ainda não existirem."""
    data = {
        "Milho": ["AS 1820 PRO4", "AS 1868 PRO4", "AS 1877 PRO4","AS 1838 PRO4","AS 1955 PRO4"],
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


def seed_phenology_stages():
    """Popula estágios fenológicos fixos para Milho, Soja e Algodão."""
    stages = [
        # 🌽 Milho
        ("Milho", "VE", "Emergência", 0),
        ("Milho", "V4", "4 folhas expandidas", 21),
        ("Milho", "VT", "Pendoamento", 60),
        ("Milho", "R1", "Florescimento", 70),
        ("Milho", "R6", "Maturação fisiológica", 100),
        # 🌱 Soja
        ("Soja", "VE", "Emergência", 0),
        ("Soja", "V4", "4 nós expandidos", 25),
        ("Soja", "R1", "Início de florescimento", 50),
        ("Soja", "R5", "Enchimento de grãos", 90),
        ("Soja", "R8", "Maturação fisiológica", 120),
        # ☁️ Algodão
        ("Algodão", "VE", "Emergência", 0),
        ("Algodão", "B1", "Botão floral", 45),
        ("Algodão", "F", "Florescimento", 65),
        ("Algodão", "CA", "Capulho aberto", 120),
    ]

    for culture, code, name, days in stages:
        exists = PhenologyStage.query.filter_by(culture=culture, code=code).first()
        if not exists:
            db.session.add(
                PhenologyStage(
                    culture=culture,
                    code=code,
                    name=name,
                    days=days
                )
            )

    db.session.commit()
    print("✅ Estágios fenológicos fixos populados!")


def seed_default_user():
    """Cria um consultor padrão se não existir (id=1)."""
    user = User.query.get(1)
    if not user:
        user = User(
            id=1,
            email="consultor@agrocrm.com",
            password_hash=generate_password_hash("123456")
        )
        db.session.add(user)
        db.session.commit()
        print("✅ Usuário padrão criado (consultor@agrocrm.com / 123456)")
    else:
        print("ℹ️ Usuário padrão já existe.")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/opt/render/project/src/uploads")  # <— padrão: disco do Render

# =====================================================
# 🚀 Criação da aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__)
    # ✅ Servir imagens da pasta "uploads"
    CORS(app, supports_credentials=True)

    # garante pasta de uploads
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Configuração do banco
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
            app.config['SQLALCHEMY_DATABASE_URI'] = (
                f"postgresql://{db_user}:{db_pass_enc}@{db_host}{port_part}/{db_name}"
            )
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10
    }

    # Inicializa extensões
    db.init_app(app)
    Migrate(app, db)
    app.register_blueprint(api_bp)

    # ✅ Servir arquivos enviados (fotos das visitas)
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(UPLOAD_DIR, filename)  # <— CORREÇÃO: indentação e diretório

    @app.route("/")
    def index():
        return jsonify({
            "message": "✅ API do AgroCRM rodando com sucesso!",
            "version": "1.0",
            "status": "ok"
        })

    # Seeds iniciais
    with app.app_context():
        db.create_all()
        try:
            seed_cultures_and_varieties()
            seed_phenology_stages()
            seed_default_user()
        except Exception as e:
            print(f"⚠️ Erro ao executar seed: {e}")

    return app



# =====================================================
# 👟 Execução local e Render
# =====================================================
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
