import os
from urllib.parse import quote_plus
from flask import Flask
from flask_cors import CORS
from models import db


def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app)

    # Configure database connection from environment (Render):
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

    # register blueprints
    from routes import bp as api_bp
    app.register_blueprint(api_bp)

    # create tables at startup (safe for simple apps/tests)
    with app.app_context():
        db.create_all()

    return app


# For gunicorn and simple runs, expose an `app` variable
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)