import os
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy import text, create_engine
from models import db, Client, Consultant
from routes import bp as api_bp

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

db_status = {"engine": "desconhecido"}

# =====================================================
# 🚀 Criação da aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    CORS(app, supports_credentials=True)

    pg_url = os.environ.get("DATABASE_URL")
    sqlite_path = os.path.join(UPLOAD_DIR, "fallback_local.db")

    # =====================================================
    # 🧠 Testa PostgreSQL corretamente (sem criar outro Flask)
    # =====================================================
    def try_postgres_connection():
        if not pg_url:
            return False
        try:
            engine = create_engine(pg_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print("⚠️ PostgreSQL indisponível:", e)
            return False

    @app.route("/api/ping")
    def ping():
        return jsonify({"status": "ok"})

    # =====================================================
    # ⚙ Configurações antes do init_app
    # =====================================================
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 180,
        "pool_timeout": 30
    }

    # =====================================================
    # 🔌 Seleção final do banco
    # =====================================================
    if try_postgres_connection():
        print("🟢 Conectado ao PostgreSQL do Render.")
        app.config["SQLALCHEMY_DATABASE_URI"] = pg_url
        db_status["engine"] = "postgresql"
    else:
        print("🟡 Usando SQLite local:", sqlite_path)
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"
        db_status["engine"] = "sqlite"

    # 🔥 Inicializa DB
    db.init_app(app)
    Migrate(app, db)

    # =====================================================
    # Rotas
    # =====================================================
    app.register_blueprint(api_bp)

    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            abort(404)
        return send_from_directory(UPLOAD_DIR, filename)

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        file_path = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(file_path):
            abort(404)
        return send_from_directory(STATIC_DIR, filename)

    @app.route("/")
    def index():
        return jsonify({"message": "API NutriCRM OK", "status": "ok"})

    @app.route("/api/status")
    def db_status_route():
        engine = db_status["engine"]
        return jsonify({
            "engine": engine,
            "message": "🟢 PostgreSQL" if engine == "postgresql" else "🟡 SQLite"
        })

    # =====================================================
    # Seeds — só roda em SQLite
    # =====================================================
    with app.app_context():
        db.create_all()
        if db_status["engine"] == "sqlite":
            try:
                auto_populate_database()
            except Exception as e:
                print("⚠️ Erro ao executar seeds:", e)

    return app


# =====================================================
# 🌱 Seeds
# =====================================================
def auto_populate_database():
    if Client.query.first():
        print("ℹ️ Banco já possui clientes.")
        return

    print("🌱 Criando dados iniciais...")
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
    print("✅ Seeds concluídos.")


# =====================================================
# 👟 Execução direta
# =====================================================
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
