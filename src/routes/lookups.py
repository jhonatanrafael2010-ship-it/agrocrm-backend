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


@lookups_bp.route('/varieties', methods=['POST'])
def create_variety():
    from models import db
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    culture_id = data.get("culture_id")

    if not name:
        return jsonify({"error": "name é obrigatório"}), 400
    if not culture_id:
        return jsonify({"error": "culture_id é obrigatório"}), 400

    existing = Variety.query.filter(
        Variety.name == name,
        Variety.culture_id == culture_id
    ).first()
    if existing:
        return jsonify({"error": "Variedade já existe para esta cultura"}), 409

    variety = Variety(name=name, culture_id=culture_id)
    db.session.add(variety)
    db.session.commit()

    culture = Culture.query.get(culture_id)

    return jsonify({
        "id": variety.id,
        "name": variety.name,
        "culture_id": variety.culture_id,
        "culture": culture.name if culture else "",
    }), 201


@lookups_bp.route('/varieties/<int:variety_id>', methods=['DELETE'])
def delete_variety(variety_id):
    from models import db
    variety = Variety.query.get(variety_id)
    if not variety:
        return jsonify({"error": "Variedade não encontrada"}), 404

    db.session.delete(variety)
    db.session.commit()

    return jsonify({"message": "Variedade excluída com sucesso"}), 200


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
