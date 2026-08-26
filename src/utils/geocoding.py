# utils/geocoding.py
"""
Geocodificação reversa para obter município a partir de coordenadas.
Usa a API Nominatim do OpenStreetMap (gratuita, sem API key).
"""

import requests
from typing import Optional, Tuple


def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """
    Obtém o município (cidade) e estado a partir de coordenadas.
    Retorna string no formato "Cidade - UF" ou None se falhar.
    """
    if lat is None or lng is None:
        return None

    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lng,
            "format": "json",
            "addressdetails": 1,
            "accept-language": "pt-BR",
        }
        headers = {
            "User-Agent": "AgroCRM/1.0 (contact@agrocrm.com)"
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        address = data.get("address", {})

        # Nominatim pode retornar cidade em diferentes campos dependendo do tamanho
        city = (
            address.get("city") or
            address.get("town") or
            address.get("municipality") or
            address.get("village") or
            address.get("county")
        )

        state = address.get("state")

        if not city:
            return None

        # Mapear nome do estado para sigla
        state_abbrev = _get_state_abbrev(state) if state else ""

        if state_abbrev:
            return f"{city} - {state_abbrev}"
        return city

    except Exception as e:
        print(f"Erro na geocodificação reversa: {e}")
        return None


def _get_state_abbrev(state_name: str) -> str:
    """Converte nome do estado brasileiro para sigla."""
    states = {
        "Acre": "AC",
        "Alagoas": "AL",
        "Amapá": "AP",
        "Amazonas": "AM",
        "Bahia": "BA",
        "Ceará": "CE",
        "Distrito Federal": "DF",
        "Espírito Santo": "ES",
        "Goiás": "GO",
        "Maranhão": "MA",
        "Mato Grosso": "MT",
        "Mato Grosso do Sul": "MS",
        "Minas Gerais": "MG",
        "Pará": "PA",
        "Paraíba": "PB",
        "Paraná": "PR",
        "Pernambuco": "PE",
        "Piauí": "PI",
        "Rio de Janeiro": "RJ",
        "Rio Grande do Norte": "RN",
        "Rio Grande do Sul": "RS",
        "Rondônia": "RO",
        "Roraima": "RR",
        "Santa Catarina": "SC",
        "São Paulo": "SP",
        "Sergipe": "SE",
        "Tocantins": "TO",
    }
    return states.get(state_name, "")


def update_property_city_state(prop) -> bool:
    """
    Atualiza o city_state de uma propriedade se ela tiver coordenadas
    e o city_state estiver vazio ou incompleto (só sigla de estado).
    Retorna True se atualizou, False caso contrário.
    """
    if not prop.latitude or not prop.longitude:
        return False

    current = (prop.city_state or "").strip()

    # Se já tem cidade válida (não apenas sigla de estado), não atualiza
    if current and len(current) > 2 and not _is_only_state_abbrev(current):
        return False

    city_state = reverse_geocode(prop.latitude, prop.longitude)
    if city_state:
        prop.city_state = city_state
        return True

    return False


def _is_only_state_abbrev(value: str) -> bool:
    """Verifica se o valor é apenas uma sigla de estado."""
    import re
    return bool(re.match(r'^[A-Z]{2}$', value.strip(), re.IGNORECASE))
