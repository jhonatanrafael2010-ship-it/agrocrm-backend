# routes/lookups.py
"""
Endpoints de lookup (dropdowns no frontend).
- /cultures
- /varieties
- /consultants
- /regions
- /seasons
"""

from flask import Blueprint, jsonify, request

from models import Variety, Culture, Consultant, AVAILABLE_REGIONS, AVAILABLE_SEASONS

lookups_bp = Blueprint('lookups', __name__)


@lookups_bp.route('/cultures', methods=['GET'])
def list_cultures():
    CULTURES = [
        {"id": 1, "name": "Milho"},
        {"id": 2, "name": "Soja"},
        {"id": 3, "name": "Algodão"},
    ]
    return jsonify(CULTURES), 200


@lookups_bp.route('/varieties', methods=['GET'])
def list_varieties():
    culture_id = request.args.get("culture_id", type=int)

    q = Variety.query
    if culture_id:
        q = q.filter(Variety.culture_id == culture_id)

    rows = q.order_by(Variety.id.asc()).all()
    culture_map = {c.id: c.name for c in Culture.query.all()}

    return jsonify([
        {
            "id": v.id,
            "culture_id": v.culture_id,
            "culture": culture_map.get(v.culture_id, ""),
            "name": v.name,
        }
        for v in rows
    ]), 200


@lookups_bp.route('/consultants', methods=['GET'])
def list_consultants():
    rows = Consultant.query.order_by(Consultant.id.asc()).all()

    if rows:
        return jsonify([
            {
                "id": c.id,
                "name": c.name,
            }
            for c in rows
        ]), 200

    return jsonify([]), 200


@lookups_bp.route('/regions', methods=['GET'])
def list_regions():
    """Retorna lista de regiões disponíveis para classificar clientes."""
    return jsonify(AVAILABLE_REGIONS), 200


@lookups_bp.route('/seasons', methods=['GET'])
def list_seasons():
    """Retorna lista de safras disponíveis para filtrar relatórios."""
    return jsonify(AVAILABLE_SEASONS), 200
