from difflib import SequenceMatcher

from models import db, Client, Property, Plot, FieldData


FIELD_DATA_CATEGORIES = {
    "manejo_fungicida": "manejo_fungicida",
    "manejo_inseticida": "manejo_inseticida",
    "manejo_herbicida": "manejo_herbicida",
    "manejo_adubacao": "manejo_adubacao",
    "comportamento_hibrido": "comportamento_hibrido",
    "pendoamento": "pendoamento",
    "sanidade": "sanidade",
    "perfil_tecnico_cliente": "perfil_tecnico_cliente",
    "perfil_comercial_cliente": "perfil_comercial_cliente",
    "geral": "geral",
}


def normalize_lookup_text(value: str) -> str:
    import re
    import unicodedata

    if not value:
        return ""
    value = unicodedata.normalize("NFD", value.strip().lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def infer_field_data_category(raw_text: str) -> str:
    text = normalize_lookup_text(raw_text)

    if "fungicida" in text:
        return "manejo_fungicida"
    if "inseticida" in text:
        return "manejo_inseticida"
    if "herbicida" in text:
        return "manejo_herbicida"
    if "adub" in text:
        return "manejo_adubacao"
    if "pendoamento" in text:
        return "pendoamento"
    if "sanidade" in text:
        return "sanidade"
    if "perfil comercial" in text or "preco" in text or "preço" in text:
        return "perfil_comercial_cliente"
    if "perfil tecnico" in text or "perfil técnico" in text:
        return "perfil_tecnico_cliente"
    if "hibrido" in text or "híbrido" in text or "variedade" in text:
        return "comportamento_hibrido"

    return "geral"


def find_best_client_by_name(client_name: str):
    if not client_name:
        return None

    target = normalize_lookup_text(client_name)
    clients = Client.query.all()

    best_client = None
    best_score = 0.0

    for client in clients:
        current = normalize_lookup_text(client.name)
        score = SequenceMatcher(None, target, current).ratio()
        if target and (target in current or current in target):
            score = max(score, 0.93)
        if score > best_score:
            best_score = score
            best_client = client

    if best_client and best_score >= 0.72:
        return best_client

    return None


def find_best_property_by_name(property_name: str, client_id: int | None = None):
    if not property_name:
        return None

    target = normalize_lookup_text(property_name)
    query = Property.query
    if client_id:
        query = query.filter_by(client_id=client_id)

    items = query.all()
    best = None
    best_score = 0.0

    for item in items:
        current = normalize_lookup_text(item.name)
        score = SequenceMatcher(None, target, current).ratio()
        if target and (target in current or current in target):
            score = max(score, 0.93)
        if score > best_score:
            best_score = score
            best = item

    if best and best_score >= 0.72:
        return best

    return None


def find_best_plot_by_name(plot_name: str, property_id: int | None = None):
    if not plot_name:
        return None

    target = normalize_lookup_text(plot_name)
    query = Plot.query
    if property_id:
        query = query.filter_by(property_id=property_id)

    items = query.all()
    best = None
    best_score = 0.0

    for item in items:
        current = normalize_lookup_text(item.name)
        score = SequenceMatcher(None, target, current).ratio()
        if target and (target in current or current in target):
            score = max(score, 0.93)
        if score > best_score:
            best_score = score
            best = item

    if best and best_score >= 0.72:
        return best

    return None


def create_field_data_record(
    consultant_id: int | None,
    client_id: int,
    content: str,
    category: str = "geral",
    property_id: int | None = None,
    plot_id: int | None = None,
    culture: str | None = None,
    variety: str | None = None,
    title: str | None = None,
    category_extra: str | None = None,
    source: str = "bot",
):
    row = FieldData(
        consultant_id=consultant_id,
        client_id=client_id,
        property_id=property_id,
        plot_id=plot_id,
        culture=(culture or "").strip() or None,
        variety=(variety or "").strip() or None,
        category=(category or "geral").strip(),
        category_extra=(category_extra or "").strip() or None,
        title=(title or "").strip() or None,
        content=(content or "").strip(),
        source=source,
    )
    db.session.add(row)
    db.session.commit()
    return row


def search_field_data(
    consultant_id: int | None = None,
    client_id: int | None = None,
    property_id: int | None = None,
    plot_id: int | None = None,
    culture: str | None = None,
    variety: str | None = None,
    category: str | None = None,
    limit: int = 10,
):
    q = FieldData.query

    if consultant_id:
        q = q.filter(FieldData.consultant_id == consultant_id)
    if client_id:
        q = q.filter(FieldData.client_id == client_id)
    if property_id:
        q = q.filter(FieldData.property_id == property_id)
    if plot_id:
        q = q.filter(FieldData.plot_id == plot_id)
    if culture:
        q = q.filter(FieldData.culture == culture)
    if variety:
        q = q.filter(FieldData.variety == variety)
    if category:
        q = q.filter(FieldData.category == category)

    return (
        q.order_by(FieldData.created_at.desc(), FieldData.id.desc())
         .limit(limit)
         .all()
    )


def build_field_data_summary_text(rows: list[FieldData]) -> str:
    if not rows:
        return "Não encontrei dados de campo para esse filtro."

    lines = ["🧠 Dados do campo encontrados:", ""]

    for idx, row in enumerate(rows, start=1):
        client_name = row.client.name if row.client else f"Cliente {row.client_id}"
        property_name = row.property.name if row.property else ""
        plot_name = row.plot.name if row.plot else ""
        variety = row.variety or ""
        category = row.category or "geral"

        context_parts = [client_name]
        if property_name:
            context_parts.append(f"Faz. {property_name}")
        if plot_name:
            context_parts.append(f"Talhão {plot_name}")
        if variety:
            context_parts.append(variety)

        context_line = " - ".join(context_parts)
        lines.append(f"{idx}. [{category}] {context_line}")
        lines.append(f"   {row.content}")

    return "\n".join(lines)