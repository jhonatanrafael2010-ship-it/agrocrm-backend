"""
================================================================
excel_report_service.py — v3 Premium
================================================================

Versão 3 do relatório XLSX gerencial NutriCRM.

Mudanças vs v2:
- FIX consultor: busca da tabela `Consultant` do banco (a constante
  CONSULTANTS hardcoded em models.py está com IDs desencontrados).
- Visual premium: banner com faixa dourada decorativa, fontes
  refinadas, espaçamento generoso, rodapé corporativo.
- Gráficos refeitos: barra com cor única, pizza com legenda lateral,
  tamanhos maiores, títulos legíveis.
- Subtítulos com tracking. KPIs polidos.

Aceita ?month=YYYY-MM ou ?start=YYYY-MM-DD&end=YYYY-MM-DD
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
from openpyxl.chart.legend import Legend
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.formatting.rule import DataBarRule, CellIsRule


META_VISITAS_CLIENTE = 5


# ================================================================
# Paleta premium
# ================================================================
BRAND_DARKEST = "0A2818"
BRAND_DARK = "0F5132"
BRAND_GREEN = "14532D"
BRAND_MID = "166534"
BRAND_LIGHT = "DCFCE7"
GOLD = "C8A857"
GOLD_LIGHT = "F4E5BC"

NEUTRAL_WHITE = "FFFFFF"
NEUTRAL_OFFWHITE = "FAFAF9"
NEUTRAL_GREY_LIGHTEST = "F4F4F5"
NEUTRAL_GREY_LIGHT = "E4E4E7"
NEUTRAL_TEXT = "18181B"
TEXT_MUTED = "71717A"

STATUS_DONE = "16A34A"
STATUS_PENDING = "EAB308"
STATUS_CANCELED = "DC2626"
STATUS_DONE_BG = "DCFCE7"
STATUS_PENDING_BG = "FEF3C7"
STATUS_CANCELED_BG = "FEE2E2"


def _styles():
    return {
        "banner_fill": PatternFill("solid", fgColor=BRAND_DARKEST),
        "banner_font": Font(name="Calibri", color=NEUTRAL_WHITE, bold=True, size=18),
        "gold_fill": PatternFill("solid", fgColor=GOLD),

        "header_fill": PatternFill("solid", fgColor=BRAND_GREEN),
        "header_font": Font(name="Calibri", color=NEUTRAL_WHITE, bold=True, size=10),

        "kpi_label_fill": PatternFill("solid", fgColor=BRAND_GREEN),
        "kpi_value_fill": PatternFill("solid", fgColor=BRAND_DARK),
        "kpi_label_font": Font(name="Calibri", color=NEUTRAL_WHITE, bold=True, size=10),
        "kpi_value_font": Font(name="Calibri", color=NEUTRAL_WHITE, bold=True, size=22),

        "section_font": Font(name="Calibri", bold=True, color=BRAND_GREEN, size=11),
        "subheader_fill": PatternFill("solid", fgColor=BRAND_LIGHT),

        "muted": Font(name="Calibri", color=TEXT_MUTED, size=9),
        "muted_italic": Font(name="Calibri", color=TEXT_MUTED, size=9, italic=True),
        "footer": Font(name="Calibri", color=TEXT_MUTED, size=8, italic=True),

        "bold": Font(name="Calibri", bold=True, color=NEUTRAL_TEXT),
        "row_font": Font(name="Calibri", color=NEUTRAL_TEXT, size=10),
        "zebra_fill": PatternFill("solid", fgColor=NEUTRAL_OFFWHITE),

        "center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "left": Alignment(horizontal="left", vertical="top", wrap_text=True),
        "left_center": Alignment(horizontal="left", vertical="center", wrap_text=True),

        "border_data": Border(
            bottom=Side(style="hair", color=NEUTRAL_GREY_LIGHT)
        ),
        "border_section": Border(
            bottom=Side(style="medium", color=GOLD)
        ),
    }


# ================================================================
# Helpers
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


def _build_consultants_map():
    """
    Busca consultores PRIMEIRO da tabela Consultant do banco.
    Fallback para constante hardcoded apenas se a query falhar.
    """
    consultants_map = {}
    try:
        from models import Consultant
        consultants_map = {c.id: c.name for c in Consultant.query.all()}
        if consultants_map:
            return consultants_map
    except Exception as e:
        print(f"[excel_report] warning - Consultant.query falhou: {e}")

    try:
        from routes import CONSULTANTS
        consultants_map = {c["id"]: c["name"] for c in CONSULTANTS}
    except Exception:
        pass

    return consultants_map


# ================================================================
# Função principal
# ================================================================
def generate_monthly_xlsx(request):
    try:
        from models import Visit, Client, Property, Plot

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

        consultants_map = _build_consultants_map()

        total_visits = len(visits)
        visits_with_photo = sum(1 for v in visits if _has_valid_photo(v))
        unique_clients = len({v.client_id for v in visits if v.client_id})
        total_clients = Client.query.count()
        coverage = (unique_clients / total_clients) if total_clients else 0

        photo_visits_by_client = Counter()
        for v in visits:
            if v.client_id and _has_valid_photo(v):
                photo_visits_by_client[v.client_id] += 1

        clients_in_target = sum(
            1 for cnt in photo_visits_by_client.values() if cnt >= META_VISITAS_CLIENTE
        )
        target_pct = (clients_in_target / total_clients) if total_clients else 0

        wb = Workbook()
        wb.remove(wb.active)

        ws_dash = wb.create_sheet("Dashboard")
        ws_visits = wb.create_sheet("Visitas")
        ws_atraso = wb.create_sheet("Atraso")
        ws_prods = wb.create_sheet("Produtos")

        period_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

        _render_dashboard(
            ws_dash, visits, period_label,
            total_visits, visits_with_photo, unique_clients, total_clients,
            coverage, clients_in_target, target_pct,
            photo_visits_by_client, clients_map, consultants_map
        )
        _render_visits(
            ws_visits, visits, period_label, total_visits, unique_clients,
            clients_map, props_map, plots_map, consultants_map
        )
        _render_atraso(
            ws_atraso, total_clients, photo_visits_by_client, clients_map, period_label
        )
        _render_products(
            ws_prods, visits, period_label,
            clients_map, props_map, consultants_map
        )

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
# Aba 1 — Dashboard premium
# ================================================================
def _render_dashboard(
    ws, visits, period_label,
    total_visits, visits_with_photo, unique_clients, total_clients,
    coverage, clients_in_target, target_pct,
    photo_visits_by_client, clients_map, consultants_map
):
    s = _styles()
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 100

    for col in range(1, 13):
        ws.column_dimensions[get_column_letter(col)].width = 17

    # ===== Banner =====
    ws.row_dimensions[1].height = 8
    ws.row_dimensions[2].height = 42
    ws.row_dimensions[3].height = 4
    ws.row_dimensions[4].height = 22

    ws.merge_cells("A2:L2")
    ws["A2"] = "PAINEL GERENCIAL — NutriCRM"
    ws["A2"].fill = s["banner_fill"]
    ws["A2"].font = s["banner_font"]
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:L3")
    ws["A3"].fill = s["gold_fill"]

    ws.merge_cells("A4:L4")
    ws["A4"] = (
        f"Período: {period_label}    •    "
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    )
    ws["A4"].font = Font(name="Calibri Light", color=TEXT_MUTED, size=10, italic=True)
    ws["A4"].alignment = Alignment(horizontal="center", vertical="center")

    # ===== Regra =====
    ws.row_dimensions[6].height = 18
    ws.merge_cells("A6:L6")
    ws["A6"] = (
        f"Regra de cálculo: visita conta como concluída quando há foto.    "
        f"Meta = {META_VISITAS_CLIENTE} visitas/cliente no período."
    )
    ws["A6"].font = Font(name="Calibri", color=TEXT_MUTED, size=9, italic=True)
    ws["A6"].alignment = Alignment(horizontal="center", vertical="center")

    # ===== KPIs =====
    ws.row_dimensions[8].height = 26
    ws.row_dimensions[9].height = 32
    ws.row_dimensions[10].height = 32
    ws.row_dimensions[11].height = 26

    _kpi_card(ws, "A", "C", 8, "TOTAL DE VISITAS",
              total_visits, "#,##0", s)
    _kpi_card(ws, "D", "F", 8, "VISITAS CONCLUÍDAS",
              visits_with_photo, "#,##0", s)
    _kpi_card(ws, "G", "I", 8, f"CLIENTES NA META ({META_VISITAS_CLIENTE}+)",
              clients_in_target, "#,##0", s)
    _kpi_card(ws, "J", "L", 8, "COBERTURA DA CARTEIRA",
              coverage, "0.0%", s)

    ws.row_dimensions[13].height = 20
    ws.merge_cells("A13:L13")
    ws["A13"] = (
        f"Carteira total: {total_clients}  •  Atendidos no período: {unique_clients}  •  "
        f"% na meta: {target_pct:.1%}"
    )
    ws["A13"].font = Font(name="Calibri", color=TEXT_MUTED, size=10)
    ws["A13"].alignment = Alignment(horizontal="center", vertical="center")

    # ===== 3 tabelas lado a lado =====
    _section_title_premium(ws, "A15", "VISITAS POR CONSULTOR", "A15:C15", s)
    ws["A16"] = "Consultor"
    ws["B16"] = "Visitas"
    ws["C16"] = "% do total"
    _style_header_row(ws, 16, 1, 3, s)

    cons_counts = Counter(v.consultant_id for v in visits if v.consultant_id)
    r = 17
    for cid, cnt in cons_counts.most_common():
        ws[f"A{r}"] = consultants_map.get(cid, f"Consultor #{cid}")
        ws[f"B{r}"] = cnt
        ws[f"C{r}"] = (cnt / total_visits) if total_visits else 0
        ws[f"C{r}"].number_format = "0.0%"
        for col in range(1, 4):
            ws.cell(r, col).border = s["border_data"]
            ws.cell(r, col).font = s["row_font"]
            ws.cell(r, col).alignment = s["left_center"] if col == 1 else s["center"]
            if (r - 17) % 2 == 1:
                ws.cell(r, col).fill = s["zebra_fill"]
        r += 1

    _section_title_premium(ws, "E15", "VISITAS POR CULTURA", "E15:G15", s)
    ws["E16"] = "Cultura"
    ws["F16"] = "Visitas"
    ws["G16"] = "% do total"
    _style_header_row(ws, 16, 5, 7, s)

    cult_counts = Counter()
    for v in visits:
        culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else None)
        culture = (culture or "—").strip()
        cult_counts[culture] += 1

    r = 17
    for culture, cnt in cult_counts.most_common():
        ws[f"E{r}"] = culture
        ws[f"F{r}"] = cnt
        ws[f"G{r}"] = (cnt / total_visits) if total_visits else 0
        ws[f"G{r}"].number_format = "0.0%"
        for col in range(5, 8):
            ws.cell(r, col).border = s["border_data"]
            ws.cell(r, col).font = s["row_font"]
            ws.cell(r, col).alignment = s["left_center"] if col == 5 else s["center"]
            if (r - 17) % 2 == 1:
                ws.cell(r, col).fill = s["zebra_fill"]
        r += 1
    end_cult_row = r - 1

    _section_title_premium(ws, "I15", "TOP 5 CLIENTES (CONCLUÍDAS)", "I15:K15", s)
    ws["I16"] = "Cliente"
    ws["J16"] = "Visitas"
    ws["K16"] = "% da meta"
    _style_header_row(ws, 16, 9, 11, s)

    top5 = photo_visits_by_client.most_common(5)
    r = 17
    for cid, cnt in top5:
        ws[f"I{r}"] = clients_map.get(cid, f"Cliente {cid}")
        ws[f"J{r}"] = cnt
        ws[f"K{r}"] = min(cnt / META_VISITAS_CLIENTE, 1.0)
        ws[f"K{r}"].number_format = "0%"
        for col in range(9, 12):
            ws.cell(r, col).border = s["border_data"]
            ws.cell(r, col).font = s["row_font"]
            ws.cell(r, col).alignment = s["left_center"] if col == 9 else s["center"]
            if (r - 17) % 2 == 1:
                ws.cell(r, col).fill = s["zebra_fill"]
        r += 1

    # ===== Visitas por dia + gráficos =====
    day_counts = defaultdict(int)
    for v in visits:
        if v.date:
            day_counts[v.date] += 1
    days_sorted = sorted(day_counts.keys())

    section_row_days = 27
    _section_title_premium(
        ws, f"A{section_row_days}",
        "EVOLUÇÃO DIÁRIA DE VISITAS",
        f"A{section_row_days}:B{section_row_days}",
        s
    )
    ws[f"A{section_row_days+1}"] = "Data"
    ws[f"B{section_row_days+1}"] = "Visitas"
    _style_header_row(ws, section_row_days + 1, 1, 2, s)

    r = section_row_days + 2
    for d in days_sorted:
        ws[f"A{r}"] = d.strftime("%d/%m/%Y")
        ws[f"B{r}"] = day_counts[d]
        ws[f"A{r}"].border = s["border_data"]
        ws[f"B{r}"].border = s["border_data"]
        ws[f"A{r}"].font = s["row_font"]
        ws[f"B{r}"].font = s["row_font"]
        ws[f"A{r}"].alignment = s["center"]
        ws[f"B{r}"].alignment = s["center"]
        if (r - (section_row_days + 2)) % 2 == 1:
            ws[f"A{r}"].fill = s["zebra_fill"]
            ws[f"B{r}"].fill = s["zebra_fill"]
        r += 1
    end_days_row = r - 1

    # gráfico barras com cor única
    if end_days_row > section_row_days + 1:
        chart = BarChart()
        chart.type = "col"
        chart.style = 2
        chart.title = "Visitas por dia"
        chart.y_axis.title = "Quantidade"
        chart.x_axis.title = None
        chart.legend = None
        chart.height = 11
        chart.width = 18

        data = Reference(ws, min_col=2, min_row=section_row_days + 1,
                         max_col=2, max_row=end_days_row)
        cats = Reference(ws, min_col=1, min_row=section_row_days + 2,
                         max_col=1, max_row=end_days_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)

        if chart.series:
            gp = GraphicalProperties(solidFill=BRAND_GREEN)
            gp.line.solidFill = BRAND_DARK
            chart.series[0].graphicalProperties = gp

        ws.add_chart(chart, "D" + str(section_row_days))

    # gráfico pizza com legenda lateral
    if end_cult_row > 16:
        pie = PieChart()
        pie.title = "Distribuição por cultura"
        pie.height = 11
        pie.width = 12

        labels = Reference(ws, min_col=5, min_row=17, max_row=end_cult_row)
        data = Reference(ws, min_col=6, min_row=16, max_row=end_cult_row)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)

        pie.dataLabels = DataLabelList(
            showPercent=True,
            showCatName=False,
            showSerName=False,
        )
        pie.legend = Legend()
        pie.legend.position = "r"

        ws.add_chart(pie, "I" + str(section_row_days))

    # ===== Progresso por cliente =====
    progresso_row = max(end_days_row, section_row_days + 22) + 3

    _section_title_premium(
        ws, f"A{progresso_row}",
        "PROGRESSO DA META POR CLIENTE",
        f"A{progresso_row}:L{progresso_row}",
        s
    )

    ws[f"A{progresso_row+1}"] = "Cliente"
    ws[f"B{progresso_row+1}"] = "Concluídas"
    ws[f"C{progresso_row+1}"] = "% da meta"
    ws[f"D{progresso_row+1}"] = "Progresso"
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
            ws.cell(r, col).font = s["row_font"]
            ws.cell(r, col).alignment = s["left_center"] if col == 1 else s["center"]
            if (r - (progresso_row + 2)) % 2 == 1:
                ws.cell(r, col).fill = s["zebra_fill"]
        r += 1
    end_meta_row = r - 1

    if end_meta_row >= progresso_row + 2:
        rule = DataBarRule(
            start_type="num", start_value=0,
            end_type="num", end_value=1,
            color=BRAND_MID, showValue=False,
        )
        ws.conditional_formatting.add(
            f"D{progresso_row+2}:D{end_meta_row}", rule
        )

        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="lessThanOrEqual", formula=["1"],
                       fill=PatternFill("solid", fgColor=STATUS_CANCELED_BG),
                       font=Font(color=STATUS_CANCELED, bold=True))
        )
        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="between", formula=["2", "4"],
                       fill=PatternFill("solid", fgColor=STATUS_PENDING_BG),
                       font=Font(color="92400E", bold=True))
        )
        ws.conditional_formatting.add(
            f"B{progresso_row+2}:B{end_meta_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=["5"],
                       fill=PatternFill("solid", fgColor=STATUS_DONE_BG),
                       font=Font(color=STATUS_DONE, bold=True))
        )

    # ===== Rodapé =====
    footer_row = end_meta_row + 3
    ws.row_dimensions[footer_row].height = 6
    ws.merge_cells(f"A{footer_row}:L{footer_row}")
    ws[f"A{footer_row}"].fill = s["gold_fill"]

    ws.merge_cells(f"A{footer_row+1}:L{footer_row+1}")
    ws[f"A{footer_row+1}"] = "NutriCRM  •  Documento gerencial  •  Confidencial"
    ws[f"A{footer_row+1}"].font = s["footer"]
    ws[f"A{footer_row+1}"].alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 12
    ws.column_dimensions["G"].width = 14
    ws.column_dimensions["H"].width = 4
    ws.column_dimensions["I"].width = 22
    ws.column_dimensions["J"].width = 12
    ws.column_dimensions["K"].width = 14
    ws.column_dimensions["L"].width = 14


def _kpi_card(ws, col1, col2, row, title, value, fmt, s):
    ws.merge_cells(f"{col1}{row}:{col2}{row}")
    label_cell = ws[f"{col1}{row}"]
    label_cell.value = title
    label_cell.fill = s["kpi_label_fill"]
    label_cell.font = s["kpi_label_font"]
    label_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.merge_cells(f"{col1}{row+1}:{col2}{row+3}")
    val_cell = ws[f"{col1}{row+1}"]
    val_cell.value = value
    val_cell.fill = s["kpi_value_fill"]
    val_cell.font = s["kpi_value_font"]
    val_cell.alignment = Alignment(horizontal="center", vertical="center")
    if fmt:
        val_cell.number_format = fmt

    c1 = ord(col1) - 64
    c2 = ord(col2) - 64
    for rr in range(row + 1, row + 4):
        for cc in range(c1, c2 + 1):
            cell = ws.cell(rr, cc)
            cell.fill = s["kpi_value_fill"]


def _section_title_premium(ws, cell_ref, text, merge_range, s):
    ws.merge_cells(merge_range)
    cell = ws[cell_ref]
    cell.value = text
    cell.font = s["section_font"]
    cell.alignment = Alignment(horizontal="left", vertical="bottom")
    cell.border = s["border_section"]


def _style_header_row(ws, row, col_start, col_end, s):
    for col in range(col_start, col_end + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = s["header_fill"]
        cell.font = s["header_font"]
        cell.alignment = s["center"]


# ================================================================
# Aba 2 — Visitas
# ================================================================
def _render_visits(ws, visits, period_label, total_visits, unique_clients,
                   clients_map, props_map, plots_map, consultants_map):
    s = _styles()
    ws.sheet_view.showGridLines = False

    ws.row_dimensions[1].height = 28
    ws.merge_cells("A1:L1")
    ws["A1"] = "RELATÓRIO DE VISITAS TÉCNICAS"
    ws["A1"].fill = s["banner_fill"]
    ws["A1"].font = s["banner_font"]
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:L2")
    ws["A2"].fill = s["gold_fill"]
    ws.row_dimensions[2].height = 4

    ws.row_dimensions[3].height = 22
    ws["A3"] = "Período:"
    ws["A3"].font = s["bold"]
    ws["B3"] = period_label
    ws["B3"].font = s["row_font"]
    ws["D3"] = "Total de visitas:"
    ws["D3"].font = s["bold"]
    ws["E3"] = total_visits
    ws["E3"].font = s["row_font"]
    ws["G3"] = "Clientes atendidos:"
    ws["G3"].font = s["bold"]
    ws["H3"] = unique_clients
    ws["H3"].font = s["row_font"]

    headers = [
        "Data", "Cliente", "Propriedade", "Talhão", "Consultor",
        "Cultura", "Variedade", "Fenologia", "Status", "Foto",
        "Dias plantio", "Observações",
    ]
    header_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, len(headers), s)
    ws.row_dimensions[header_row].height = 26
    ws.freeze_panes = "A6"

    row_idx = header_row
    for v in visits:
        row_idx += 1

        client_name = clients_map.get(v.client_id, "—") if v.client_id else "—"
        prop_name = props_map.get(v.property_id, "—") if v.property_id else "—"
        plot_name = plots_map.get(v.plot_id, "—") if v.plot_id else "—"
        cons_name = consultants_map.get(v.consultant_id, f"#{v.consultant_id}" if v.consultant_id else "—")

        culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else "—")
        variety = v.variety or (v.planting.variety if getattr(v, "planting", None) else "—")

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
        obs = _truncate(v.recommendation, 200)

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
            cell.alignment = s["center"] if i in (1, 9, 10, 11) else s["left"]
            if (row_idx - header_row) % 2 == 0:
                cell.fill = s["zebra_fill"]

        status_cell = ws.cell(row=row_idx, column=9)
        if status_pt == "Concluída":
            status_cell.fill = PatternFill("solid", fgColor=STATUS_DONE_BG)
            status_cell.font = Font(name="Calibri", color=STATUS_DONE, bold=True, size=10)
        elif status_pt == "Cancelada":
            status_cell.fill = PatternFill("solid", fgColor=STATUS_CANCELED_BG)
            status_cell.font = Font(name="Calibri", color=STATUS_CANCELED, bold=True, size=10)
        elif status_pt in ("Planejada", "Pendente"):
            status_cell.fill = PatternFill("solid", fgColor=STATUS_PENDING_BG)
            status_cell.font = Font(name="Calibri", color="92400E", bold=True, size=10)

    if row_idx > header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{row_idx}"

    widths = [12, 28, 22, 18, 18, 12, 18, 14, 14, 8, 12, 60]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ================================================================
# Aba 3 — Atraso
# ================================================================
def _render_atraso(ws, total_clients, photo_visits_by_client, clients_map, period_label):
    s = _styles()
    ws.sheet_view.showGridLines = False

    ws.row_dimensions[1].height = 28
    ws.merge_cells("A1:E1")
    ws["A1"] = "CLIENTES EM ATRASO — AÇÃO PRIORITÁRIA"
    ws["A1"].fill = s["banner_fill"]
    ws["A1"].font = s["banner_font"]
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:E2")
    ws["A2"].fill = s["gold_fill"]
    ws.row_dimensions[2].height = 4

    ws.merge_cells("A3:E3")
    ws["A3"] = (
        f"Período: {period_label}    •    "
        f"Meta: {META_VISITAS_CLIENTE} visitas/cliente"
    )
    ws["A3"].font = s["muted_italic"]
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 18

    headers = ["Cliente", "Concluídas", "Faltam", "% da meta", "Prioridade"]
    header_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, 5, s)
    ws.row_dimensions[header_row].height = 24
    ws.freeze_panes = "A6"

    all_clients = []
    for cid, name in clients_map.items():
        cnt = photo_visits_by_client.get(cid, 0)
        if cnt < META_VISITAS_CLIENTE:
            all_clients.append((cid, name, cnt))

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

    r = header_row + 1
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
            ws.cell(r, col).font = s["row_font"]
            ws.cell(r, col).alignment = s["center"] if col != 1 else s["left_center"]
            if (r - (header_row + 1)) % 2 == 1:
                ws.cell(r, col).fill = s["zebra_fill"]

        prio_cell = ws.cell(r, 5)
        if prioridade == "ALTA":
            prio_cell.fill = PatternFill("solid", fgColor=STATUS_CANCELED_BG)
            prio_cell.font = Font(name="Calibri", color=STATUS_CANCELED, bold=True, size=10)
        elif prioridade == "MÉDIA":
            prio_cell.fill = PatternFill("solid", fgColor=STATUS_PENDING_BG)
            prio_cell.font = Font(name="Calibri", color="92400E", bold=True, size=10)
        else:
            prio_cell.fill = PatternFill("solid", fgColor=STATUS_DONE_BG)
            prio_cell.font = Font(name="Calibri", color=STATUS_DONE, bold=True, size=10)

        r += 1

    if r > header_row + 1:
        ws.auto_filter.ref = f"A{header_row}:E{r-1}"

    widths = [34, 14, 12, 14, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ================================================================
# Aba 4 — Produtos
# ================================================================
def _render_products(ws, visits, period_label,
                     clients_map, props_map, consultants_map):
    s = _styles()
    ws.sheet_view.showGridLines = False

    ws.row_dimensions[1].height = 28
    ws.merge_cells("A1:I1")
    ws["A1"] = "PRODUTOS APLICADOS"
    ws["A1"].fill = s["banner_fill"]
    ws["A1"].font = s["banner_font"]
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:I2")
    ws["A2"].fill = s["gold_fill"]
    ws.row_dimensions[2].height = 4

    ws.merge_cells("A3:I3")
    ws["A3"] = f"Período: {period_label}"
    ws["A3"].font = s["muted_italic"]
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 18

    headers = [
        "Data", "Cliente", "Propriedade", "Cultura", "Fenologia",
        "Consultor", "Produto", "Dose / Unidade", "Data aplicação",
    ]
    header_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i).value = h
    _style_header_row(ws, header_row, 1, len(headers), s)
    ws.row_dimensions[header_row].height = 24
    ws.freeze_panes = "A6"

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
                cell.alignment = s["center"] if i in (1, 4, 5, 8, 9) else s["left_center"]
                if (r - header_row - 1) % 2 == 0:
                    cell.fill = s["zebra_fill"]
            r += 1

    if not has_data:
        ws.merge_cells(start_row=header_row + 2, start_column=1,
                       end_row=header_row + 2, end_column=9)
        empty_cell = ws.cell(row=header_row + 2, column=1)
        empty_cell.value = "Nenhum produto registrado neste período."
        empty_cell.font = s["muted_italic"]
        empty_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[header_row + 2].height = 32

    if r > header_row + 1:
        ws.auto_filter.ref = f"A{header_row}:I{r-1}"

    widths = [12, 26, 22, 12, 14, 18, 22, 18, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
