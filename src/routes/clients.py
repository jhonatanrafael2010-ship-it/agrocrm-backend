# routes/clients.py
"""
CRUD de clientes.
- /clients (GET, POST)
- /clients/<id> (GET, PUT, DELETE)
- /clients/search
- /clients/<id>/plantings
"""

from flask import Blueprint, jsonify, request
from difflib import SequenceMatcher
import re
import unicodedata

from models import db, Client, Property, Plot, Planting

clients_bp = Blueprint('clients', __name__)


def _normalize_lookup_text(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


@clients_bp.route('/clients', methods=['GET'])
def get_clients():
    """Return list of clients."""
    clients = Client.query.order_by(Client.id.desc()).all()
    return jsonify([c.to_dict() for c in clients]), 200


@clients_bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    return jsonify(client.to_dict()), 200


@clients_bp.route('/clients', methods=['POST'])
def create_client():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify(message='name is required'), 400

    client = Client(
        name=name,
        document=data.get('document'),
        segment=data.get('segment'),
        vendor=data.get('vendor'),
        region=data.get('region') or None,
    )
    db.session.add(client)
    db.session.commit()
    return jsonify(message='client created', client=client.to_dict()), 201


@clients_bp.route('/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    data = request.get_json() or {}

    for field in ('name', 'document', 'segment', 'vendor', 'region'):
        if field in data:
            value = data.get(field)
            setattr(client, field, value if value else None)

    db.session.commit()
    return jsonify(message='client updated', client=client.to_dict()), 200


@clients_bp.route('/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    db.session.delete(client)
    db.session.commit()
    return jsonify(message='client deleted'), 200


@clients_bp.route("/clients/search", methods=["GET"])
def search_clients():
    """Busca fuzzy de clientes pelo nome."""
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 10, type=int)

    if not q:
        return jsonify([]), 200

    target = _normalize_lookup_text(q)
    clients = Client.query.all()

    scored = []
    for c in clients:
        current = _normalize_lookup_text(c.name)
        score = SequenceMatcher(None, target, current).ratio()

        if target in current or current in target:
            score = max(score, 0.8)

        scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = [item[0] for item in scored[:limit] if item[1] >= 0.3]

    return jsonify([
        {"id": c.id, "name": c.name, "region": c.region}
        for c in top
    ]), 200


@clients_bp.route("/clients/<int:client_id>/plantings", methods=["GET"])
def get_client_plantings(client_id: int):
    """Retorna plantios do cliente com info de fazenda/talhão."""
    client = Client.query.get(client_id)
    if not client:
        return jsonify(error="Cliente não encontrado"), 404

    properties = Property.query.filter_by(client_id=client_id).all()
    property_ids = [p.id for p in properties]

    if not property_ids:
        return jsonify([]), 200

    plots = Plot.query.filter(Plot.property_id.in_(property_ids)).all()
    plot_ids = [pl.id for pl in plots]

    if not plot_ids:
        return jsonify([]), 200

    plantings = Planting.query.filter(Planting.plot_id.in_(plot_ids)).all()

    property_map = {p.id: p for p in properties}
    plot_map = {pl.id: pl for pl in plots}

    result = []
    for pt in plantings:
        plot = plot_map.get(pt.plot_id)
        prop = property_map.get(plot.property_id) if plot else None

        result.append({
            "id": pt.id,
            "culture": pt.culture,
            "variety": pt.variety,
            "planting_date": pt.planting_date.isoformat() if pt.planting_date else None,
            "plot_id": pt.plot_id,
            "plot_name": plot.name if plot else None,
            "property_id": prop.id if prop else None,
            "property_name": prop.name if prop else None,
        })

    return jsonify(result), 200
