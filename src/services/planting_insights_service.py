from datetime import date as _date
from models import Planting, Visit, Client


def get_local_today():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Cuiaba")).date()


def resolve_planting_date_for_context(
    client_id: int | None = None,
    property_id: int | None = None,
    plot_id: int | None = None,
    culture: str | None = None,
    variety: str | None = None,
):
    q = Planting.query

    if plot_id:
        q = q.filter(Planting.plot_id == plot_id)

    if culture:
        q = q.filter(Planting.culture == culture)

    if variety:
        q = q.filter(Planting.variety == variety)

    planting = q.order_by(Planting.planting_date.desc().nullslast(), Planting.id.desc()).first()
    if planting and planting.planting_date:
        return planting.planting_date, planting

    vq = Visit.query.filter(Visit.client_id == client_id)

    if property_id is not None:
        vq = vq.filter(Visit.property_id == property_id)
    if plot_id is not None:
        vq = vq.filter(Visit.plot_id == plot_id)
    if culture:
        vq = vq.filter(Visit.culture == culture)
    if variety:
        vq = vq.filter(Visit.variety == variety)

    vq = vq.filter(Visit.fenologia_real == "Plantio")

    visit = vq.order_by(Visit.date.asc().nullslast(), Visit.id.asc()).first()
    if visit and visit.date:
        return visit.date, None

    return None, None


def calculate_days_since_planting(
    client_id: int | None = None,
    property_id: int | None = None,
    plot_id: int | None = None,
    culture: str | None = None,
    variety: str | None = None,
):
    planting_date, planting = resolve_planting_date_for_context(
        client_id=client_id,
        property_id=property_id,
        plot_id=plot_id,
        culture=culture,
        variety=variety,
    )

    if not planting_date:
        return None

    days = (get_local_today() - planting_date).days
    if days < 0:
        days = 0

    return {
        "planting_date": planting_date.isoformat(),
        "days": days,
        "planting_id": planting.id if planting else None,
    }


def build_days_planted_text(client_name: str, variety: str, result: dict | None) -> str:
    if not result:
        return f"Não encontrei data de plantio para {client_name}{' - ' + variety if variety else ''}."

    return (
        f"🌱 Dias de plantado\n"
        f"Cliente: {client_name}\n"
        f"Variedade: {variety or '—'}\n"
        f"Data do plantio: {result['planting_date']}\n"
        f"Dias de plantado: {result['days']}"
    )