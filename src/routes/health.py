# routes/health.py
"""
Endpoints de saúde e debug.
- /ping
- /status
- /hello
- /db-test
- /debug/*
"""

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from models import db, User, Client, Property, Plot, Visit

health_bp = Blueprint('health', __name__)

BUILD_STAMP = "routes_2026_05_21_refactor_01"


@health_bp.route("/ping", methods=["GET"])
def ping():
    return "pong", 200


@health_bp.route("/status")
def status():
    return jsonify({
        "ok": True,
        "clients": Client.query.count(),
        "properties": Property.query.count(),
        "plots": Plot.query.count(),
        "visits": Visit.query.count(),
    }), 200


@health_bp.route("/hello", methods=["GET"])
def hello():
    return jsonify(message="Hello from Flask!")


@health_bp.route("/db-test", methods=["GET"])
def db_test():
    """Simple endpoint to test DB connectivity and return user count."""
    try:
        result = None
        with db.engine.connect() as conn:
            row = conn.execute(text('SELECT 1')).fetchone()
            result = row[0] if row is not None else None

        user_count = User.query.count()
        return jsonify(status='ok', ping=result, users=user_count), 200
    except Exception as e:
        return jsonify(status='error', error=str(e)), 500


@health_bp.route("/debug/build-stamp", methods=["GET"])
def debug_build_stamp():
    return jsonify({
        "ok": True,
        "build_stamp": BUILD_STAMP
    }), 200


@health_bp.route("/debug/routes-visits", methods=["GET"])
def debug_routes_visits():
    routes = []

    for rule in current_app.url_map.iter_rules():
        rule_str = str(rule)
        if "/api/visits" in rule_str:
            methods = sorted([m for m in rule.methods if m not in {"HEAD", "OPTIONS"}])
            routes.append({
                "rule": rule_str,
                "methods": methods,
                "endpoint": rule.endpoint,
            })

    routes.sort(key=lambda x: x["rule"])
    return jsonify({
        "ok": True,
        "build_stamp": BUILD_STAMP,
        "routes": routes,
    }), 200
