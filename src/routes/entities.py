# routes/entities.py
"""
CRUD de entidades hierárquicas.
- /properties (GET, POST)
- /properties/<id> (GET, PUT, DELETE)
- /plots (GET, POST)
- /plots/<id> (GET, PUT, DELETE)
- /plantings (GET, POST)
- /plantings/<id> (GET, PUT, DELETE)
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

from models import db, Client, Property, Plot, Planting, Visit

entities_bp = Blueprint('entities', __name__)


def _parse_optional_float(value):
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# PROPERTIES
# ============================================================

@entities_bp.route('/properties', methods=['GET'])
def get_properties():
    """List properties. Optional query param: client_id to filter by client."""
    client_id = request.args.get('client_id', type=int)
    q = Property.query
    if client_id:
        q = q.filter_by(client_id=client_id)
    props = q.order_by(Property.id.desc()).all()
    return jsonify([p.to_dict() for p in props]), 200


@entities_bp.route('/properties/<int:prop_id>', methods=['GET'])
def get_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    return jsonify(p.to_dict()), 200


@entities_bp.route('/properties', methods=['POST'])
def create_property():
    data = request.get_json() or {}

    client_id = data.get('client_id')
    name = (data.get('name') or '').strip()
    city_state = (data.get('city_state') or '').strip() or None
    area_ha = data.get('area_ha')
    latitude = _parse_optional_float(data.get('latitude'))
    longitude = _parse_optional_float(data.get('longitude'))

    if not client_id or not name:
        return jsonify(message='client_id and name are required'), 400

    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404

    try:
        prop = Property(
            client_id=int(client_id),
            name=name,
            city_state=city_state,
            area_ha=(float(area_ha) if area_ha not in (None, "") else None),
            latitude=latitude,
            longitude=longitude,
        )
        db.session.add(prop)
        db.session.commit()
        return jsonify(message='property created', property=prop.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500


@entities_bp.route('/properties/<int:prop_id>', methods=['PUT'])
def update_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404

    data = request.get_json() or {}

    if 'client_id' in data and data.get('client_id') not in (None, ""):
        if not Client.query.get(data.get('client_id')):
            return jsonify(message='client not found'), 404
        p.client_id = int(data.get('client_id'))

    if 'name' in data:
        p.name = (data.get('name') or '').strip()

    if 'city_state' in data:
        p.city_state = (data.get('city_state') or '').strip() or None

    if 'area_ha' in data:
        p.area_ha = float(data.get('area_ha')) if data.get('area_ha') not in (None, "") else None

    if 'latitude' in data:
        p.latitude = _parse_optional_float(data.get('latitude'))

    if 'longitude' in data:
        p.longitude = _parse_optional_float(data.get('longitude'))

    try:
        db.session.commit()
        return jsonify(message='property updated', property=p.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500


@entities_bp.route('/properties/<int:prop_id>', methods=['DELETE'])
def delete_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='property deleted'), 200


# ============================================================
# PLOTS
# ============================================================

@entities_bp.route('/plots', methods=['GET'])
def get_plots():
    try:
        property_id = request.args.get('property_id', type=int)
        client_id = request.args.get('client_id', type=int)
        q = Plot.query
        if property_id:
            q = q.filter_by(property_id=property_id)
        if client_id:
            q = q.join(Property).filter(Property.client_id == client_id)
        plots = q.order_by(Plot.id.desc()).all()
        return jsonify([pl.to_dict() for pl in plots]), 200
    except Exception as e:
        print(f"Erro em /plots: {e}")
        return jsonify(error=str(e)), 500


@entities_bp.route('/plots/<int:plot_id>', methods=['GET'])
def get_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    return jsonify(pl.to_dict()), 200


@entities_bp.route('/plots', methods=['POST'])
def create_plot():
    data = request.get_json() or {}
    property_id = data.get('property_id')
    name = data.get('name')
    if not property_id or not name:
        return jsonify(message='property_id and name are required'), 400
    prop = Property.query.get(property_id)
    if not prop:
        return jsonify(message='property not found'), 404

    irrigated = data.get('irrigated')
    if irrigated is not None:
        if isinstance(irrigated, str):
            irrigated = irrigated.lower() in ('1', 'true', 'yes', 'sim')
        else:
            irrigated = bool(irrigated)

    pl = Plot(
        property_id=property_id,
        name=name,
        area_ha=(float(data.get('area_ha')) if data.get('area_ha') is not None else None),
        irrigated=irrigated,
    )
    db.session.add(pl)
    db.session.commit()
    return jsonify(message='plot created', plot=pl.to_dict()), 201


@entities_bp.route('/plots/<int:plot_id>', methods=['PUT'])
def update_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    data = request.get_json() or {}

    for field in ('name', 'area_ha', 'irrigated', 'property_id', 'latitude', 'longitude'):
        if field in data:
            if field == 'area_ha':
                setattr(pl, field, float(data.get(field)) if data.get(field) is not None else None)
            elif field == 'irrigated':
                v = data.get(field)
                if isinstance(v, str):
                    v = v.lower() in ('1', 'true', 'yes', 'sim')
                else:
                    v = bool(v)
                setattr(pl, field, v)
            else:
                setattr(pl, field, data.get(field))

    if 'property_id' in data and data.get('property_id') is not None:
        if not Property.query.get(data.get('property_id')):
            return jsonify(message='property not found'), 404

    db.session.commit()
    return jsonify(message='plot updated', plot=pl.to_dict()), 200


@entities_bp.route('/plots/<int:plot_id>', methods=['DELETE'])
def delete_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    db.session.delete(pl)
    db.session.commit()
    return jsonify(message='plot deleted'), 200


# ============================================================
# PLANTINGS
# ============================================================

@entities_bp.route('/plantings', methods=['GET'])
def get_plantings():
    """List plantings. Optional filters: plot_id, property_id, client_id"""
    plot_id = request.args.get('plot_id', type=int)
    property_id = request.args.get('property_id', type=int)
    client_id = request.args.get('client_id', type=int)

    q = Planting.query
    if plot_id:
        q = q.filter_by(plot_id=plot_id)
    if property_id:
        q = q.join(Plot).filter(Plot.property_id == property_id)
    if client_id:
        q = q.join(Plot).join(Property).filter(Property.client_id == client_id)

    items = q.order_by(Planting.id.desc()).all()
    return jsonify([it.to_dict() for it in items]), 200


@entities_bp.route('/plantings/<int:pid>', methods=['GET'])
def get_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    return jsonify(p.to_dict()), 200


@entities_bp.route('/plantings', methods=['POST'])
def create_planting():
    data = request.get_json() or {}
    plot_id = data.get('plot_id')
    if not plot_id:
        return jsonify(message='plot_id is required'), 400

    plot = Plot.query.get(plot_id)
    if not plot:
        return jsonify(message='plot not found'), 404

    culture = data.get('culture')
    variety = data.get('variety')

    planting_date = None
    if data.get('planting_date'):
        try:
            planting_date = datetime.fromisoformat(data.get('planting_date')).date()
        except Exception:
            return jsonify(message='invalid planting_date, expected YYYY-MM-DD'), 400

    p = Planting(
        plot_id=plot_id,
        culture=culture,
        variety=variety,
        planting_date=planting_date,
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(message='planting created', planting=p.to_dict()), 201


@entities_bp.route('/plantings/<int:pid>', methods=['PUT'])
def update_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    data = request.get_json() or {}

    for field in ('culture', 'variety'):
        if field in data:
            setattr(p, field, data.get(field))

    if 'planting_date' in data:
        pd_raw = data.get('planting_date')
        if pd_raw:
            try:
                p.planting_date = datetime.fromisoformat(pd_raw).date()
            except Exception:
                return jsonify(message='invalid planting_date'), 400
        else:
            p.planting_date = None

    db.session.commit()
    return jsonify(message='planting updated', planting=p.to_dict()), 200


@entities_bp.route('/plantings/<int:pid>', methods=['DELETE'])
def delete_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='planting deleted'), 200
