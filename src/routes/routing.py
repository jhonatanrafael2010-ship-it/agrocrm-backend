# routes/routing.py
"""
Serviço de roteirização usando Google Directions API.
- /routing/calculate - Calcula rota otimizada entre pontos
"""

import os
import requests
from flask import Blueprint, jsonify, request

routing_bp = Blueprint('routing', __name__)

GOOGLE_API_KEY = os.environ.get('GOOGLE_DIRECTIONS_API_KEY', '')


@routing_bp.route('/routing/calculate', methods=['POST'])
def calculate_route():
    """
    Calcula rota otimizada entre origem e múltiplos destinos.

    Body JSON:
    {
        "origin": {"lat": -15.123, "lng": -56.456},
        "destinations": [
            {"id": 1, "name": "Cliente A", "lat": -15.200, "lng": -56.500},
            {"id": 2, "name": "Cliente B", "lat": -15.300, "lng": -56.600},
        ],
        "return_to_origin": true  // opcional, se deve voltar ao ponto inicial
    }

    Retorna:
    {
        "success": true,
        "route": {
            "total_distance_km": 150.5,
            "total_duration_min": 180,
            "optimized_order": [2, 1],  // IDs na ordem otimizada
            "legs": [
                {
                    "from": "Origem",
                    "to": "Cliente B",
                    "distance_km": 50.2,
                    "duration_min": 60,
                },
                ...
            ],
            "polyline": "encoded_polyline_string",  // para desenhar no mapa
            "waypoints_order": [1, 0]  // índice original reordenado
        }
    }
    """
    if not GOOGLE_API_KEY:
        return jsonify(success=False, error='API key não configurada'), 500

    data = request.get_json() or {}

    origin = data.get('origin')
    destinations = data.get('destinations', [])
    return_to_origin = data.get('return_to_origin', False)
    via_points = data.get('via_points', [])  # Pontos de passagem (não são paradas)

    if not origin or not origin.get('lat') or not origin.get('lng'):
        return jsonify(success=False, error='Origem é obrigatória'), 400

    if not destinations or len(destinations) == 0:
        return jsonify(success=False, error='Pelo menos um destino é necessário'), 400

    if len(destinations) > 25:
        return jsonify(success=False, error='Máximo de 25 destinos por rota'), 400

    # Formata origem
    origin_str = f"{origin['lat']},{origin['lng']}"

    # Formata via_points com prefixo "via:" (passagem sem parada)
    via_points_str = [f"via:{vp['lat']},{vp['lng']}" for vp in via_points]

    # Se só tem 1 destino, não precisa otimizar
    if len(destinations) == 1:
        dest = destinations[0]
        dest_str = f"{dest['lat']},{dest['lng']}"

        params = {
            'origin': origin_str,
            'destination': dest_str,
            'mode': 'driving',
            'language': 'pt-BR',
            'key': GOOGLE_API_KEY,
        }

        if return_to_origin:
            params['destination'] = origin_str
            all_waypoints = [dest_str] + via_points_str
            params['waypoints'] = '|'.join(all_waypoints)
        elif via_points_str:
            params['waypoints'] = '|'.join(via_points_str)
    else:
        # Múltiplos destinos - usar waypoints com otimização
        waypoints = [f"{d['lat']},{d['lng']}" for d in destinations]

        # O último destino é o destino final (ou origem se return_to_origin)
        if return_to_origin:
            dest_str = origin_str
            # Via points não são otimizados, vão no final
            all_waypoints = waypoints + via_points_str
            waypoints_str = f"optimize:true|{'|'.join(all_waypoints)}"
        else:
            dest_str = waypoints.pop()  # último ponto é o destino
            if waypoints or via_points_str:
                all_waypoints = waypoints + via_points_str
                waypoints_str = f"optimize:true|{'|'.join(all_waypoints)}"
            else:
                waypoints_str = None

        params = {
            'origin': origin_str,
            'destination': dest_str,
            'mode': 'driving',
            'language': 'pt-BR',
            'key': GOOGLE_API_KEY,
        }

        if return_to_origin or len(destinations) > 1:
            # Todos os destinos são waypoints quando volta à origem
            if return_to_origin:
                waypoints = [f"{d['lat']},{d['lng']}" for d in destinations]
                waypoints_str = f"optimize:true|{'|'.join(waypoints)}"
            params['waypoints'] = waypoints_str

    try:
        response = requests.get(
            'https://maps.googleapis.com/maps/api/directions/json',
            params=params,
            timeout=30
        )
        result = response.json()

        if result.get('status') != 'OK':
            error_msg = result.get('error_message', result.get('status', 'Erro desconhecido'))
            return jsonify(success=False, error=f'Google API: {error_msg}'), 400

        # Processa resultado
        route = result['routes'][0]
        legs = route['legs']

        # Calcula totais
        total_distance_m = sum(leg['distance']['value'] for leg in legs)
        total_duration_s = sum(leg['duration']['value'] for leg in legs)

        # Ordem otimizada dos waypoints (se houver)
        waypoint_order = result.get('routes', [{}])[0].get('waypoint_order', [])

        # Monta ordem otimizada dos IDs
        optimized_order = []
        if waypoint_order and destinations:
            for idx in waypoint_order:
                if idx < len(destinations):
                    optimized_order.append(destinations[idx]['id'])
            # Se não volta à origem, adiciona o último destino
            if not return_to_origin and len(destinations) > 1:
                optimized_order.append(destinations[-1]['id'])
        elif len(destinations) == 1:
            optimized_order = [destinations[0]['id']]
        else:
            optimized_order = [d['id'] for d in destinations]

        # Monta legs detalhadas
        legs_detail = []
        dest_names = {d['id']: d.get('name', f"Ponto {d['id']}") for d in destinations}

        for i, leg in enumerate(legs):
            if i == 0:
                from_name = origin.get('name', 'Origem')
            else:
                # Pega o nome do destino anterior
                if waypoint_order and i - 1 < len(waypoint_order):
                    prev_idx = waypoint_order[i - 1]
                    from_name = destinations[prev_idx].get('name', f"Ponto {prev_idx + 1}")
                else:
                    from_name = f"Ponto {i}"

            if i == len(legs) - 1 and return_to_origin:
                to_name = origin.get('name', 'Origem')
            elif waypoint_order and i < len(waypoint_order):
                to_idx = waypoint_order[i]
                to_name = destinations[to_idx].get('name', f"Ponto {to_idx + 1}")
            elif i < len(destinations):
                to_name = destinations[i].get('name', f"Ponto {i + 1}")
            else:
                to_name = origin.get('name', 'Origem') if return_to_origin else "Destino"

            legs_detail.append({
                'from': from_name,
                'to': to_name,
                'distance_km': round(leg['distance']['value'] / 1000, 1),
                'duration_min': round(leg['duration']['value'] / 60),
                'start_address': leg.get('start_address', ''),
                'end_address': leg.get('end_address', ''),
            })

        # Decodifica TODAS as polylines detalhadas de cada step (como o Google Maps faz)
        all_coords = []
        for leg in legs:
            for step in leg.get('steps', []):
                step_polyline = step.get('polyline', {}).get('points', '')
                if step_polyline:
                    step_coords = decode_polyline(step_polyline)
                    all_coords.extend(step_coords)

        # Se não tiver steps, usa overview como fallback
        if not all_coords:
            overview_polyline = route.get('overview_polyline', {}).get('points', '')
            all_coords = decode_polyline(overview_polyline)

        decoded_coords = all_coords

        return jsonify(
            success=True,
            route={
                'total_distance_km': round(total_distance_m / 1000, 1),
                'total_duration_min': round(total_duration_s / 60),
                'total_duration_formatted': format_duration(total_duration_s),
                'optimized_order': optimized_order,
                'waypoints_order': waypoint_order,
                'legs': legs_detail,
                'coordinates': decoded_coords,
            }
        ), 200

    except requests.Timeout:
        return jsonify(success=False, error='Timeout ao calcular rota'), 504
    except requests.RequestException as e:
        return jsonify(success=False, error=f'Erro de conexão: {str(e)}'), 500
    except Exception as e:
        return jsonify(success=False, error=f'Erro interno: {str(e)}'), 500


def format_duration(seconds: int) -> str:
    """Formata duração em formato legível."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def decode_polyline(encoded: str) -> list:
    """Decodifica polyline encoded do Google para lista de [lat, lng]."""
    if not encoded:
        return []

    points = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        # Decodifica latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        # Decodifica longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        points.append([lat / 1e5, lng / 1e5])

    return points


@routing_bp.route('/routing/test', methods=['GET'])
def test_api():
    """Testa se a API key está configurada."""
    if not GOOGLE_API_KEY:
        return jsonify(configured=False, message='GOOGLE_DIRECTIONS_API_KEY não configurada'), 200

    # Testa com uma requisição simples
    try:
        params = {
            'origin': '-15.5989,-56.0949',  # Cuiabá
            'destination': '-15.6014,-56.0979',
            'mode': 'driving',
            'key': GOOGLE_API_KEY,
        }
        response = requests.get(
            'https://maps.googleapis.com/maps/api/directions/json',
            params=params,
            timeout=10
        )
        result = response.json()

        if result.get('status') == 'OK':
            return jsonify(configured=True, status='OK', message='API funcionando'), 200
        else:
            return jsonify(
                configured=True,
                status=result.get('status'),
                message=result.get('error_message', 'Erro na API')
            ), 200

    except Exception as e:
        return jsonify(configured=True, status='ERROR', message=str(e)), 200
