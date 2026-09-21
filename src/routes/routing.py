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
    Via points são usados DEPOIS da otimização para ajustar o trajeto.

    Body JSON:
    {
        "origin": {"lat": -15.123, "lng": -56.456, "name": "Minha Casa"},
        "destinations": [
            {"id": 1, "name": "Cliente A", "lat": -15.200, "lng": -56.500},
            {"id": 2, "name": "Cliente B", "lat": -15.300, "lng": -56.600},
        ],
        "return_to_origin": true,
        "via_points": [
            {"lat": -15.250, "lng": -56.550, "name": "Via Point 1"}
        ]
    }
    """
    if not GOOGLE_API_KEY:
        return jsonify(success=False, error='API key não configurada'), 500

    data = request.get_json() or {}

    origin = data.get('origin')
    destinations = data.get('destinations', [])
    return_to_origin = data.get('return_to_origin', False)
    via_points = data.get('via_points', [])

    if not origin or not origin.get('lat') or not origin.get('lng'):
        return jsonify(success=False, error='Origem é obrigatória'), 400

    if not destinations or len(destinations) == 0:
        return jsonify(success=False, error='Pelo menos um destino é necessário'), 400

    if len(destinations) > 25:
        return jsonify(success=False, error='Máximo de 25 destinos por rota'), 400

    origin_str = f"{origin['lat']},{origin['lng']}"

    try:
        # ============================================================
        # PASSO 1: Calcular ordem otimizada (sem via_points)
        # ============================================================
        waypoint_order = []

        if len(destinations) == 1:
            # Só 1 destino - não precisa otimizar
            waypoint_order = [0]
            dest_str = f"{destinations[0]['lat']},{destinations[0]['lng']}"
            if return_to_origin:
                dest_str = origin_str
                first_waypoints = [f"{destinations[0]['lat']},{destinations[0]['lng']}"]
            else:
                first_waypoints = []
        else:
            # Múltiplos destinos - otimiza primeiro
            all_dest_strs = [f"{d['lat']},{d['lng']}" for d in destinations]

            if return_to_origin:
                dest_str = origin_str
                first_waypoints = all_dest_strs
            else:
                dest_str = all_dest_strs[-1]
                first_waypoints = all_dest_strs[:-1]

            if first_waypoints:
                # Primeira chamada para obter ordem otimizada
                opt_params = {
                    'origin': origin_str,
                    'destination': dest_str,
                    'waypoints': f"optimize:true|{'|'.join(first_waypoints)}",
                    'mode': 'driving',
                    'language': 'pt-BR',
                    'key': GOOGLE_API_KEY,
                }

                opt_response = requests.get(
                    'https://maps.googleapis.com/maps/api/directions/json',
                    params=opt_params,
                    timeout=30
                )
                opt_result = opt_response.json()

                if opt_result.get('status') == 'OK':
                    waypoint_order = opt_result['routes'][0].get('waypoint_order', [])
                else:
                    # Se falhou a otimização, usa ordem original
                    waypoint_order = list(range(len(first_waypoints)))

        # ============================================================
        # PASSO 2: Calcular rota final COM via_points (sem otimizar)
        # ============================================================

        # Reordena destinos conforme otimização
        if waypoint_order and len(destinations) > 1:
            if return_to_origin:
                ordered_dests = [destinations[i] for i in waypoint_order]
            else:
                ordered_dests = [destinations[i] for i in waypoint_order] + [destinations[-1]]
        else:
            ordered_dests = destinations

        # Monta waypoints na ordem otimizada + via_points intercalados
        final_waypoints = []

        # Adiciona destinos na ordem otimizada
        for dest in ordered_dests:
            if return_to_origin or dest != ordered_dests[-1]:
                final_waypoints.append(f"{dest['lat']},{dest['lng']}")

        # Adiciona via_points com prefixo "via:" - eles forçam passagem sem parar
        # Os via_points são adicionados ao final, o Google vai intercalá-los no trajeto
        for vp in via_points:
            final_waypoints.append(f"via:{vp['lat']},{vp['lng']}")

        # Define destino final
        if return_to_origin:
            final_dest = origin_str
        else:
            final_dest = f"{ordered_dests[-1]['lat']},{ordered_dests[-1]['lng']}"

        # Monta requisição final (SEM optimize:true para preservar via_points)
        final_params = {
            'origin': origin_str,
            'destination': final_dest,
            'mode': 'driving',
            'language': 'pt-BR',
            'key': GOOGLE_API_KEY,
        }

        if final_waypoints:
            # NÃO usa optimize:true aqui para respeitar os via_points
            final_params['waypoints'] = '|'.join(final_waypoints)

        response = requests.get(
            'https://maps.googleapis.com/maps/api/directions/json',
            params=final_params,
            timeout=30
        )
        result = response.json()

        if result.get('status') != 'OK':
            error_msg = result.get('error_message', result.get('status', 'Erro desconhecido'))
            return jsonify(success=False, error=f'Google API: {error_msg}'), 400

        # ============================================================
        # PASSO 3: Processar resultado
        # ============================================================
        route = result['routes'][0]
        legs = route['legs']

        # Calcula totais - soma a distância de cada leg
        total_distance_m = 0
        total_duration_s = 0
        for idx, leg in enumerate(legs):
            leg_dist = leg['distance']['value']
            leg_dur = leg['duration']['value']
            total_distance_m += leg_dist
            total_duration_s += leg_dur
            print(f"[Routing] Leg {idx+1}: {leg_dist/1000:.1f} km, {leg_dur/60:.0f} min")

        # Monta ordem otimizada dos IDs
        optimized_order = [d['id'] for d in ordered_dests]

        # Monta legs detalhadas
        legs_detail = []

        leg_idx = 0
        for i, leg in enumerate(legs):
            # Nome da origem da leg
            if i == 0:
                from_name = origin.get('name', 'Origem')
            elif leg_idx > 0 and leg_idx <= len(ordered_dests):
                from_name = ordered_dests[leg_idx - 1].get('name', f"Ponto {leg_idx}")
            else:
                from_name = f"Via {i}"

            # Nome do destino da leg
            if i == len(legs) - 1:
                if return_to_origin:
                    to_name = origin.get('name', 'Origem')
                else:
                    to_name = ordered_dests[-1].get('name', 'Destino')
            elif leg_idx < len(ordered_dests):
                to_name = ordered_dests[leg_idx].get('name', f"Ponto {leg_idx + 1}")
                leg_idx += 1
            else:
                to_name = f"Via {i + 1}"

            legs_detail.append({
                'from': from_name,
                'to': to_name,
                'distance_km': round(leg['distance']['value'] / 1000, 1),
                'duration_min': round(leg['duration']['value'] / 60),
                'start_address': leg.get('start_address', ''),
                'end_address': leg.get('end_address', ''),
            })

        # Decodifica TODAS as polylines detalhadas de cada step
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

        total_km = round(total_distance_m / 1000, 1)
        print(f"[Routing] TOTAL: {total_km} km, {total_duration_s/60:.0f} min, {len(legs)} legs, {len(via_points)} via_points")

        return jsonify(
            success=True,
            route={
                'total_distance_km': total_km,
                'total_duration_min': round(total_duration_s / 60),
                'total_duration_formatted': format_duration(total_duration_s),
                'optimized_order': optimized_order,
                'waypoints_order': waypoint_order,
                'legs': legs_detail,
                'coordinates': all_coords,
                'via_points_count': len(via_points),
            }
        ), 200

    except requests.Timeout:
        return jsonify(success=False, error='Timeout ao calcular rota'), 504
    except requests.RequestException as e:
        return jsonify(success=False, error=f'Erro de conexão: {str(e)}'), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
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
