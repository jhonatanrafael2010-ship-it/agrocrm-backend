"""
================================================================
ProactiveInsights Service
================================================================

Gera insights e lembretes proativos para consultores:
- Visitas pendentes do dia
- Clientes sem visita há muito tempo
- Resumo de atividades

Usado por:
- API do app/site (polling ou on-load)
- Cron de notificações Telegram
================================================================
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from models import Visit, Client, Consultant, TelegramContactBinding, db


def get_consultant_insights(consultant_id: int) -> Dict[str, Any]:
    """
    Retorna todos os insights proativos para um consultor.
    Chamado pelo app/site ao carregar ou por polling.
    """
    today = date.today()

    insights = {
        "consultant_id": consultant_id,
        "date": today.isoformat(),
        "pending_today": get_pending_visits_today(consultant_id),
        "stale_clients": get_stale_clients(consultant_id),
        "week_summary": get_week_summary(consultant_id),
        "alerts": [],
    }

    # Gera alertas baseados nos insights
    alerts = []

    pending_count = len(insights["pending_today"])
    if pending_count > 0:
        alerts.append({
            "type": "pending_visits",
            "priority": "high" if pending_count >= 3 else "medium",
            "message": f"Você tem {pending_count} visita(s) pendente(s) para hoje",
            "count": pending_count,
        })

    stale_count = len(insights["stale_clients"])
    if stale_count > 0:
        most_stale = insights["stale_clients"][0] if insights["stale_clients"] else None
        if most_stale and most_stale.get("days_since_visit", 0) > 30:
            alerts.append({
                "type": "stale_client",
                "priority": "high",
                "message": f"Cliente {most_stale['name']} não é visitado há {most_stale['days_since_visit']} dias",
                "client_id": most_stale.get("id"),
                "client_name": most_stale.get("name"),
                "days": most_stale.get("days_since_visit"),
            })
        elif stale_count >= 3:
            alerts.append({
                "type": "stale_clients",
                "priority": "medium",
                "message": f"{stale_count} clientes sem visita há mais de 15 dias",
                "count": stale_count,
            })

    insights["alerts"] = alerts
    return insights


def get_pending_visits_today(consultant_id: int) -> List[Dict[str, Any]]:
    """Retorna visitas planejadas para hoje."""
    today = date.today()

    visits = Visit.query.filter(
        Visit.consultant_id == consultant_id,
        Visit.date == today,
        Visit.status == "planned",
    ).all()

    result = []
    for v in visits:
        client = Client.query.get(v.client_id) if v.client_id else None
        result.append({
            "id": v.id,
            "client_id": v.client_id,
            "client_name": client.name if client else "—",
            "culture": v.culture,
            "fenologia": v.fenologia_real,
            "property_id": v.property_id,
        })

    return result


def get_stale_clients(consultant_id: int, days_threshold: int = 15, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna clientes que não são visitados há mais de X dias.
    Ordenados pelo mais atrasado primeiro.
    """
    today = date.today()
    threshold_date = today - timedelta(days=days_threshold)

    # Subconsulta: última visita por cliente do consultor
    subq = db.session.query(
        Visit.client_id,
        db.func.max(Visit.date).label("last_visit_date")
    ).filter(
        Visit.consultant_id == consultant_id,
        Visit.status == "done",
        Visit.client_id.isnot(None),
    ).group_by(Visit.client_id).subquery()

    # Clientes com última visita anterior ao threshold
    results = db.session.query(
        Client.id,
        Client.name,
        subq.c.last_visit_date
    ).join(
        subq, Client.id == subq.c.client_id
    ).filter(
        subq.c.last_visit_date < threshold_date
    ).order_by(
        subq.c.last_visit_date.asc()
    ).limit(limit).all()

    stale = []
    for client_id, name, last_visit in results:
        days_since = (today - last_visit).days if last_visit else 999
        stale.append({
            "id": client_id,
            "name": name,
            "last_visit_date": last_visit.isoformat() if last_visit else None,
            "days_since_visit": days_since,
        })

    return stale


def get_week_summary(consultant_id: int) -> Dict[str, Any]:
    """Resumo rápido da semana atual."""
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    # Visitas realizadas esta semana
    done_visits = Visit.query.filter(
        Visit.consultant_id == consultant_id,
        Visit.date >= start_of_week,
        Visit.date <= today,
        Visit.status == "done",
    ).count()

    # Visitas planejadas restantes da semana
    end_of_week = start_of_week + timedelta(days=6)
    planned_visits = Visit.query.filter(
        Visit.consultant_id == consultant_id,
        Visit.date > today,
        Visit.date <= end_of_week,
        Visit.status == "planned",
    ).count()

    return {
        "done_this_week": done_visits,
        "planned_remaining": planned_visits,
        "week_start": start_of_week.isoformat(),
        "week_end": end_of_week.isoformat(),
    }


def build_daily_reminder_text(consultant_id: int, consultant_name: str) -> Optional[str]:
    """
    Gera texto do lembrete diário para Telegram.
    Retorna None se não houver nada relevante para notificar.
    """
    insights = get_consultant_insights(consultant_id)

    lines = []
    lines.append(f"🌅 Bom dia, {consultant_name}!")
    lines.append("")

    # Visitas do dia
    pending = insights.get("pending_today", [])
    if pending:
        lines.append(f"📋 Você tem {len(pending)} visita(s) para hoje:")
        for i, v in enumerate(pending[:5], 1):
            culture_info = f" - {v['culture']}" if v.get('culture') else ""
            lines.append(f"   {i}. {v['client_name']}{culture_info}")
        if len(pending) > 5:
            lines.append(f"   ... e mais {len(pending) - 5}")
        lines.append("")

    # Clientes atrasados (só os críticos)
    stale = insights.get("stale_clients", [])
    critical_stale = [s for s in stale if s.get("days_since_visit", 0) > 30]
    if critical_stale:
        lines.append("⚠️ Atenção:")
        for s in critical_stale[:3]:
            lines.append(f"   • {s['name']} sem visita há {s['days_since_visit']} dias")
        lines.append("")

    # Se não tem nada relevante, não envia
    if not pending and not critical_stale:
        return None

    # Resumo da semana
    summary = insights.get("week_summary", {})
    done = summary.get("done_this_week", 0)
    planned = summary.get("planned_remaining", 0)
    if done > 0 or planned > 0:
        lines.append(f"📊 Semana: {done} realizadas | {planned} planejadas")

    return "\n".join(lines)


def get_all_consultants_for_daily_reminder() -> List[Dict[str, Any]]:
    """
    Retorna lista de consultores com Telegram vinculado
    para envio de lembretes diários.
    """
    bindings = TelegramContactBinding.query.filter_by(is_active=True).all()

    consultants = []
    for b in bindings:
        consultant = Consultant.query.get(b.consultant_id)
        if consultant:
            consultants.append({
                "consultant_id": consultant.id,
                "consultant_name": consultant.name,
                "telegram_chat_id": b.telegram_chat_id,
            })

    return consultants
