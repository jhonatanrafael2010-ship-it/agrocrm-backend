"""
================================================================
excel_report_service.py
================================================================

Geração do relatório XLSX gerencial do NutriCRM.

Esta versão substitui o endpoint /reports/monthly.xlsx que estava
inline no routes.py. Mantém a mesma rota e parâmetros, mas:

- 4 KPIs principais com numerador/denominador claros
- Visitas por consultor mostra NOME (não ID)
- Aba "Atraso" nova focada em clientes abaixo da meta
- Status traduzido para português
- Coluna "Tem foto?" e "Dias desde plantio" na aba Visitas
- Aba Produtos com contexto (cultura, fenologia, consultor)
- AutoFiltro habilitado em todas as tabelas
- Gráficos: barras por dia, pizza por cultura

USO no routes.py:

    from services.excel_report_service import generate_monthly_xlsx

    @bp.route("/reports/monthly.xlsx", methods=["GET"])
    def report_monthly_xlsx():
        return generate_monthly_xlsx(request)
================================================================
"""

from io import BytesIO
from datetime import date as _date, datetime
import datetime as _dt
from collections import Counter, defaultdict

from flask import jsonify, send_file
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule, CellIsRule


META_VISITAS_CLIENTE = 5


# ================================================================
# Estilos
# ================================================================
BRAND_DARK = "0F5132"
BRAND_GREEN = "14532D"
BRAND_LIGHT = "E8F5E9"

NEUTRAL_GREY_LIGHT = "F8FAFC"
NEUTRAL_GREY = "E5E7EB"
NEUTRAL_GREY_DARK = "111827"
TEXT_MUTED = "6B7280"

STATUS_DONE = "22C55E"
STATUS_PENDING = "F59E0B"
STATUS_CANCELED = "EF4444"


def _styles():
    return {
        "title_fill": PatternFill("solid", fgColor=BRAND_DARK),
        "title_font": Font(color="FFFFFF", bold=True, size=16),
        "header_fill": PatternFill("solid", fgColor=BRAND_GREEN),
        "header_font": Font(color="FFFFFF", bold=True, size=11),
        "kpi_label_fill": PatternFill("solid", fgColor=BRAND_GREEN),
        "kpi_value_fill": PatternFill("solid", fgColor=BRAND_DARK),
        "kpi_label_font": Font(color="FFFFFF", bold=True, size=11),
        "kpi_value_font": Font(color="FFFFFF", bold=True, size=20),
        "section_fill": PatternFill("solid", fgColor=NEUTRAL_GREY),
        "section_font": Font(bold=True, color=NEUTRAL_GREY_DARK, size=12),
        "subheader_fill": PatternFill("solid", fgColor=BRAND_LIGHT),
        "muted": Font(color=TEXT_MUTED, size=9),
        "bold": Font(bold=True),
        "row_font": Font(color=NEUTRAL_GREY_DARK),
        "zebra_fill": PatternFill("solid", fgColor=NEUTRAL_GREY_LIGHT),
        "center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "left": Alignment(horizontal="left", vertical="top", wrap_text=True),
        "border_thin": Border(
            left=Side(style="thin", color="1F3A33"),
            right=Side(style="thin", color="1F3A33"),
            top=Side(style="thin", color="1F3A33"),
            bottom=Side(style="thin", color="1F3A33"),
        ),
        "border_data": Border(bottom=Side(style="hair", color="16312B")),
    }


# ================================================================
# Helpers de data
# ================================================================
def _br_date(d):
    if not d:
        return ""
    if isinstance(d, str):
        try:
            return _date.fromisoformat(d[:10]).strftime("%d/%m/%Y")
        except Exception:
            return d[:10]
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _translate_status(status):
    mapping = {
        "done": "Concluída",
        "concluida": "Concluída",
        "concluído": "Concluída",
        "planned": "Planejada",
        "planejada": "Planejada",
        "pendente": "Pendente",
        "canceled": "Cancelada",
        "cancelado": "Cancelada",
    }
    return mapping.get((status or "").lower(), status or "—")


def _has_valid_photo(visit):
    photos = getattr(visit, "photos", []) or []
    return any(getattr(p, "url", None) for p in photos)


def _truncate(text, limit=200):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


# ================================================================
# Função principal
# ================================================================
def generate_monthly_xlsx(request):
    """
    Endpoint /reports/monthly.xlsx
    Aceita ?month=YYYY-MM ou ?start=YYYY-MM-DD&end=YYYY-MM-DD
    """
    try:
        # imports tardios para evitar ciclos
        from models import Visit, Client, Property, Plot

        # 1) intervalo
        month = request.args.get("month")
        start = request.args.get("start")
        end = request.args.get("end")

        if month:
            y, m = [int(x) for x in month.split("-")]
            start_date = _date(y, m, 1)
            next_month = _date(y + 1, 1, 1) if m == 12 else _date(y, m + 1, 1)
            end_date = next_month - _dt.timedelta(days=1)
        else:
            if not start or not end:
                return jsonify(message="Informe ?month=YYYY-MM ou ?start=YYYY-MM-DD&end=YYYY-MM-DD"), 400
            start_date = _date.fromisoformat(start)
            end_date = _date.fromisoformat(end)

        # 2) busca visitas e mapas
        visits = (
            Visit.query
            .filter(Visit.date >= start_date)
            .filter(Visit.date <= end_date)
            .order_by(Visit.date.asc().nullslast())
            .all()
        )

        client_ids = sorted({v.client_id for v in visits if v.client_id})
        prop_ids = sorted({v.property_id for v in visits if v.property_id})
        plot_ids = sorted({v.plot_id for v in visits if v.plot_id})

        clients_map = (
            {c.id: c.name for c in Client.query.filter(Client.id.in_(client_ids)).all()}
            if client_ids else {}
        )
        props_map = (
            {p.id: p.name for p in Property.query.filter(Property.id.in_(prop_ids)).all()}
            if prop_ids else {}
        )
        plots_map = (
            {pl.id: pl.name for pl in Plot.query.filter(Plot.id.in_(plot_ids)).all()}
            if plot_ids else {}
        )

        # consultores
        try:
            from routes import CONSULTANTS
            consultants_map = {c["id"]: c["name"] for c in CONSULTANTS}
        except Exception:
            consultants_map = {}

        # 3) cálculos
        total_visits = len(visits)
        visits_with_photo = sum(1 for v in visits if _has_valid_photo(v))
        unique_clients = len({v.client_id for v in visits if v.client_id})
        total_clients = Client.query.count()
        coverage = (unique_clients / total_clients) if total_clients else 0

        photo_visits_by_client = Counter()
        for v in visits:
            if v.client_id and _has_valid_photo(v):
                photo_visits_by_client[v.client_id] += 1

        clients_in_target = sum(1 for cnt in photo_visits_by_client.values() if cnt >= META_VISITAS_CLIENTE)
        target_pct = (clients_in_target / total_clients) if total_clients else 0

        # 4) workbook
        wb = Workbook()
        wb.remove(wb.active)

        ws_dash = wb.create_sheet("Dashboard")
        ws_visits = wb.create_sheet("Visitas")
        ws_atraso = wb.create_sheet("Atraso")
        ws_prods = wb.create_sheet("Produtos")

        period_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

        # 5) renderização
        _render_dashboard(
            ws_dash, visits, period_label,
            total_visits, visits_with_photo, unique_clients, total_clients,
            coverage, clients_in_target, target_pct,
            photo_visits_by_client, clients_map, consultants_map
        )
        _render_visits(ws_visits, visits, period_label, total_visits, unique_clients,
                       clients_map, props_map, plots_map, consultants_map)
        _render_atraso(ws_atraso, total_clients, photo_visits_by_client, clients_map, period_label)
        _render_products(ws_prods, visits, period_label,
                         clients_map, props_map, consultants_map)

        # 6) export
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        filename = f"relatorio_visitas_{start_date.isoformat()}_a_{end_date.isoformat()}.xlsx"
        return send_file(
            bio,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        import traceback
        print("⚠️ erro generate_monthly_xlsx:", e)
        traceback.print_exc()
        return jsonify(message=f"Erro ao gerar relatório: {e}"), 500


# ================================================================
# Aba 1 — Dashboard
# ================================================================
def _render_dashboard(
    ws, visits, period_label,
    total_visits, visits_with_photo, unique_clients, total_clients,
    coverage, clients_in_target, target_pct,
    photo_visits_by_client, clients_map, consultants_map
):
    s = _styles()

    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 110

    for col in range(1, 13):
        ws.column_dimensions[get_column_letter(col)].width = 17

    # Banner
    ws.merge_cells("A1:L1")
    ws["A1"] = "Painel Gerencial — NutriCRM"
    ws["A1"].fill = s["title_fill"]
    ws["A1"].font = s["title_font"]
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # Subtítulo
    ws.merge_cells("A2:L2")
    ws["A2"] = f"Período: {period_label}    •    Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = Font(color=TEXT_MUTED, size=10, italic=True)
    ws["A2"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 18

    # Linha 3: regra
    ws.merge_cells("A3:L3")
    ws["A3"] = f"Regra: visita conta como concluída quando há foto. Meta = {META_VISITAS_CLIENTE} visitas/cliente no período."
    ws["A3"].font = Font(color=TEXT_MUTED, size=9)
    ws["A3"].alignment = Alignment(horizontal="center")

    # 4 KPIs principais (linha 5-8)
    ws.row_dimensions[5].height = 24
    ws.row_dimensions[6].height = 36
    ws.row_dimensions[7].height = 36
    ws.row_dimensions[8].height = 24

    _kpi_card(ws, "A", "C", 5, "Total de visitas (período)",
              total_visits, "#,##0", s)
    _kpi_card(ws, "D", "F", 5, "Visitas concluídas (com foto)",
              visits_with_photo, "#,##0", s)
    _kpi_card(ws, "G", "I", 5, f"Clientes na meta ({META_VISITAS_CLIENTE}+)",
              clients_in_target, "#,##0", s)
    _kpi_card(ws, "J", "L", 5, "Cobertura da carteira",
              coverage, "0.0%", s)

    # contextualizacao em pequena linha abaixo
    ws.merge_cells("A9:L9")
    ws["A9"] = (
        f"Carteira total: {total_clients} clientes  •  Atendidos no período: {unique_clients}  •  "
        f"% na meta: {target_pct:.1%}"
    )
    ws["A9"].font = Font(color=TEXT_MUTED, size=10)
    ws["A9"].alignment = Alignment(horizontal="center")

    # ========== Visitas por consultor ==========
    _section_title(ws, "A11", "Visitas por consultor", s)
    ws["A12"] = "Consultor"
    ws["B12"] = "Visitas"
    ws["C12"] = "% do total"
    _style_header_row(ws, 12, 1, 3, s)

    cons_counts = Counter(v.consultant_id for v in visits if v.consultant_id)
    r = 13
    for cid, cnt in cons_counts.most_common():
        ws[f"A{r}"] = consultants_map.get(cid, f"Consultor {cid}")
        ws[f"B{r}"] = cnt
        ws[f"C{r}"] = (cnt / total_visits) if total_visits else 0
        ws[f"C{r}"].number_format = "0.0%"
        for col in range(1, 4):
            ws.cell(r, col).border = s["border_data"]
        r += 1

    # ========== Visitas por cultura ==========
    _section_title(ws, "E11", "Visitas por cultura", s)
    ws["E12"] = "Cultura"
    ws["F12"] = "Visitas"
    ws["G12"] = "% do total"
    _style_header_row(ws, 12, 5, 7, s)

    cult_counts = Counter()
    for v in visits:
        culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else None)
        culture = (culture or "—").strip()
        cult_counts[culture] += 1

    r = 13
    for culture, cnt in cult_counts.most_common():
        ws[f"E{r}"] = culture
        ws[f"F{r}"] = cnt
        ws[f"G{r}"] = (cnt / total_visits) if total_visits else 0
        ws[f"G{r}"].number_format = "0.0%"
        for col in range(5, 8):
            ws.cell(r, col).border = s["border_data"]
        r += 1
    end_cult_row = r - 1

    # ========== Top 5 clientes ==========
    _section_title(ws, "I11", "Top 5 clientes (concluídas)", s)
    ws["I12"] = "Cliente"
    ws["J12"] = "Visitas"
    ws["K12"] = "% da meta"
    _style_header_row(ws, 12, 9, 11, s)

    top5 = photo_visits_by_client.most_common(5)
    r = 13
    for cid, cnt in top5:
        ws[f"I{r}"] = clients_map.get(cid, f"Cliente {cid}")
        ws[f"J{r}"] = cnt
        ws[f"K{r}"] = min(cnt / META_VISITAS_CLIENTE, 1.0)
        ws[f"K{r}"].number_format = "0%"
        for col in range(9, 12):
            ws.cell(r, col).border = s["border_data"]
        r += 1

    # ========== Visitas por dia (tabela + gráfico) ==========
    day_counts = defaultdict(int)
    for v in visits:
        if v.date:
            day_counts[v.date] += 1
    days_sorted = sorted(day_counts.keys())

    section_row_days = 25
    _section_title(ws, f"A{section_row_days}", "Visitas por dia", s)
    ws[f"A{section_row_days+1}"] = "Data"
    ws[f"B{section_row_days+1}"] = "Visitas"
    _style_header_row(ws, section_row_days + 1, 1, 2, s)

    r = section_row_days + 2
    for d in days_sorted:
        ws[f"A{r}"] = d.strftime("%d/%m/%Y")
        ws[f"B{r}"] = day_counts[d]
        ws[f"A{r}"].border = s["border_data"]
        ws[f"B{r}"].border = s["border_data"]
        r += 1
    end_days_row = r - 1

    # gráfico de barras visitas por dia
    if end_days_row > section_row_days + 1:
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = "Visitas por dia"
        chart.y_axis.title = "Visitas"
        chart.x_axis.title = "Data"
        data = Reference(ws, min_col=2, min_row=section_row_days + 1,
                         max_col=2, max_row=end_days_row)
        cats = Reference(ws, min_col=1, min_row=section_row_days + 2,
                         max_col=1, max_row=end_days_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 9
        chart.width = 22
        ws.add_chart(chart, "D" + str(section_row_days))

    # gráfico pizza por cultura
    if end_cult_row > 12:
        pie = PieChart()
        pie.title = "Distribuição por cultura"
        labels = Reference(ws, min_col=5, min_row=13, max_row=end_cult_row)
        data = Reference(ws, min_col=6, min_row=12, max_row=end_cult_row)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.dataLabels = DataLabelList(showPercent=True)
        pie.height = 9
        pie.width = 14
        ws.add_chart(pie, "I" + str(section_row_days))

    # ========== Progresso por cliente com semáforo ==========
    progresso_row = max(end_days_row, section_row_days + 14) + 3

    _section_title(ws, f"A{progresso_row}", "Progresso da meta por cliente", s)
    ws.merge_cells(f"A{progresso_row}:L{progresso_row}")

    ws[f"A{progresso_row+1}"] = "Cliente"
    ws[f"B{progresso_row+1}"] = "Concluídas"
    ws[f"C{progresso_row+1}"] = "% da meta"
    ws[f"D{progresso_row+1}"] = "Barra"
    _style_header_row(ws, progresso_row + 1, 1, 4, s)

    r = progresso_row + 2
    for cid in sorted(clients_map.keys(), key=lambda k: -photo_visits_by_client.get(k, 0)):
        cnt = photo_visits_by_client.get(cid, 0)
        ws[f"A{r}"] = clients_map.get(cid, f"Cliente {cid}")
        ws[f"B{r}"] = cnt
        pct = min(cnt / META_VISITAS_CLIENTE, 1.0)
        ws[f"C{r}"] = pct
        ws[f"D{r}"] = pct
        ws[f"C{r}"].number_format = "0%"
        ws[f"D{r}"].number_format = "0%"
        for col in range(1, 5):
            ws.cell(r, col).border = s["border_data"]
        r += 1
    end_meta_row = r - 1

    if end_meta_row >= progresso_row + 2:
        # data bar
        rule = DataBarRule(
            start_type="num", start_value=0,
            end_type="num", end_value=1,
            color="2DD36F", showValue=False,
        )
        ws.conditional_formatting.add(
            f"D{progresso_row+2}:D{end_meta_row}", rule
        )

        # semáforo na coluna B (concluídas)
        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="lessThan", formula=["2"],
                       fill=PatternFill("solid", fgColor=STATUS_CANCELED),
                       font=Font(color="FFFFFF", bold=True))
        )
        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="between", formula=["2", "4"],
                       fill=PatternFill("solid", fgColor=STATUS_PENDING),
                       font=Font(bold=True))
        )
        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=["5"],
                       fill=PatternFill("solid", fgColor=STATUS_DONE),
                       font=Font(color="FFFFFF", bold=True))
        )

    # larguras finais
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 22
    for col in range(5, 13):
        ws.column_dimensions[get_column_letter(col)].width = 16


def _kpi_card(ws, col1, col2, row, title, value, fmt, s):
    """Card de KPI ocupando 3 colunas e 4 linhas."""
    ws.merge_cells(f"{col1}{row}:{col2}{row}")
    label_cell = ws[f"{col1}{row}"]
    label_cell.value = title
    label_cell.fill = s["kpi_label_fill"]
    label_cell.font = s["kpi_label_font"]
    label_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    label_cell.border = s["border_thin"]

    ws.merge_cells(f"{col1}{row+1}:{col2}{row+3}")
    val_cell = ws[f"{col1}{row+1}"]
    val_cell.value = value
    val_cell.fill = s["kpi_value_fill"]
    val_cell.font = s["kpi_value_font"]
    val_cell.alignment = Alignment(horizontal="center", vertical="center")
    val_cell.border = s["border_thin"]
    if fmt:
        val_cell.number_format = fmt

    c1 = ord(col1) - 64
    c2 = ord(col2) - 64
    for rr in range(row + 1, row + 4):
        for cc in range(c1, c2 + 1):
            cell = ws.cell(rr, cc)
            cell.fill = s["kpi_value_fill"]
            cell.border = s["border_thin"]


def _section_title(ws, cell_ref, text, s):
    cell = ws[cell_ref]
    cell.value = text
    cell.font = s["section_font"]
    cell.fill = s["section_fill"]
    cell.alignment = Alignment(horizontal="left", vertical="center")
    cell.border = s["border_thin"]


def _style_header_row(ws, row, col_start, col_end, s):
    for col in range(col_start, col_end + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = s["header_fill"]
        cell.font = s["header_font"]
        cell.alignment = s["center"]
        cell.border = s["border_thin"]


# ================================================================
# Aba 2 — Visitas
# ================================================================
def _render_visits(ws, visits, period_label, total_visits, unique_clients,
                   clients_map, props_map, plots_map, consultants_map):
    s = _styles()

    ws["A1"] = "Relatório Mensal — Visitas Técnicas"
    ws["A1"].font = Font(bold=True, size=14, color=BRAND_GREEN)
    ws["A2"] = "Período:"
    ws["A2"].font = s["bold"]
    ws["B2"] = period_label
    ws["A3"] = "Total de visitas:"
    ws["A3"].font = s["bold"]
    ws["B3"] = total_visits
    ws["A4"] = "Clientes atendidos:"
    ws["A4"].font = s["bold"]
    ws["B4"] = unique_clients

    for r in range(1, 5):
        for c in range(1, 3):
            cell = ws.cell(r, c)
            cell.fill = s["subheader_fill"]
            cell.border = s["border_data"]

    headers = [
        "Data", "Cliente", "Propriedade", "Talhão", "Consultor",
        "Cultura", "Variedade", "Fenologia", "Status", "Tem foto?",
        "Dias desde plantio", "Observações",
    ]
    header_row = 6
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, len(headers), s)
    ws.freeze_panes = "A7"

    today = _date.today()
    row_idx = header_row
    for v in visits:
        row_idx += 1

        client_name = clients_map.get(v.client_id, f"Cliente {v.client_id}" if v.client_id else "—")
        prop_name = props_map.get(v.property_id, "—") if v.property_id else "—"
        plot_name = plots_map.get(v.plot_id, "—") if v.plot_id else "—"
        cons_name = consultants_map.get(v.consultant_id, f"Consultor {v.consultant_id}" if v.consultant_id else "—")

        culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else "—")
        variety = v.variety or (v.planting.variety if getattr(v, "planting", None) else "—")

        # dias desde plantio
        dias_plantio = "—"
        planting = getattr(v, "planting", None)
        planting_date = getattr(planting, "planting_date", None) if planting else None
        if planting_date and v.date:
            try:
                dias_plantio = (v.date - planting_date).days
            except Exception:
                dias_plantio = "—"

        has_photo = "Sim" if _has_valid_photo(v) else "Não"
        status_pt = _translate_status(v.status)
        obs = _truncate(getattr(v, "recommendation", None) or getattr(v, "observation", None), 200)

        row_values = [
            _br_date(v.date), client_name, prop_name, plot_name, cons_name,
            culture, variety, v.fenologia_real or "—", status_pt, has_photo,
            dias_plantio, obs,
        ]
        for i, val in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=i)
            cell.value = val
            cell.border = s["border_data"]
            cell.font = s["row_font"]
            if i in (1, 9, 10, 11):
                cell.alignment = s["center"]
            else:
                cell.alignment = s["left"]
            if (row_idx - header_row) % 2 == 0:
                cell.fill = s["zebra_fill"]

        # cor do status
        status_cell = ws.cell(row=row_idx, column=9)
        if status_pt == "Concluída":
            status_cell.fill = PatternFill("solid", fgColor=STATUS_DONE)
            status_cell.font = Font(color="FFFFFF", bold=True)
        elif status_pt == "Cancelada":
            status_cell.fill = PatternFill("solid", fgColor=STATUS_CANCELED)
            status_cell.font = Font(color="FFFFFF", bold=True)
        elif status_pt in ("Planejada", "Pendente"):
            status_cell.fill = PatternFill("solid", fgColor=STATUS_PENDING)
            status_cell.font = Font(color=NEUTRAL_GREY_DARK, bold=True)

    # AutoFiltro
    if row_idx > header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{row_idx}"

    # larguras
    widths = [12, 28, 22, 18, 18, 12, 18, 14, 14, 10, 14, 60]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ================================================================
# Aba 3 — Atraso (foco gerencial)
# ================================================================
def _render_atraso(ws, total_clients, photo_visits_by_client, clients_map, period_label):
    s = _styles()

    ws["A1"] = "Clientes em atraso (abaixo da meta)"
    ws["A1"].font = Font(bold=True, size=14, color=BRAND_GREEN)
    ws.merge_cells("A1:E1")

    ws["A2"] = f"Período: {period_label}    •    Meta: {META_VISITAS_CLIENTE} visitas/cliente"
    ws["A2"].font = s["muted"]
    ws.merge_cells("A2:E2")

    headers = ["Cliente", "Visitas concluídas", "Faltam para meta", "% da meta", "Prioridade"]
    header_row = 4
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, 5, s)
    ws.freeze_panes = "A5"

    # ranking invertido — quem está mais atrasado primeiro
    all_clients = []
    for cid, name in clients_map.items():
        cnt = photo_visits_by_client.get(cid, 0)
        if cnt < META_VISITAS_CLIENTE:
            all_clients.append((cid, name, cnt))

    # Adiciona clientes da carteira que nem aparecem nas visitas
    try:
        from models import Client
        all_carteira = Client.query.all()
        existing_ids = set(clients_map.keys())
        for c in all_carteira:
            if c.id not in existing_ids:
                all_clients.append((c.id, c.name, 0))
    except Exception:
        pass

    all_clients.sort(key=lambda x: x[2])

    r = 5
    for cid, name, cnt in all_clients:
        falta = META_VISITAS_CLIENTE - cnt
        pct = cnt / META_VISITAS_CLIENTE
        prioridade = "ALTA" if cnt <= 1 else ("MÉDIA" if cnt <= 3 else "BAIXA")

        ws.cell(r, 1).value = name
        ws.cell(r, 2).value = cnt
        ws.cell(r, 3).value = falta
        ws.cell(r, 4).value = pct
        ws.cell(r, 4).number_format = "0%"
        ws.cell(r, 5).value = prioridade

        for col in range(1, 6):
            ws.cell(r, col).border = s["border_data"]
            ws.cell(r, col).alignment = s["center"] if col != 1 else s["left"]
            if (r - 5) % 2 == 0:
                ws.cell(r, col).fill = s["zebra_fill"]

        # cor da prioridade
        prio_cell = ws.cell(r, 5)
        if prioridade == "ALTA":
            prio_cell.fill = PatternFill("solid", fgColor=STATUS_CANCELED)
            prio_cell.font = Font(color="FFFFFF", bold=True)
        elif prioridade == "MÉDIA":
            prio_cell.fill = PatternFill("solid", fgColor=STATUS_PENDING)
            prio_cell.font = Font(bold=True)
        else:
            prio_cell.fill = PatternFill("solid", fgColor=BRAND_LIGHT)
            prio_cell.font = Font(color=BRAND_DARK, bold=True)

        r += 1

    if r > 5:
        ws.auto_filter.ref = f"A{header_row}:E{r-1}"

    widths = [32, 16, 16, 12, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ================================================================
# Aba 4 — Produtos
# ================================================================
def _render_products(ws, visits, period_label,
                     clients_map, props_map, consultants_map):
    s = _styles()

    ws["A1"] = "Produtos aplicados nas visitas"
    ws["A1"].font = Font(bold=True, size=14, color=BRAND_GREEN)
    ws.merge_cells("A1:I1")

    ws["A2"] = f"Período: {period_label}"
    ws["A2"].font = s["muted"]
    ws.merge_cells("A2:I2")

    headers = [
        "Data", "Cliente", "Propriedade", "Cultura", "Fenologia",
        "Consultor", "Produto", "Dose+Unidade", "Data aplicação",
    ]
    header_row = 4
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, len(headers), s)
    ws.freeze_panes = "A5"

    r = header_row + 1
    has_data = False
    for v in visits:
        produtos = getattr(v, "products", None) or []
        for p in produtos:
            has_data = True
            client_name = clients_map.get(v.client_id, "—") if v.client_id else "—"
            prop_name = props_map.get(v.property_id, "—") if v.property_id else "—"
            cons_name = consultants_map.get(v.consultant_id, "—") if v.consultant_id else "—"
            culture = v.culture or "—"
            fenologia = v.fenologia_real or "—"

            dose_unidade = ""
            try:
                dose = getattr(p, "dose", "") or ""
                unit = getattr(p, "unit", "") or ""
                dose_unidade = f"{dose} {unit}".strip()
            except Exception:
                pass

            row_values = [
                _br_date(v.date),
                client_name,
                prop_name,
                culture,
                fenologia,
                cons_name,
                getattr(p, "product_name", "—"),
                dose_unidade,
                _br_date(getattr(p, "application_date", None) or v.date),
            ]
            for i, val in enumerate(row_values, start=1):
                cell = ws.cell(row=r, column=i)
                cell.value = val
                cell.border = s["border_data"]
                cell.font = s["row_font"]
                cell.alignment = s["center"] if i in (1, 4, 5, 8, 9) else s["left"]
                if (r - header_row - 1) % 2 == 0:
                    cell.fill = s["zebra_fill"]
            r += 1

    if not has_data:
        ws.cell(row=header_row + 1, column=1).value = "Nenhum produto registrado no período."
        ws.cell(row=header_row + 1, column=1).font = s["muted"]
        ws.merge_cells(start_row=header_row + 1, start_column=1,
                       end_row=header_row + 1, end_column=9)

    if r > header_row + 1:
        ws.auto_filter.ref = f"A{header_row}:I{r-1}"

    widths = [12, 26, 22, 12, 14, 18, 22, 16, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
