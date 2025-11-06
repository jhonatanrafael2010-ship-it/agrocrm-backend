import os
from urllib.parse import quote_plus
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
from models import db, Culture, Variety, PhenologyStage, User
from routes import bp as api_bp

# =====================================================
# 🌱 Seeds iniciais — Culturas, Variedades, Fenologia e Usuário padrão
# =====================================================

def seed_cultures_and_varieties():
    # ... (mantém seu conteúdo atual)
    pass

def seed_phenology_stages():
    # ... (mantém seu conteúdo atual)
    pass

def seed_default_user():
    # ... (mantém seu conteúdo atual)
    pass

# =====================================================
# 📂 Diretórios importantes
# =====================================================
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# garante que as pastas existam
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)


# =====================================================
# 🚀 Criação da aplicação Flask
# =====================================================
def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    CORS(app, supports_credentials=True)

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
            app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_pass_enc}@{db_host}{port_part}/{db_name}"
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

    # =====================================================
    # 📸 Rotas estáticas
    # =====================================================

    # 1️⃣ Servir imagens de uploads (fotos das visitas)
    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            print(f"⚠️ Arquivo não encontrado: {file_path}")
            abort(404)
        return send_from_directory(UPLOAD_DIR, filename)

    # 2️⃣ Servir logo e arquivos estáticos do app
    @app.route("/static/<path:filename>")
    def serve_static(filename):
        file_path = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(file_path):
            print(f"⚠️ Arquivo estático não encontrado: {file_path}")
            abort(404)
        return send_from_directory(STATIC_DIR, filename)

    # =====================================================
    # 🏠 Rota raiz de teste
    # =====================================================
    @app.route("/")
    def index():
        return jsonify({
            "message": "✅ API do NutriCRM rodando com sucesso!",
            "version": "1.0",
            "status": "ok"
        })

    # =====================================================
    # 🌾 Seeds iniciais
    # =====================================================
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



from models import db, Client, Consultant  # já deve estar importado lá em cima

def auto_populate_database():
    """Popula APENAS clientes e consultores se o banco estiver vazio.

    Culturas, variedades e estágios fenológicos já são populados
    por outro trecho do código (aquele que imprime ✅ Culturas e variedades fixas populadas!).
    """
    try:
        # Se já existir qualquer cliente, não faz nada
        if Client.query.first():
            print("ℹ️ Banco já possui clientes. Não será feito repovoamento automático.")
            return

        print("🌱 Banco vazio detectado. Preenchendo dados iniciais (clientes e consultores)...")

        # 🔹 Consultores fixos
        if Consultant.query.count() == 0:
            consultants = [
                "Jhonatan",
                "Pedro",
                "Felipe",
                "Everton",
                "Alexandre",
            ]
            for nome in consultants:
                db.session.add(Consultant(name=nome))

        # 🔹 Lista de clientes que você me passou
        clientes_data = [
            {"name": "Edevi Massoni", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Livenio Sanini", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Eduardo Lorenzi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Claudio Duffeck", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Elias Soares ", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Everton Melchior", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ademir Fischer", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcos Zanin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ivan Zanin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Simao Da Silva", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Robson Nadin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ademir Bonfanti", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Luis Martins", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ivo Cella", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Pedro Copini", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Giovane  Paloschi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Gustavo Paloschi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Alexandre Barzotto", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Evaristo Barzotto", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Enio Rigo", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcelo Alonso", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Matheus Alonso", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Cesar Prediger", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ryan Boyaski", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marco H. Bares", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Daniel Capelin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Macleiton Priester", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Roberto Bogorni", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcio Basso", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Emilio Carlos Gonzatto", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Flavio Remor", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Edgar Stragliotto", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Amilton Oliveira", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Egon Afonso Schons", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Arlei Favaretto", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Fabiano Zilli", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Daniel Vian", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Paulo kummer", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Lair Prediger", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Cleiton Bigaton", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Michel Starlick", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Sidney Scopel", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Paulo Cesar Iores", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Tarcisio Garbin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Julia Barzagui", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Gracieti Casagranda", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Neuri Schereiner", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Nirval Strapasson", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Mauro Techio", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Sandro Bonasa", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Pasquali", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ivanir Meneguzzo", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Darci Ely", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Vanderlei Vitiorassi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Fiorin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Cerone Gurgel", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Gelson Tibirissa", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Ednilson Melchior", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Antonio Uncini", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcos Terhorst", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Everton Turqueti", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Alexandro Lorenzi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Taparello", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Claudio Schons", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Raquel Ida", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Luis de Marco", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Rafael Nadin", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Cirilo Remor", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Rizzi", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Andre Picolo", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Tarciano Remor", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Pedro Cossul", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Andre Eikoff", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcos Puziski", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Rogerio Remor", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Cristiano Escobar", "document": "--", "segment": "Agronegócio", "consultor": ""},
            {"name": "Marcos Ioris", "document": "--", "segment": "Agronegócio", "consultor": ""},
        ]

        for c in clientes_data:
            client = Client(
                name=c["name"],
                document=c.get("document", ""),
                segment=c.get("segment", ""),
                vendor=c.get("consultor") or "",
            )
            db.session.add(client)

        db.session.commit()
        print("✅ Clientes e consultores restaurados com sucesso!")

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao popular o banco automaticamente: {e}")


# ============================================================
# 🚀 Popula dados iniciais (clientes e consultores)
# ============================================================
with app.app_context():
    auto_populate_database()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
