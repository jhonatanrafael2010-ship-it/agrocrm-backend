import os
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy import text
from threading import Timer
from models import db, Client, Consultant
from routes import bp as api_bp

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

db_status = {"engine": "desconhecido"}  # 🧠 guarda status atual

# =====================================================
# 🚀 Criação da aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    CORS(app, supports_credentials=True)

    pg_url = os.environ.get("DATABASE_URL") or os.environ.get("INTERNAL_DATABASE_URL")
    sqlite_path = os.path.join(UPLOAD_DIR, "fallback_local.db")

    # =====================================================
    # 🧠 Testa conexão real com PostgreSQL
    # =====================================================
    def try_postgres():
        if not pg_url or not pg_url.startswith("postgresql"):
            return False
        try:
            tmp_app = Flask(__name__)
            tmp_app.config["SQLALCHEMY_DATABASE_URI"] = pg_url
            tmp_db = db
            tmp_db.init_app(tmp_app)
            with tmp_app.app_context():
                tmp_db.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    # =====================================================
    # 🔁 Conecta com fallback automático
    # =====================================================
    def connect_database():
        if pg_url and try_postgres():
            app.config["SQLALCHEMY_DATABASE_URI"] = pg_url
            db.init_app(app)
            db_status["engine"] = "postgresql"
            print("🟢 Conectado ao PostgreSQL do Render.")
        else:
            app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"
            db.init_app(app)
            db_status["engine"] = "sqlite"
            print(f"🟡 Usando banco SQLite local: {sqlite_path}")

    connect_database()

    # =====================================================
    # ⏱️ Verificação automática a cada 30 min
    # =====================================================
    def periodic_check():
        try:
            if db_status["engine"] == "sqlite" and try_postgres():
                print("✅ PostgreSQL disponível novamente — migrando de volta...")
                app.config["SQLALCHEMY_DATABASE_URI"] = pg_url
                with app.app_context():
                    db.engine.dispose()
                    db.create_all()
                    db_status["engine"] = "postgresql"
                    print("🔄 Migração automática concluída com sucesso.")
            elif db_status["engine"] == "postgresql":
                with app.app_context():
                    db.session.execute(text("SELECT 1"))
        except Exception as e:
            print(f"⚠️ Verificação periódica detectou erro: {e}")
            db_status["engine"] = "sqlite"
        finally:
            Timer(1800, periodic_check).start()  # 30 minutos

    Timer(1800, periodic_check).start()

    # =====================================================
    # ⚙️ Configurações adicionais
    # =====================================================
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }

    Migrate(app, db)
    app.register_blueprint(api_bp)

    # =====================================================
    # 🖼️ Rotas de arquivos
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
    # 🏠 Rota principal
    # =====================================================
    @app.route("/")
    def index():
        return jsonify({
            "message": "✅ API do NutriCRM rodando com sucesso!",
            "status": "ok"
        })

    # =====================================================
    # 📡 Nova rota de status da base
    # =====================================================
    @app.route("/api/status")
    def db_status_route():
        engine = db_status.get("engine", "desconhecido")
        if engine == "postgresql":
            label = "🟢 Conectado ao servidor principal (PostgreSQL)"
        elif engine == "sqlite":
            label = "🟡 Operando em modo local (SQLite)"
        else:
            label = "🔴 Banco de dados desconhecido"
        return jsonify({
            "engine": engine,
            "message": label
        })

    # =====================================================
    # 🌾 Seeds automáticos
    # =====================================================
    with app.app_context():
        db.create_all()
        try:
            auto_populate_database()
        except Exception as e:
            print(f"⚠️ Erro ao executar população automática: {e}")

    return app


# =====================================================
# 🌱 População inicial
# =====================================================
def auto_populate_database():
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
# 👟 Execução direta
# =====================================================
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
