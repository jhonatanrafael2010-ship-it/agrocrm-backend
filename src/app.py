import os
from urllib.parse import quote_plus
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Culture, Variety, PhenologyStage, User, Client, Consultant
from routes import bp as api_bp

# =====================================================
# 📂 Diretórios principais
# =====================================================
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)


# =====================================================
# 🚀 Criação da aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    CORS(app, supports_credentials=True)

    # =====================================================
    # 🗄️ Configuração do banco de dados (usa SQLite se Postgres estiver desativado)
    # =====================================================
    try:
        disable_pg = os.environ.get("DISABLE_PG", "").lower() == "true"
        internal_url = os.environ.get("INTERNAL_DATABASE_URL") or os.environ.get("DATABASE_URL")

        if not disable_pg and internal_url and internal_url.startswith("postgresql"):
            app.config["SQLALCHEMY_DATABASE_URI"] = internal_url
            print("🟢 Usando banco PostgreSQL do Render.")
        else:
            raise ValueError("Postgres desativado ou indisponível — usando SQLite.")
    except Exception as e:
        sqlite_path = os.path.join(UPLOAD_DIR, "database.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"
        print(f"🟡 Usando banco SQLite local: {sqlite_path} — motivo: {e}")

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }



    # =====================================================
    # 🔌 Inicializações
    # =====================================================
    db.init_app(app)
    Migrate(app, db)
    app.register_blueprint(api_bp)

    # =====================================================
    # 🖼️ Rotas para arquivos estáticos e uploads
    # =====================================================
    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            print(f"⚠️ Arquivo não encontrado: {file_path}")
            abort(404)
        return send_from_directory(UPLOAD_DIR, filename)

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        file_path = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(file_path):
            print(f"⚠️ Arquivo estático não encontrado: {file_path}")
            abort(404)
        return send_from_directory(STATIC_DIR, filename)

    # =====================================================
    # 🏠 Rota principal de teste
    # =====================================================
    @app.route("/")
    def index():
        return jsonify({
            "message": "✅ API do NutriCRM rodando com sucesso!",
            "version": "1.0",
            "status": "ok",
        })

    # =====================================================
    # 🌾 Inicialização e seeds automáticos
    # =====================================================
    with app.app_context():
        db.create_all()
        try:
            auto_populate_database()
        except Exception as e:
            print(f"⚠️ Erro ao executar população automática: {e}")

    return app


# =====================================================
# 🌱 Função para popular dados iniciais
# =====================================================
def auto_populate_database():
    """Cria consultores e clientes padrão se o banco estiver vazio."""
    try:
        if Client.query.first():
            print("ℹ️ Banco já possui clientes. Nenhuma ação necessária.")
            return

        print("🌱 Criando dados iniciais (clientes e consultores)...")

        if Consultant.query.count() == 0:
            for nome in ["Jhonatan", "Pedro", "Felipe", "Everton", "Alexandre"]:
                db.session.add(Consultant(name=nome))

        clientes = [
            "Edevi Massoni", "Livenio Sanini", "Eduardo Lorenzi",
            "Claudio Duffeck", "Elias Soares", "Everton Melchior",
            "Ademir Fischer", "Marcos Zanin", "Ivan Zanin",
            "Simao Da Silva", "Robson Nadin", "Ademir Bonfanti"
        ]

        for nome in clientes:
            db.session.add(Client(name=nome, document="--", segment="Agronegócio", vendor=""))

        db.session.commit()
        print("✅ Banco populado com sucesso!")

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao popular banco: {e}")


# =====================================================
# 👟 Execução principal
# =====================================================
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
