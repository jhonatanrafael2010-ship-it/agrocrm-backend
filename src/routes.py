# =========================
# Python (stdlib)
# =========================
import os
import re
import uuid
import tempfile
import unicodedata
import datetime
from io import BytesIO
from urllib.request import Request, urlopen
from datetime import date as _date, datetime as _dt

# =========================
# Third-party
# =========================
import jwt
import requests
from PIL import Image as PILImage
from PIL import ImageFile, ImageOps
from sqlalchemy import text
from werkzeug.utils import secure_filename
from flask_cors import cross_origin

# PIL config
ImageFile.LOAD_TRUNCATED_IMAGES = True

# =========================
# Flask
# =========================
from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template_string,
    request,
    send_file,
)

# =========================
# XML / HTML utils
# =========================
from xml.sax.saxutils import escape as xml_escape
from html import escape as html_escape

# =========================
# ReportLab (PDF)
# =========================
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing, String, Rect

# =========================
# OpenPyXL (Excel)
# =========================
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule

# =========================
# App / Models / Utils
# =========================
from models import (
    db,
    User,
    Client,
    Property,
    Plot,
    Visit,
    Planting,
    Opportunity,
    Photo,
    PhenologyStage,
    Variety,
    Culture,
    WhatsAppContactBinding,
    WhatsAppInboundMessage,
    ChatbotConversationState,
)
from utils.r2_client import get_r2_client

import json

from services.chatbot_service import ChatbotService, parse_chatbot_message, send_telegram_message






# =====================================================
# 🔒 LIMITES DE SEGURANÇA (EVITA ESTOURO DE MEMÓRIA)
# =====================================================
MAX_VISITS = 12        # máximo de visitas no PDF cumulativo
MAX_PHOTOS_V = 6       # máximo de fotos por visita






bp = Blueprint('api', __name__, url_prefix='/api')

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/opt/render/project/src/uploads")

def normalize_phone_number(phone: str) -> str:
    if not phone:
        return ""
    phone = re.sub(r"\D", "", phone)
    if not phone.startswith("55"):
        phone = f"55{phone}"
    return phone

# ============================================================
# 🌾 CULTURAS, VARIEDADES, CONSULTOR
# ============================================================

@bp.route('/cultures', methods=['GET'])
def list_cultures():
    CULTURES = [
        {"id": 1, "name": "Milho"},
        {"id": 2, "name": "Soja"},
        {"id": 3, "name": "Algodão"},
    ]
    return jsonify(CULTURES), 200


@bp.route('/whatsapp/bindings', methods=['GET'])
def list_whatsapp_bindings():
    rows = WhatsAppContactBinding.query.order_by(WhatsAppContactBinding.id.asc()).all()
    return jsonify([r.to_dict() for r in rows]), 200


@bp.route('/whatsapp/bindings', methods=['POST'])
def create_whatsapp_binding():
    data = request.get_json() or {}

    phone_number = normalize_phone_number((data.get("phone_number") or "").strip())
    consultant_id = data.get("consultant_id")
    display_name = (data.get("display_name") or "").strip() or None

    if not phone_number:
        return jsonify(message="phone_number is required"), 400

    if consultant_id is None:
        return jsonify(message="consultant_id is required"), 400

    try:
        consultant_id = int(consultant_id)
    except (TypeError, ValueError):
        return jsonify(message="consultant_id must be an integer"), 400

    if consultant_id not in CONSULTANT_IDS:
        return jsonify(message="consultant not found"), 404

    existing = WhatsAppContactBinding.query.filter_by(phone_number=phone_number).first()
    if existing:
        return jsonify(message="phone_number already linked"), 409

    row = WhatsAppContactBinding(
        phone_number=phone_number,
        consultant_id=consultant_id,
        display_name=display_name,
        is_active=True,
    )

    db.session.add(row)
    db.session.commit()

    return jsonify(message="binding created", binding=row.to_dict()), 201


    

@bp.route('/whatsapp/webhook', methods=['GET'])
def whatsapp_webhook_verify():
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    mode = request.args.get("hub.mode")

    expected_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "agrocrm_verify_token")

    if mode == "subscribe" and verify_token == expected_token:
        return challenge, 200

    return jsonify({"error": "verification failed"}), 403


@bp.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook_receive():
    payload = request.get_json(silent=True) or {}

    try:
        entry_list = payload.get("entry", [])
        saved = 0

        for entry in entry_list:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                contacts = value.get("contacts", []) or []
                messages = value.get("messages", []) or []

                contact_name = None
                wa_from = None

                if contacts:
                    contact_name = contacts[0].get("profile", {}).get("name")
                    wa_from = contacts[0].get("wa_id")

                for msg in messages:
                    message_type = msg.get("type", "unknown")
                    wa_message_id = msg.get("id")
                    from_number = msg.get("from") or wa_from

                    text_content = None
                    media_id = None
                    mime_type = None

                    if message_type == "text":
                        text_content = (msg.get("text") or {}).get("body")

                    elif message_type == "image":
                        image_obj = msg.get("image") or {}
                        media_id = image_obj.get("id")
                        mime_type = image_obj.get("mime_type")

                    elif message_type == "audio":
                        audio_obj = msg.get("audio") or {}
                        media_id = audio_obj.get("id")
                        mime_type = audio_obj.get("mime_type")

                    existing = WhatsAppInboundMessage.query.filter_by(
                        wa_message_id=wa_message_id
                    ).first()

                    if existing:
                        continue

                    row = WhatsAppInboundMessage(
                        wa_message_id=wa_message_id,
                        phone_number=from_number or "",
                        contact_name=contact_name,
                        message_type=message_type,
                        text_content=text_content,
                        media_id=media_id,
                        mime_type=mime_type,
                        raw_payload=str(payload),
                        processing_status="received",
                    )
                    db.session.add(row)
                    saved += 1

        db.session.commit()
        return jsonify({"status": "ok", "saved": saved}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro no webhook WhatsApp: {e}")
        return jsonify({"error": str(e)}), 500



@bp.route('/telegram/test-send', methods=['POST'])
def telegram_test_send():
    try:
        data = request.get_json(silent=True) or {}
        chat_id = str(data.get("chat_id") or "").strip()
        text = (data.get("text") or "Teste do AgroCRM no Telegram").strip()

        if not chat_id:
            return jsonify({
                "ok": False,
                "error": "chat_id is required"
            }), 400

        result = send_telegram_message(chat_id=chat_id, text=text)

        return jsonify({
            "ok": True,
            "send_result": result
        }), 200

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500       

@bp.route("/reports/monthly.xlsx", methods=["GET"])
def report_monthly_xlsx():
    """
    Relatório XLSX formatado.
    Aceita:
      - ?month=YYYY-MM   (ex: 2026-02)
    ou
      - ?start=YYYY-MM-DD&end=YYYY-MM-DD  (end inclusive)
    """
    try:
        from io import BytesIO
        from datetime import date as _date
        import datetime as _dt
        from collections import Counter, defaultdict

        from flask import request, jsonify, send_file

        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.chart import LineChart, BarChart, PieChart, Reference

        # =========================
        # 1) Define intervalo
        # =========================
        month = request.args.get("month")
        start = request.args.get("start")
        end = request.args.get("end")

        if month:
            y, m = [int(x) for x in month.split("-")]
            start_date = _date(y, m, 1)
            if m == 12:
                next_month = _date(y + 1, 1, 1)
            else:
                next_month = _date(y, m + 1, 1)
            end_date = next_month - _dt.timedelta(days=1)
        else:
            if not start or not end:
                return jsonify(message="Informe ?month=YYYY-MM ou ?start=YYYY-MM-DD&end=YYYY-MM-DD"), 400
            start_date = _date.fromisoformat(start)
            end_date = _date.fromisoformat(end)

        # =========================
        # 2) Busca visitas
        # =========================
        visits = (
            Visit.query
            .filter(Visit.date >= start_date)
            .filter(Visit.date <= end_date)
            .order_by(Visit.date.asc().nullslast())
            .all()
        )

        client_ids = sorted({v.client_id for v in visits if v.client_id})
        prop_ids   = sorted({v.property_id for v in visits if v.property_id})
        plot_ids   = sorted({v.plot_id for v in visits if v.plot_id})

        clients_map = {c.id: c.name for c in Client.query.filter(Client.id.in_(client_ids)).all()} if client_ids else {}
        props_map   = {p.id: p.name for p in Property.query.filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}
        plots_map   = {pl.id: pl.name for pl in Plot.query.filter(Plot.id.in_(plot_ids)).all()} if plot_ids else {}

        # =========================
        # 3) Cria workbook / sheets
        # =========================
        wb = Workbook()

        ws = wb.active
        ws.title = "Visitas"

        ws_dash = wb.create_sheet("Dashboard", 0)  # primeira aba
        ws2 = wb.create_sheet("Produtos")

        # =========================
        # 4) Estilos
        # =========================
        header_fill = PatternFill("solid", fgColor="14532D")
        header_font = Font(color="FFFFFF", bold=True)
        title_font = Font(bold=True, size=14, color="14532D")
        bold_font = Font(bold=True)

        subheader_fill = PatternFill("solid", fgColor="E8F5E9")  # verde bem claro
        zebra_fill  = PatternFill("solid", fgColor="F8FAFC")
        zebra_fill2 = PatternFill("solid", fgColor="EEF2F7")
        # e ajuste as fontes das linhas para preto:
        row_font = Font(color="111827")



        status_planned = PatternFill("solid", fgColor="F59E0B")  # amarelo
        status_done = PatternFill("solid", fgColor="22C55E")     # verde
        status_canceled = PatternFill("solid", fgColor="EF4444") # vermelho
        status_font_dark = Font(color="0B1F17", bold=True)
        status_font_light = Font(color="FFFFFF", bold=True)

        dash_section_fill = PatternFill("solid", fgColor="E5E7EB")  # cinza claro
        dash_header_fill  = PatternFill("solid", fgColor="D1D5DB")  # cinza um pouco mais escuro
        dash_font = Font(bold=True, color="111827")                 # quase preto
        dash_center = Alignment(horizontal="center", vertical="center", wrap_text=True)



        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # BORDAS MAIS SUAVES (troque o seu thin/border por estes)
        thin_header = Side(style="thin", color="1F3A33")   # header um pouco mais visível
        hair_data   = Side(style="hair", color="16312B")   # linhas bem discretas

        border_header = Border(left=thin_header, right=thin_header, top=thin_header, bottom=thin_header)
        border_data   = Border(bottom=hair_data)          # só linha inferior, fica limpo


        kpi_fill = PatternFill("solid", fgColor="0B3A2E")
        kpi_label_fill = PatternFill("solid", fgColor="0F5132")
        kpi_font = Font(color="FFFFFF", bold=True, size=12)
        kpi_value_font = Font(color="FFFFFF", bold=True, size=18)

        def style_header(sheet, row_idx, max_col):
            for col in range(1, max_col + 1):
                cell = sheet.cell(row=row_idx, column=col)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center
                cell.border = border_header


        def br_date(d):
            if not d:
                return ""
            if isinstance(d, str):
                try:
                    d2 = _date.fromisoformat(d[:10])
                    return d2.strftime("%d/%m/%Y")
                except:
                    return d[:10]
            try:
                return d.strftime("%d/%m/%Y")
            except:
                return str(d)

        period_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

        # ==========================================================
        # 5) DASHBOARD (KPIs + Gráficos) — Layout executivo
        # ==========================================================

        # -------------------------
        # Setup visual geral
        # -------------------------
        ws_dash.sheet_view.showGridLines = False
        ws_dash.sheet_view.zoomScale = 110
        ws_dash.page_setup.orientation = "landscape"
        ws_dash.page_setup.fitToWidth = 1
        ws_dash.page_setup.fitToHeight = 0

        # largura de colunas (painel usa A..N)
        for col in range(1, 15):  # A..N
            ws_dash.column_dimensions[get_column_letter(col)].width = 16

        # alturas (melhora leitura)
        ws_dash.row_dimensions[1].height = 30
        ws_dash.row_dimensions[2].height = 18
        ws_dash.row_dimensions[4].height = 18
        ws_dash.row_dimensions[5].height = 28
        ws_dash.row_dimensions[6].height = 28
        ws_dash.row_dimensions[7].height = 28
        ws_dash.row_dimensions[8].height = 28

        # -------------------------
        # Novos estilos do Dashboard
        # -------------------------
        dash_title_fill = PatternFill("solid", fgColor="0F5132")
        dash_title_font = Font(color="FFFFFF", bold=True, size=16)
        dash_sub_font = Font(color="1F2937", bold=True, size=11)

        kpi_fill = PatternFill("solid", fgColor="0B3A2E")
        kpi_label_fill = PatternFill("solid", fgColor="14532D")
        kpi_font = Font(color="FFFFFF", bold=True, size=11)
        kpi_value_font = Font(color="FFFFFF", bold=True, size=18)

        box_border = Border(
            left=Side(style="thin", color="1F3A33"),
            right=Side(style="thin", color="1F3A33"),
            top=Side(style="thin", color="1F3A33"),
            bottom=Side(style="thin", color="1F3A33"),
        )

        muted = Font(color="6B7280")
        num_font = Font(color="111827", bold=True)

        # -------------------------
        # Cabeçalho (banner)
        # -------------------------
        ws_dash.merge_cells("A1:N1")
        ws_dash["A1"] = "Painel Gerencial — NutriCRM (Relatório de Visitas)"
        ws_dash["A1"].fill = dash_title_fill
        ws_dash["A1"].font = dash_title_font
        ws_dash["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws_dash["A1"].border = box_border

        ws_dash["A2"] = "Período:"
        ws_dash["A2"].font = dash_sub_font
        ws_dash["B2"] = period_label
        ws_dash["B2"].font = Font(color="111827", bold=True)

        ws_dash["D2"] = "Regra:"
        ws_dash["D2"].font = dash_sub_font
        ws_dash.merge_cells("E2:N2")
        ws_dash["E2"] = "Visita concluída - Meta = 5 visitas por cliente."
        ws_dash["E2"].font = muted

        # -------------------------
        # KPIs (linha de cards)
        # -------------------------
        total_visits = len(visits)

        def has_valid_photo(v) -> bool:
            photos = getattr(v, "photos", []) or []
            return any(getattr(p, "url", None) for p in photos)

        visits_with_photo = sum(1 for v in visits if has_valid_photo(v))
        real_completion = (visits_with_photo / total_visits) if total_visits else 0.0

        unique_clients = len({v.client_id for v in visits if v.client_id})
        total_clients = Client.query.count()
        coverage = (unique_clients / total_clients) if total_clients else 0

        unique_consultants = len({v.consultant_id for v in visits if v.consultant_id})
        avg_visits_per_consultant = (total_visits / unique_consultants) if unique_consultants else 0

        META_VISITAS_CLIENTE = 5

        # visitas válidas (com foto) por cliente
        photo_visits_by_client = Counter()
        for v in visits:
            if v.client_id and has_valid_photo(v):
                photo_visits_by_client[v.client_id] += 1

        done_units = sum(min(cnt, META_VISITAS_CLIENTE) for cnt in photo_visits_by_client.values())
        target_units = (total_clients or 0) * META_VISITAS_CLIENTE
        portfolio_progress = (done_units / target_units) if target_units else 0.0

        # Card helper com largura fixa de 2 colunas
        def make_kpi_block(col1, col2, row_top, title, value, fmt=None):
            # título
            ws_dash.merge_cells(f"{col1}{row_top}:{col2}{row_top}")
            tcell = ws_dash[f"{col1}{row_top}"]
            tcell.value = title
            tcell.fill = kpi_label_fill
            tcell.font = kpi_font
            tcell.alignment = Alignment(horizontal="center", vertical="center")
            tcell.border = box_border

            # valor
            ws_dash.merge_cells(f"{col1}{row_top+1}:{col2}{row_top+3}")
            vcell = ws_dash[f"{col1}{row_top+1}"]
            vcell.value = value
            vcell.fill = kpi_fill
            vcell.font = kpi_value_font
            vcell.alignment = Alignment(horizontal="center", vertical="center")
            vcell.border = box_border

            # aplicar formato (percent / number)
            if fmt:
                vcell.number_format = fmt

            # borda/fill nas células mescladas
            c1 = ord(col1) - 64
            c2 = ord(col2) - 64
            for rr in range(row_top+1, row_top+4):
                for cc in range(c1, c2+1):
                    cell = ws_dash.cell(rr, cc)
                    cell.fill = kpi_fill
                    cell.border = box_border

        # KPIs (7 cards) — 2 colunas cada
        # A-B / C-D / E-F / G-H / I-J / K-L / M-N
        make_kpi_block("A","B",4,"Total de visitas (todas)", total_visits, fmt="#,##0")
        make_kpi_block("C","D",4,"Visitas concluídas", visits_with_photo, fmt="#,##0")
        make_kpi_block("E","F",4,"Taxa de conclusão real", real_completion, fmt="0.0%")
        make_kpi_block("G","H",4,"Clientes atendidos (período)", unique_clients, fmt="#,##0")
        make_kpi_block("I","J",4,"Cobertura da carteira", coverage, fmt="0.0%")
        make_kpi_block("K","L",4,"Média visitas/consultor", round(avg_visits_per_consultant,1), fmt="0.0")
        make_kpi_block("M","N",4,"Meta 5 visitas (carteira)", portfolio_progress, fmt="0.0%")

        # trava cabeçalho
        ws_dash.freeze_panes = "A10"

        # -------------------------
        # Seções (títulos)
        # -------------------------
        def section_title(cell_ref, text):
            cell = ws_dash[cell_ref]
            cell.value = text
            cell.font = Font(bold=True, color="111827", size=12)
            cell.fill = PatternFill("solid", fgColor="E5E7EB")
            cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.border = box_border

        # -------------------------
        # Tabela: Visitas por dia (A..B)
        # -------------------------
        section_title("A10", "Visitas por dia")
        ws_dash["A12"] = "Data"
        ws_dash["B12"] = "Visitas"
        for cell in ws_dash["A12:B12"][0]:
            cell.fill = dash_header_fill
            cell.font = dash_font
            cell.alignment = dash_center
            cell.border = border_header

        day_counts = defaultdict(int)
        for v in visits:
            if v.date:
                day_counts[v.date] += 1

        days_sorted = sorted(day_counts.keys())
        r = 13
        for d in days_sorted:
            ws_dash[f"A{r}"] = d.strftime("%d/%m/%Y")
            ws_dash[f"B{r}"] = day_counts[d]
            ws_dash[f"A{r}"].alignment = left
            ws_dash[f"B{r}"].alignment = dash_center
            ws_dash[f"B{r}"].number_format = "#,##0"
            r += 1
        end_row_days = r - 1

        # -------------------------
        # Tabela: Visitas por consultor (D..E)
        # -------------------------
        section_title("D10", "Visitas por consultor")
        ws_dash["D12"] = "Consultor"
        ws_dash["E12"] = "Visitas"
        for cell in ws_dash["D12:E12"][0]:
            cell.fill = dash_header_fill
            cell.font = dash_font
            cell.alignment = dash_center
            cell.border = border_header

        try:
            consultants_map = {c["id"]: c["name"] for c in CONSULTANTS}
        except:
            consultants_map = {}

        cons_counts = Counter(v.consultant_id for v in visits if v.consultant_id)
        r2 = 13
        for cid, cnt in cons_counts.most_common():
            ws_dash[f"D{r2}"] = consultants_map.get(cid, f"ID {cid}")
            ws_dash[f"E{r2}"] = cnt
            ws_dash[f"D{r2}"].alignment = left
            ws_dash[f"E{r2}"].alignment = dash_center
            ws_dash[f"E{r2}"].number_format = "#,##0"
            r2 += 1
        end_row_cons = r2 - 1

        # -------------------------
        # Tabela: Visitas por cultura (G..H)
        # -------------------------
        section_title("G10", "Visitas por cultura")
        ws_dash["G12"] = "Cultura"
        ws_dash["H12"] = "Visitas"
        for cell in ws_dash["G12:H12"][0]:
            cell.fill = dash_header_fill
            cell.font = dash_font
            cell.alignment = dash_center
            cell.border = border_header

        cult_counts = Counter()
        for v in visits:
            culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else None)
            culture = (culture or "—").strip()
            cult_counts[culture] += 1

        r3 = 13
        for culture, cnt in cult_counts.most_common():
            ws_dash[f"G{r3}"] = culture
            ws_dash[f"H{r3}"] = cnt
            ws_dash[f"G{r3}"].alignment = left
            ws_dash[f"H{r3}"].alignment = dash_center
            ws_dash[f"H{r3}"].number_format = "#,##0"
            r3 += 1
        end_row_cult = r3 - 1

        # -------------------------
        # Tabela: Top 5 clientes (visitas com foto) (J..K)
        # -------------------------
        section_title("J10", "Top 5 clientes (visitas com foto)")
        ws_dash["J12"] = "Cliente"
        ws_dash["K12"] = "Concluídas"
        for cell in ws_dash["J12:K12"][0]:
            cell.fill = dash_header_fill
            cell.font = dash_font
            cell.alignment = dash_center
            cell.border = border_header

        client_counts = Counter()
        for v in visits:
            if v.client_id and has_valid_photo(v):
                client_counts[v.client_id] += 1

        top5 = client_counts.most_common(5)
        r4 = 13
        for cid, cnt in top5:
            ws_dash[f"J{r4}"] = clients_map.get(cid, f"Cliente {cid}")
            ws_dash[f"K{r4}"] = cnt
            ws_dash[f"J{r4}"].alignment = left
            ws_dash[f"K{r4}"].alignment = dash_center
            ws_dash[f"K{r4}"].number_format = "#,##0"
            r4 += 1
        end_row_top5 = r4 - 1


        # ==========================================================
        # 📊 Progresso meta por cliente (5 visitas com foto)
        # ==========================================================
        # bloco mais "executivo": Cliente | Concluídas | % | Barra
        start_meta_title_row = 40
        section_title(f"A{start_meta_title_row}", "Progresso da meta por cliente (5 visitas com foto)")
        ws_dash.merge_cells(f"A{start_meta_title_row}:N{start_meta_title_row}")

        ws_dash[f"A{start_meta_title_row+2}"] = "Cliente"
        ws_dash[f"B{start_meta_title_row+2}"] = "Concluídas"
        ws_dash[f"C{start_meta_title_row+2}"] = "% da meta"
        ws_dash[f"D{start_meta_title_row+2}"] = "Barra"

        for cell in ws_dash[f"A{start_meta_title_row+2}:D{start_meta_title_row+2}"][0]:
            cell.fill = dash_header_fill
            cell.font = dash_font
            cell.alignment = dash_center
            cell.border = border_header

        # escreve dados
        rmeta = start_meta_title_row + 3
        for cid, cnt in sorted(photo_visits_by_client.items(), key=lambda x: x[1], reverse=True):
            ws_dash[f"A{rmeta}"] = clients_map.get(cid, f"Cliente {cid}")
            ws_dash[f"B{rmeta}"] = cnt
            pct = min(cnt, META_VISITAS_CLIENTE) / META_VISITAS_CLIENTE
            ws_dash[f"C{rmeta}"] = pct
            ws_dash[f"C{rmeta}"].number_format = "0%"

            # estilos
            ws_dash[f"A{rmeta}"].alignment = left
            ws_dash[f"B{rmeta}"].alignment = dash_center
            ws_dash[f"C{rmeta}"].alignment = dash_center
            ws_dash[f"B{rmeta}"].number_format = "#,##0"

            for col in range(1, 5):
                ws_dash.cell(rmeta, col).border = border_data

            rmeta += 1

        end_row_meta = rmeta - 1

        # barra de progresso (DataBar)
        if end_row_meta >= (start_meta_title_row + 3):
            rule = DataBarRule(
                start_type="num", start_value=0,
                end_type="num", end_value=1,
                color="2DD36F", showValue=False
            )
            ws_dash.conditional_formatting.add(
                f"D{start_meta_title_row+3}:D{end_row_meta}", rule
            )

            # coluna D recebe o mesmo pct só pra barra funcionar bem
            for rr in range(start_meta_title_row+3, end_row_meta+1):
                ws_dash[f"D{rr}"] = ws_dash[f"C{rr}"].value
                ws_dash[f"D{rr}"].number_format = "0%"

        # ajuste largura das colunas do bloco meta
        ws_dash.column_dimensions["A"].width = 34
        ws_dash.column_dimensions["B"].width = 14
        ws_dash.column_dimensions["C"].width = 12
        ws_dash.column_dimensions["D"].width = 22



        # ==========================================================
        # 6) ABA VISITAS
        # ==========================================================
        ws["A1"] = "Relatório Mensal — Visitas Técnicas"
        ws["A1"].font = title_font

        ws["A2"] = "Período:"
        ws["A2"].font = bold_font
        ws["B2"] = period_label

        ws["A3"] = "Total de visitas:"
        ws["A3"].font = bold_font
        ws["B3"] = total_visits

        ws["A4"] = "Clientes atendidos:"
        ws["A4"].font = bold_font
        ws["B4"] = unique_clients


        # 🎨 Destaque do resumo (A1:B4)
        for r in range(1, 5):
            for c in range(1, 3):  # A..B
                cell = ws.cell(r, c)
                cell.border = border_data
                if r == 1:
                    cell.fill = subheader_fill
                    cell.font = Font(bold=True, size=14, color="14532D")
                else:
                    cell.fill = subheader_fill
                    if c == 1:
                        cell.font = bold_font
                    cell.alignment = left


        ws["A6"] = "Detalhamento de visitas"
        ws["A6"].font = bold_font

        headers = [
            "Data","Cliente","Propriedade","Talhão","Consultor",
            "Cultura","Variedade","Fenologia (observada)","Status","Observações"
        ]
        header_row = 6

        for i, h in enumerate(headers, start=1):
            ws.cell(row=header_row, column=i).value = h

        style_header(ws, header_row, len(headers))
        ws.freeze_panes = "A7"

        row_idx = header_row
        for v in visits:
            row_idx += 1

            client_name = clients_map.get(v.client_id, f"Cliente {v.client_id}")
            prop_name   = props_map.get(v.property_id, "") if v.property_id else ""
            plot_name   = plots_map.get(v.plot_id, "") if v.plot_id else ""

            culture = v.culture or (v.planting.culture if getattr(v, "planting", None) else "")
            variety = v.variety or (v.planting.variety if getattr(v, "planting", None) else "")

            try:
                consultant_name = next((c["name"] for c in CONSULTANTS if c["id"] == v.consultant_id), "")
            except:
                consultant_name = ""

            fenologia_obs = v.fenologia_real or ""
            status = (v.status or "").strip()
            obs = (v.recommendation or "").strip()

            ws.append([
                br_date(v.date),
                client_name,
                prop_name,
                plot_name,
                consultant_name,
                culture or "",
                variety or "",
                fenologia_obs,
                status,
                obs,
            ])

            # 🎨 Zebra (alternando fundo)
            row_fill = zebra_fill if (row_idx % 2 == 0) else zebra_fill2

            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col)
                cell.border = border_data
                cell.fill = row_fill
                cell.alignment = left if col in (2, 3, 4, 10) else center

            # 🎨 Status com cor (coluna 9)
            st = (status or "").lower().strip()
            status_cell = ws.cell(row=row_idx, column=9)

            if st in ("planned", "planejada", "pendente"):
                status_cell.fill = status_planned
                status_cell.font = status_font_dark
            elif st in ("done", "realizada", "concluida", "concluída"):
                status_cell.fill = status_done
                status_cell.font = status_font_dark
            elif st in ("canceled", "cancelada", "cancelado"):
                status_cell.fill = status_canceled
                status_cell.font = status_font_light
            else:
                status_cell.font = Font(color="FFFFFF", bold=True)


        # ✅ filtro cobrindo até a última linha de dados
        last_row_visits = ws.max_row
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{last_row_visits}"

        # ==========================================================
        # 7) ABA PRODUTOS
        # ==========================================================
        ws2["A1"] = "Produtos aplicados nas visitas"
        ws2["A1"].font = title_font
        ws2["A2"] = "Período:"
        ws2["A2"].font = bold_font
        ws2["B2"] = period_label

        prod_headers = ["Data visita", "Cliente", "Produto", "Dose", "Unidade", "Data aplicação"]
        ws2_header_row = 4


        for i, h in enumerate(prod_headers, start=1):
            ws2.cell(row=ws2_header_row, column=i).value = h

        style_header(ws2, ws2_header_row, len(prod_headers))
        ws2.freeze_panes = "A5"

        prod_row = ws2_header_row
        for v in visits:
            client_name = clients_map.get(v.client_id, f"Cliente {v.client_id}")
            v_date = br_date(v.date)

            prods = getattr(v, "products", []) or []
            for p in prods:
                prod_row += 1
                ws2.append([
                    v_date,
                    client_name,
                    getattr(p, "product_name", "") or "",
                    getattr(p, "dose", "") or "",
                    getattr(p, "unit", "") or "",
                    br_date(getattr(p, "application_date", None)),
                ])

                row_fill = zebra_fill if (prod_row % 2 == 0) else zebra_fill2

                for col in range(1, len(prod_headers) + 1):
                    cell = ws2.cell(row=prod_row, column=col)
                    cell.border = border_data
                    cell.fill = row_fill
                    cell.alignment = left if col in (2, 3) else center


        # ✅ filtro cobrindo até a última linha de dados
        last_row_prod = ws2.max_row
        ws2.auto_filter.ref = f"A{ws2_header_row}:{get_column_letter(len(prod_headers))}{last_row_prod}"

        # ==========================================================
        # 8) Ajusta largura colunas
        # ==========================================================
        def autosize(sheet, max_col, min_w=12, max_w=44):
            for col in range(1, max_col + 1):
                letter = get_column_letter(col)
                max_len = 0
                for cell in sheet[letter]:
                    val = "" if cell.value is None else str(cell.value)
                    max_len = max(max_len, len(val))
                sheet.column_dimensions[letter].width = max(min_w, min(max_w, max_len + 2))

        autosize(ws, len(headers))
        autosize(ws2, len(prod_headers))

        # ==========================================================
        # 9) Exporta arquivo
        # ==========================================================
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        filename = f"relatorio_visitas_{start_date.isoformat()}_a_{end_date.isoformat()}.xlsx"
        return send_file(
            bio,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print("⚠️ erro report_monthly_xlsx:", e)
        return jsonify(error=str(e)), 500





@bp.route('/varieties', methods=['GET'])
def list_varieties():
    # opcional: filtrar por culture_id (mais seguro e rápido)
    culture_id = request.args.get("culture_id", type=int)

    q = Variety.query
    if culture_id:
        q = q.filter(Variety.culture_id == culture_id)

    rows = q.order_by(Variety.id.asc()).all()

    # devolve também o nome da cultura (útil no front)
    culture_map = {c.id: c.name for c in Culture.query.all()}

    return jsonify([
        {
            "id": v.id,
            "culture_id": v.culture_id,
            "culture": culture_map.get(v.culture_id, ""),
            "name": v.name,
        }
        for v in rows
    ]), 200


# ============================================================
# 👨‍🌾 CONSULTANTS — lista fixa (IDs estáveis 1..5)
# ============================================================
CONSULTANTS = [
    {"id": 1, "name": "Jhonatan"},
    {"id": 2, "name": "Felipe"},
    {"id": 3, "name": "Everton"},
    {"id": 4, "name": "Pedro"},
    {"id": 5, "name": "Alexandre"},
]

CONSULTANT_IDS = {c["id"] for c in CONSULTANTS}

@bp.route('/consultants', methods=['GET'])
def list_consultants():
    return jsonify(CONSULTANTS), 200


# ============================================================
# 🔵 Endpoint de teste usado pelo APK (detectar conexão real)
# ============================================================
@bp.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

def is_confirmation_reply(text: str) -> bool:
    if not text:
        return False

    value = text.strip().upper()
    return value == "NOVA" or value.isdigit()

@bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """
    Webhook inicial do Telegram.
    Nesta etapa:
    - recebe o payload bruto
    - normaliza a mensagem
    - interpreta texto/caption
    - busca cliente e pendências
    - envia resposta automática no Telegram
    """
    try:
        payload = request.get_json(silent=True) or {}

        chatbot_service = ChatbotService()
        chat_message = chatbot_service.normalize_telegram_update(payload)

        if not chat_message:
            return jsonify({
                "ok": True,
                "message": "update sem mensagem utilizável"
            }), 200

        message_text = (chat_message.text or chat_message.caption or "").strip()

        if not message_text:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="Recebi sua mensagem, mas ainda não consegui interpretar esse formato."
            )
            return jsonify({
                "ok": True,
                "message": "mensagem sem texto/caption"
            }), 200

        # =========================================================
        # Se a mensagem for resposta de confirmação (1, 2, NOVA),
        # tenta resolver usando o estado salvo da conversa
        # =========================================================
        if is_confirmation_reply(message_text):
            state = ChatbotConversationState.query.filter_by(
                platform="telegram",
                chat_id=chat_message.chat_id,
                status="awaiting_confirmation"
            ).first()

            if state:
                pending_visit_suggestions = json.loads(state.pending_visit_suggestions_json or "[]")
                visit_preview = json.loads(state.visit_preview_json or "{}")

                user_reply = message_text.strip().upper()

                if user_reply == "NOVA":
                    action = "create_new_visit"
                    selected_pending_visit = None
                    final_visit_payload = visit_preview
                elif user_reply.isdigit():
                    idx = int(user_reply) - 1

                    if idx < 0 or idx >= len(pending_visit_suggestions):
                        send_telegram_message(
                            chat_id=chat_message.chat_id,
                            text="Opção inválida. Responda com o número da visita ou NOVA."
                        )
                        return jsonify({
                            "ok": True,
                            "message": "opção inválida para confirmação"
                        }), 200

                    selected_pending_visit = pending_visit_suggestions[idx]
                    action = "use_existing_pending_visit"

                    final_visit_payload = {
                        **visit_preview,
                        "client_id": selected_pending_visit.get("client_id") or visit_preview.get("client_id"),
                        "property_id": selected_pending_visit.get("property_id") or visit_preview.get("property_id"),
                        "plot_id": selected_pending_visit.get("plot_id") or visit_preview.get("plot_id"),
                        "linked_pending_visit_id": selected_pending_visit.get("id"),
                    }
                else:
                    send_telegram_message(
                        chat_id=chat_message.chat_id,
                        text="Resposta inválida. Use um número ou NOVA."
                    )
                    return jsonify({
                        "ok": True,
                        "message": "resposta inválida"
                    }), 200

                # força done
                final_visit_payload["status"] = "done"

                if action == "use_existing_pending_visit":
                    pending_visit_id = final_visit_payload.get("linked_pending_visit_id")
                    visit = Visit.query.get(pending_visit_id)

                    if not visit:
                        send_telegram_message(
                            chat_id=chat_message.chat_id,
                            text="Não consegui localizar a visita pendente escolhida."
                        )
                        return jsonify({
                            "ok": True,
                            "message": "visita pendente não encontrada"
                        }), 200

                    if final_visit_payload.get("date"):
                        visit.date = _date.fromisoformat(final_visit_payload["date"])

                    visit.status = "done"
                    visit.culture = final_visit_payload.get("culture") or visit.culture
                    visit.variety = final_visit_payload.get("variety") or visit.variety
                    visit.fenologia_real = final_visit_payload.get("fenologia_real")
                    visit.recommendation = final_visit_payload.get("recommendation") or visit.recommendation
                    visit.consultant_id = final_visit_payload.get("consultant_id") or visit.consultant_id
                    visit.latitude = final_visit_payload.get("latitude")
                    visit.longitude = final_visit_payload.get("longitude")

                    if hasattr(visit, "source"):
                        visit.source = final_visit_payload.get("source", "chatbot")

                    db.session.commit()

                    state.status = "completed"
                    db.session.commit()

                    send_telegram_message(
                        chat_id=chat_message.chat_id,
                        text=f"Visita pendente atualizada com sucesso. ID da visita: {visit.id}"
                    )

                    return jsonify({
                        "ok": True,
                        "message": "confirmação processada com visita existente",
                        "visit": visit.to_dict()
                    }), 200

                if action == "create_new_visit":
                    if not final_visit_payload.get("client_id"):
                        send_telegram_message(
                            chat_id=chat_message.chat_id,
                            text="Não consegui criar a visita porque o cliente não foi identificado."
                        )
                        return jsonify({
                            "ok": True,
                            "message": "client_id ausente"
                        }), 200

                    visit_date = None
                    if final_visit_payload.get("date"):
                        visit_date = _date.fromisoformat(final_visit_payload["date"])

                    new_visit = Visit(
                        client_id=final_visit_payload.get("client_id"),
                        property_id=final_visit_payload.get("property_id"),
                        plot_id=final_visit_payload.get("plot_id"),
                        consultant_id=final_visit_payload.get("consultant_id"),
                        date=visit_date,
                        recommendation=final_visit_payload.get("recommendation") or "",
                        status="done",
                        culture=final_visit_payload.get("culture") or "",
                        variety=final_visit_payload.get("variety") or "",
                        fenologia_real=final_visit_payload.get("fenologia_real"),
                        latitude=final_visit_payload.get("latitude"),
                        longitude=final_visit_payload.get("longitude"),
                    )

                    if hasattr(new_visit, "source"):
                        new_visit.source = final_visit_payload.get("source", "chatbot")

                    db.session.add(new_visit)
                    db.session.commit()

                    state.status = "completed"
                    db.session.commit()

                    send_telegram_message(
                        chat_id=chat_message.chat_id,
                        text=f"Nova visita criada com sucesso. ID da visita: {new_visit.id}"
                    )

                    return jsonify({
                        "ok": True,
                        "message": "confirmação processada com nova visita",
                        "visit": new_visit.to_dict()
                    }), 201

        parsed = parse_chatbot_message(message_text)

        matched_client = find_client_by_name(parsed.get("client_name"))
        matched_property = find_property_by_name(
            parsed.get("property_name"),
            matched_client.id if matched_client else None
        )

        pending_visits = []
        same_culture_found = False

        if matched_client:
            pending_visits, same_culture_found = find_pending_visits(
                client_id=matched_client.id,
                property_id=matched_property.id if matched_property else None,
                culture=parsed.get("culture"),
                limit=5
            )

        suggestions = []
        for visit in pending_visits:
            suggestions.append({
                "id": visit.id,
                "date": visit.date.isoformat() if visit.date else None,
                "status": visit.status,
                "culture": visit.culture,
                "variety": visit.variety,
                "fenologia_real": visit.fenologia_real,
                "recommendation": (visit.recommendation or "").strip(),
                "client_id": visit.client_id,
                "property_id": visit.property_id,
                "plot_id": visit.plot_id,
                "display_text": visit.to_dict().get("display_text"),
            })

        if matched_client:
            confirmation_text = build_pending_visits_confirmation_text(
                client_name=matched_client.name,
                requested_culture=parsed.get("culture"),
                suggestions=suggestions,
                same_culture_found=same_culture_found
            )
        else:
            confirmation_text = (
                "Não consegui localizar o cliente informado.\n\n"
                "Tente enviar no formato:\n"
                "cliente NOME_CLIENTE fazenda NOME_FAZENDA cultura estágio observação"
            )

        visit_preview = {
            "client_id": matched_client.id if matched_client else None,
            "property_id": matched_property.id if matched_property else None,
            "plot_id": None,
            "consultant_id": 1,
            "date": parsed.get("date"),
            "status": parsed.get("status", "planned"),
            "culture": parsed.get("culture") or "",
            "variety": "",
            "fenologia_real": parsed.get("fenologia_real"),
            "recommendation": parsed.get("recommendation") or "",
            "products": [],
            "latitude": None,
            "longitude": None,
            "generate_schedule": False,
            "source": parsed.get("source", "chatbot"),
        }

        state = ChatbotConversationState.query.filter_by(
            platform="telegram",
            chat_id=chat_message.chat_id
        ).first()

        if not state:
            state = ChatbotConversationState(
                platform="telegram",
                chat_id=chat_message.chat_id,
            )
            db.session.add(state)

        state.last_message = message_text
        state.pending_visit_suggestions_json = json.dumps(suggestions, ensure_ascii=False)
        state.visit_preview_json = json.dumps(visit_preview, ensure_ascii=False)
        state.confirmation_text = confirmation_text
        state.status = "awaiting_confirmation"

        db.session.commit()   

        send_result = send_telegram_message(
            chat_id=chat_message.chat_id,
            text=confirmation_text
        )

        return jsonify({
            "ok": True,
            "telegram_summary": chatbot_service.build_internal_summary(chat_message),
            "parsed_message": parsed,
            "matched_client": matched_client.to_dict() if matched_client else None,
            "matched_property": matched_property.to_dict() if matched_property else None,
            "pending_visit_suggestions": suggestions,
            "same_culture_found": same_culture_found,
            "confirmation_text": confirmation_text,
            "send_result": send_result,
        }), 200

    except Exception as e:
        print(f"❌ Erro em /telegram/webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

def normalize_lookup_text(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def find_client_by_name(client_name: str):
    if not client_name:
        return None

    target = normalize_lookup_text(client_name)
    clients = Client.query.all()

    exact_match = None
    partial_match = None

    for client in clients:
        current = normalize_lookup_text(client.name)
        if current == target:
            exact_match = client
            break
        if target in current and partial_match is None:
            partial_match = client

    return exact_match or partial_match


def find_property_by_name(property_name: str, client_id: int = None):
    if not property_name:
        return None

    target = normalize_lookup_text(property_name)
    query = Property.query

    if client_id:
        query = query.filter_by(client_id=client_id)

    properties = query.all()

    exact_match = None
    partial_match = None

    for prop in properties:
        current = normalize_lookup_text(prop.name)
        if current == target:
            exact_match = prop
            break
        if target in current and partial_match is None:
            partial_match = prop

    return exact_match or partial_match


def find_pending_visits(
    client_id: int,
    property_id: int = None,
    culture: str = None,
    limit: int = 5
):
    """
    Busca visitas pendentes do cliente e, se houver, da propriedade.
    Retorna:
    - visits: lista de visitas
    - same_culture_found: se encontrou visitas da mesma cultura
    """
    base_query = Visit.query.filter(Visit.client_id == client_id)
    base_query = base_query.filter(Visit.status.in_(["planned", "pendente", "planejada", "planejado"]))

    if property_id:
        base_query = base_query.filter(Visit.property_id == property_id)

    if culture:
        same_culture = (
            base_query
            .filter(Visit.culture == culture)
            .order_by(Visit.date.asc().nullslast())
            .limit(limit)
            .all()
        )
        if same_culture:
            return same_culture, True

    fallback = (
        base_query
        .order_by(Visit.date.asc().nullslast())
        .limit(limit)
        .all()
    )
    return fallback, False


@bp.route('/chatbot/preview-visit', methods=['POST'])
def chatbot_preview_visit():
    """
    Recebe uma mensagem simples e devolve uma prévia
    do payload que no futuro será enviado para /api/visits.
    Ainda não salva nada no banco.
    """
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        consultant_id = data.get("consultant_id", 1)

        if not message:
            return jsonify({
                "ok": False,
                "error": "message is required"
            }), 400

        parsed = parse_chatbot_message(message)

        matched_client = find_client_by_name(parsed.get("client_name"))
        matched_property = find_property_by_name(
            parsed.get("property_name"),
            matched_client.id if matched_client else None
        )

        visit_payload = {
            "client_id": matched_client.id if matched_client else None,
            "property_id": matched_property.id if matched_property else None,
            "plot_id": None,
            "consultant_id": consultant_id,
            "date": parsed.get("date"),
            "status": parsed.get("status", "planned"),
            "culture": parsed.get("culture") or "",
            "variety": "",
            "fenologia_real": parsed.get("fenologia_real"),
            "recommendation": parsed.get("recommendation") or "",
            "products": [],
            "latitude": None,
            "longitude": None,
            "generate_schedule": False,
            "source": parsed.get("source", "chatbot"),
        }

        return jsonify({
            "ok": True,
            "parsed_message": parsed,
            "matched_entities": {
                "client": matched_client.to_dict() if matched_client else None,
                "property": matched_property.to_dict() if matched_property else None,
            },
            "visit_preview": visit_payload
        }), 200

    except Exception as e:
        print(f"❌ Erro em /chatbot/preview-visit: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

def build_pending_visits_confirmation_text(
    client_name: str,
    requested_culture: str,
    suggestions: list,
    same_culture_found: bool
) -> str:
    if not suggestions:
        return (
            f"Não encontrei visitas pendentes para {client_name or 'este cliente'}.\n\n"
            f"Responda com NOVA para criar uma nova visita."
        )

    lines = []

    if requested_culture and not same_culture_found:
        lines.append(
            f"Não encontrei visitas pendentes de {requested_culture} para {client_name or 'este cliente'}."
        )
        lines.append("")
        lines.append("Encontrei outras visitas pendentes deste cliente:")
    else:
        lines.append(f"Encontrei visitas pendentes para {client_name or 'este cliente'}:")

    for idx, item in enumerate(suggestions, start=1):
        culture = item.get("culture") or "—"
        recommendation = item.get("recommendation") or "—"
        date_value = item.get("date") or "sem data"
        lines.append(f"{idx}. {culture} - {recommendation} - {date_value}")

    lines.append("")
    lines.append("Responda com:")
    lines.append("- o número da visita que deseja realizar")
    lines.append("- ou NOVA para criar uma nova visita")

    return "\n".join(lines)

@bp.route('/chatbot/suggest-pending-visits', methods=['POST'])
def chatbot_suggest_pending_visits():
    """
    Recebe uma mensagem do chatbot, resolve cliente/propriedade
    e sugere visitas pendentes compatíveis para confirmação.
    Ainda não salva nada.
    """
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        consultant_id = data.get("consultant_id", 1)

        if not message:
            return jsonify({
                "ok": False,
                "error": "message is required"
            }), 400

        parsed = parse_chatbot_message(message)

        matched_client = find_client_by_name(parsed.get("client_name"))
        matched_property = find_property_by_name(
            parsed.get("property_name"),
            matched_client.id if matched_client else None
        )

        pending_visits = []
        same_culture_found = False

        if matched_client:
            pending_visits, same_culture_found = find_pending_visits(
                client_id=matched_client.id,
                property_id=matched_property.id if matched_property else None,
                culture=parsed.get("culture"),
                limit=5
            )

        visit_preview = {
            "client_id": matched_client.id if matched_client else None,
            "property_id": matched_property.id if matched_property else None,
            "plot_id": None,
            "consultant_id": consultant_id,
            "date": parsed.get("date"),
            "status": parsed.get("status", "planned"),
            "culture": parsed.get("culture") or "",
            "variety": "",
            "fenologia_real": parsed.get("fenologia_real"),
            "recommendation": parsed.get("recommendation") or "",
            "products": [],
            "latitude": None,
            "longitude": None,
            "generate_schedule": False,
            "source": parsed.get("source", "chatbot"),
        }

        suggestions = []
        for visit in pending_visits:
            suggestions.append({
                "id": visit.id,
                "date": visit.date.isoformat() if visit.date else None,
                "status": visit.status,
                "culture": visit.culture,
                "variety": visit.variety,
                "fenologia_real": visit.fenologia_real,
                "recommendation": (visit.recommendation or "").strip(),
                "client_id": visit.client_id,
                "property_id": visit.property_id,
                "plot_id": visit.plot_id,
                "display_text": visit.to_dict().get("display_text"),
            })

        confirmation_text = build_pending_visits_confirmation_text(
            client_name=matched_client.name if matched_client else parsed.get("client_name"),
            requested_culture=parsed.get("culture"),
            suggestions=suggestions,
            same_culture_found=same_culture_found
        )

        return jsonify({
            "ok": True,
            "parsed_message": parsed,
            "matched_entities": {
                "client": matched_client.to_dict() if matched_client else None,
                "property": matched_property.to_dict() if matched_property else None,
            },
            "visit_preview": visit_preview,
            "pending_visit_suggestions": suggestions,
            "needs_confirmation": True if suggestions else False,
            "same_culture_found": same_culture_found,
            "requested_culture": parsed.get("culture"),
            "confirmation_text": confirmation_text,
        }), 200

    except Exception as e:
        print(f"❌ Erro em /chatbot/suggest-pending-visits: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@bp.route('/chatbot/resolve-confirmation', methods=['POST'])
def chatbot_resolve_confirmation():
    """
    Recebe a resposta do usuário após a sugestão de visitas pendentes.
    Ainda não salva nada no banco.
    Apenas decide se:
    - usa uma visita pendente existente
    - ou cria uma nova visita
    """
    try:
        data = request.get_json(silent=True) or {}

        user_reply = (data.get("user_reply") or "").strip().upper()
        pending_visit_suggestions = data.get("pending_visit_suggestions") or []
        visit_preview = data.get("visit_preview") or {}

        if not user_reply:
            return jsonify({
                "ok": False,
                "error": "user_reply is required"
            }), 400

        if user_reply == "NOVA":
            return jsonify({
                "ok": True,
                "action": "create_new_visit",
                "selected_pending_visit": None,
                "final_visit_payload": visit_preview,
                "message": "Usuário optou por criar uma nova visita."
            }), 200

        if user_reply.isdigit():
            idx = int(user_reply) - 1

            if idx < 0 or idx >= len(pending_visit_suggestions):
                return jsonify({
                    "ok": False,
                    "error": "opção inválida"
                }), 400

            selected = pending_visit_suggestions[idx]

            merged_payload = {
                **visit_preview,
                "client_id": selected.get("client_id") or visit_preview.get("client_id"),
                "property_id": selected.get("property_id") or visit_preview.get("property_id"),
                "plot_id": selected.get("plot_id") or visit_preview.get("plot_id"),
                "linked_pending_visit_id": selected.get("id"),
            }

            return jsonify({
                "ok": True,
                "action": "use_existing_pending_visit",
                "selected_pending_visit": selected,
                "final_visit_payload": merged_payload,
                "message": f"Usuário escolheu a visita pendente #{user_reply}."
            }), 200

        return jsonify({
            "ok": False,
            "error": "resposta inválida. Use um número ou NOVA"
        }), 400

    except Exception as e:
        print(f"❌ Erro em /chatbot/resolve-confirmation: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@bp.route('/chatbot/commit-visit', methods=['POST'])
def chatbot_commit_visit():
    """
    Efetiva a visita no banco.
    - Se action == use_existing_pending_visit: atualiza a visita pendente escolhida e marca como done
    - Se action == create_new_visit: cria nova visita e marca como done
    """
    try:
        data = request.get_json(silent=True) or {}

        action = data.get("action")
        final_visit_payload = data.get("final_visit_payload") or {}
        selected_pending_visit = data.get("selected_pending_visit")

        if not action:
            return jsonify({
                "ok": False,
                "error": "action is required"
            }), 400

        if not final_visit_payload:
            return jsonify({
                "ok": False,
                "error": "final_visit_payload is required"
            }), 400

        # força status done
        final_visit_payload["status"] = "done"

        # =========================================================
        # 1) Atualizar visita pendente existente
        # =========================================================
        if action == "use_existing_pending_visit":
            pending_visit_id = final_visit_payload.get("linked_pending_visit_id")

            if not pending_visit_id:
                return jsonify({
                    "ok": False,
                    "error": "linked_pending_visit_id is required for use_existing_pending_visit"
                }), 400

            visit = Visit.query.get(pending_visit_id)
            if not visit:
                return jsonify({
                    "ok": False,
                    "error": "pending visit not found"
                }), 404

            # Atualizações principais
            if final_visit_payload.get("date"):
                visit.date = _date.fromisoformat(final_visit_payload["date"])

            visit.status = "done"
            visit.culture = final_visit_payload.get("culture") or visit.culture
            visit.variety = final_visit_payload.get("variety") or visit.variety
            visit.fenologia_real = final_visit_payload.get("fenologia_real")
            visit.recommendation = final_visit_payload.get("recommendation") or visit.recommendation
            visit.consultant_id = final_visit_payload.get("consultant_id") or visit.consultant_id
            visit.latitude = final_visit_payload.get("latitude")
            visit.longitude = final_visit_payload.get("longitude")

            # source só se a coluna existir no banco/model
            if hasattr(visit, "source"):
                visit.source = final_visit_payload.get("source", "chatbot")

            db.session.commit()

            return jsonify({
                "ok": True,
                "action": action,
                "message": "Visita pendente atualizada com sucesso.",
                "visit": visit.to_dict()
            }), 200

        # =========================================================
        # 2) Criar nova visita
        # =========================================================
        if action == "create_new_visit":
            if not final_visit_payload.get("client_id"):
                return jsonify({
                    "ok": False,
                    "error": "client_id is required to create a new visit"
                }), 400

            visit_date = None
            if final_visit_payload.get("date"):
                visit_date = _date.fromisoformat(final_visit_payload["date"])

            new_visit = Visit(
                client_id=final_visit_payload.get("client_id"),
                property_id=final_visit_payload.get("property_id"),
                plot_id=final_visit_payload.get("plot_id"),
                consultant_id=final_visit_payload.get("consultant_id"),
                date=visit_date,
                recommendation=final_visit_payload.get("recommendation") or "",
                status="done",
                culture=final_visit_payload.get("culture") or "",
                variety=final_visit_payload.get("variety") or "",
                fenologia_real=final_visit_payload.get("fenologia_real"),
                latitude=final_visit_payload.get("latitude"),
                longitude=final_visit_payload.get("longitude"),
            )

            if hasattr(new_visit, "source"):
                new_visit.source = final_visit_payload.get("source", "chatbot")

            db.session.add(new_visit)
            db.session.commit()

            return jsonify({
                "ok": True,
                "action": action,
                "message": "Nova visita criada com sucesso.",
                "visit": new_visit.to_dict()
            }), 201

        return jsonify({
            "ok": False,
            "error": "invalid action"
        }), 400

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro em /chatbot/commit-visit: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# ============================================================
# 🌱 VISITS ENDPOINTS
# ============================================================

@bp.route('/visits', methods=['GET'])
def get_visits():
    """
    Rota unificada:
    - ?month=current → modo iOS (visitas só do mês)
    - ?scope=all → retorna todas as visitas (usado no Acompanhamentos/Calendar)
    - sem params → retorna visitas com filtros normais
    """
    from datetime import date

    try:
        month = request.args.get("month")
        scope = request.args.get("scope")

        # ============================================
        # 🍏 iOS → apenas visitas do mês atual
        # ============================================
        if month == "current":
            today = date.today()
            visits = (
                Visit.query
                .filter(db.extract('month', Visit.date) == today.month)
                .filter(db.extract('year', Visit.date) == today.year)
                .order_by(Visit.date.asc())
                .all()
            )

        # ============================================
        # 🔵 Acompanhamentos / Calendar Desktop → all
        # ============================================
        elif scope == "all":
            visits = Visit.query.order_by(Visit.date.asc().nullslast()).all()

        # ============================================
        # 🔧 Filtros normais (client_id, talhão, etc.)
        # ============================================
        else:
            client_id = request.args.get('client_id', type=int)
            property_id = request.args.get('property_id', type=int)
            plot_id = request.args.get('plot_id', type=int)
            consultant_id = request.args.get('consultant_id', type=int)
            status = request.args.get('status', type=str)

            q = Visit.query
            if client_id:
                q = q.filter_by(client_id=client_id)
            if property_id:
                q = q.filter_by(property_id=property_id)
            if plot_id:
                q = q.filter_by(plot_id=plot_id)
            if consultant_id:
                q = q.filter_by(consultant_id=consultant_id)

            visits = q.order_by(Visit.date.asc().nullslast()).all()

        # ============================================
        # 📸 Montagem final da resposta (unificada)
        # ============================================
        result = []
        backend_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com"

        for v in visits:
            client = Client.query.get(v.client_id)
            consultant_name = next(
                (c["name"] for c in CONSULTANTS if c["id"] == v.consultant_id),
                None
            )

            photos = []
            for p in v.photos:
                file_name = os.path.basename(p.url)
                photos.append({
                    "id": p.id,
                    "url": resolve_photo_url(p.url),
                    "caption": p.caption or ""
                })

            culture = v.culture or (v.planting.culture if v.planting else "—")
            variety = v.variety or (v.planting.variety if v.planting else "—")

            d = v.to_dict()

            # 🔥 Sobrescreve SEMPRE com o valor real, mesmo se vazio
            d["fenologia_real"] = v.fenologia_real or ""

            # 🔥 ADICIONAR LISTA DE PRODUTOS DA VISITA
            d["products"] = [p.to_dict() for p in v.products]

            # Ajustes finais
            d["client_name"] = client.name if client else f"Cliente {v.client_id}"
            d["consultant_name"] = consultant_name or "—"
            d["culture"] = culture
            d["variety"] = variety
            d["photos"] = photos

            result.append(d)


        return jsonify(result), 200

    except Exception as e:
        print(f"⚠️ Erro ao listar visitas: {e}")
        return jsonify(error=str(e)), 500





@bp.route('/visits', methods=['POST'])
def create_visit():
    """
    Cria uma nova visita.
    Se 'generate_schedule' for True, gera automaticamente o cronograma fenológico
    com base na cultura e na data de plantio.
    """
    from datetime import date as _d, timedelta
    data = request.get_json(silent=True) or {}

    client_id = data.get('client_id')
    property_id = data.get('property_id')
    plot_id = data.get('plot_id')
    consultant_id = data.get('consultant_id')
    status = (data.get('status') or 'planned').strip().lower()
    gen_schedule = bool(data.get('generate_schedule'))
    culture = (data.get('culture') or '').strip() or None
    variety = (data.get('variety') or '').strip() or None
    date_str = data.get('date')
    recommendation = (data.get('recommendation') or '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    fenologia_real = data.get("fenologia_real")


    # ========================
    # ✅ VALIDAÇÕES BÁSICAS
    # ========================
    if not client_id:
        return jsonify(message="client_id é obrigatório"), 400
    if not Client.query.get(client_id):
        return jsonify(message="cliente não encontrado"), 404
    if property_id and not Property.query.get(property_id):
        return jsonify(message="propriedade não encontrada"), 404
    if plot_id and not Plot.query.get(plot_id):
        return jsonify(message="talhão não encontrado"), 404
    if consultant_id and int(consultant_id) not in {c["id"] for c in CONSULTANTS}:
        return jsonify(message="consultor não encontrado"), 404

    try:
        visit_date = _d.fromisoformat(date_str)
    except Exception:
        return jsonify(message="data inválida, esperado formato YYYY-MM-DD"), 400

    # ======================================================
    # 🌾 GERAÇÃO AUTOMÁTICA DO CRONOGRAMA FENOLÓGICO
    # ======================================================
    from models import PhenologyStage

    p = None
    if gen_schedule:
        if not culture or not variety:
            return jsonify(message="culture e variety são obrigatórios quando gerar cronograma"), 400

        # ✅ Cria o registro de plantio — mesmo que não haja talhão
        if not plot_id:
            p = Planting(
                plot_id=None,
                culture=culture,
                variety=variety,
                planting_date=visit_date
            )
            db.session.add(p)
            db.session.flush()
        else:
            p = Planting(
                plot_id=plot_id,
                culture=culture,
                variety=variety,
                planting_date=visit_date
            )
            db.session.add(p)
            db.session.flush()


        # Visita inicial (plantio)
        v0 = Visit(
            client_id=client_id,
            property_id=property_id or None,
            plot_id=plot_id or None,
            planting_id=p.id if p else None,
            consultant_id=consultant_id,
            date=visit_date,
            recommendation="Plantio",
            status=status,
            culture=culture,
            variety=variety,
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(v0)

        # Gera visitas futuras conforme fenologia
        stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days.asc()).all()
        if culture.lower() == "soja":
            stages = [s for s in stages if "maturação fisiológica" not in s.name.lower()]

        for st in stages:
            if st.days == 0 or "plantio" in st.name.lower():
                continue

            fut_date = visit_date + timedelta(days=int(st.days))
            vv = Visit(
                client_id=client_id,  # garante o vínculo com o mesmo cliente
                property_id=property_id,  # idem para fazenda
                plot_id=plot_id,  # idem para talhão
                planting_id=p.id if p else None,
                consultant_id=consultant_id or v0.consultant_id,  # fallback seguro
                date=fut_date,
                recommendation=st.name.strip().capitalize(),
                status='planned',
                culture=culture,
                variety=variety,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(vv)


        db.session.commit()
        return jsonify(message="visita criada com cronograma", visit=v0.to_dict()), 201

    # ======================================================
    # 🌱 VISITA NORMAL (SEM CRONOGRAMA)
    # ======================================================
    v = Visit(
        client_id=client_id,
        property_id=property_id or None,
        plot_id=plot_id or None,
        consultant_id=consultant_id,
        date=visit_date,
        checklist=data.get('checklist'),
        diagnosis=data.get('diagnosis'),
        recommendation=recommendation,
        status=status,
        culture=culture,
        variety=variety,
        latitude=latitude,
        longitude=longitude,
        fenologia_real=fenologia_real
    )

    # 🌿 Preenche cultura e variedade a partir do plantio, se não vierem do frontend
    if not v.culture and v.plot_id:
        planting = Planting.query.filter_by(plot_id=v.plot_id).order_by(Planting.id.desc()).first()
        if planting:
            v.culture = planting.culture
            v.variety = planting.variety

    
    # ===========================================
    # 🌿 SALVAR PRODUTOS NA CRIAÇÃO DA VISITA
    # ===========================================
    products = data.get("products", [])
    from models import VisitProduct

    for p in products:
        vp = VisitProduct(
            visit_id=v.id,
            product_name=p.get("product_name", ""),
            dose=p.get("dose", ""),
            unit=p.get("unit", ""),
            application_date=(
                datetime.strptime(p["application_date"], "%Y-%m-%d")
                if p.get("application_date")
                else None
            ),
        )
        db.session.add(vp)


    db.session.add(v)
    db.session.commit()
    return jsonify(message="visita criada", visit=v.to_dict()), 201




@bp.route('/visits/<int:visit_id>/pdf', methods=['GET'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com"])
def export_visit_pdf(visit_id):
    """
    📄 Gera um PDF cumulativo moderno:
    - Capa estilizada
    - Visitas do ciclo
    - Layout centralizado
    - Fotos com compressão inteligente
    """

    # =====================================================
    # 🔎 BUSCA DADOS PRINCIPAIS
    # =====================================================
    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    property_ = Property.query.get(visit.property_id) if visit.property_id else None
    plot = Plot.query.get(visit.plot_id) if visit.plot_id else None

    consultant_name = next(
        (c["name"] for c in CONSULTANTS if c["id"] == visit.consultant_id),
        f"Consultor {visit.consultant_id}" if visit.consultant_id else ""
    )

    # =====================================================
    # 🔎 BUSCA TODAS AS VISITAS DO CICLO
    # =====================================================
    if visit.planting_id:
        visits_to_include = (
            Visit.query.filter(Visit.planting_id == visit.planting_id)
            .order_by(Visit.date.desc()).all()
        )
    else:
        visits_to_include = (
            Visit.query.filter(
                Visit.client_id == visit.client_id,
                Visit.property_id == visit.property_id,
                Visit.plot_id == visit.plot_id,
                Visit.culture == visit.culture,
            )
            .order_by(Visit.date.desc()).all()
        )

    # =====================================================
    # 🔎 FILTRO DE VISITAS COM FOTOS
    # =====================================================
    uploads_dir = ...
    filtered = []
    for v in visits_to_include:
        valid = [p for p in getattr(v, "photos", []) if getattr(p, "url", None)]
        if valid:
            v._valid_photos = valid
            filtered.append(v)

    visits_to_include = filtered

    # ✅ corta visitas (o PDF cumulativo é o que mais pesa)
    visits_to_include = visits_to_include[:MAX_VISITS]




    # =====================================================
    # ✅ PRESERVAR QUEBRA DE LINHA NAS OBSERVAÇÕES
    # =====================================================
    def nl2br(text: str) -> str:
        if not text:
            return ""
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = html_escape(t)  # evita quebrar markup no Paragraph
        return t.replace("\n", "<br/>")

    # =====================================================
    # 🖼️ LOGOS (rodapé em todas as páginas)
    # =====================================================
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    nutriverde_logo_path = os.path.join(static_dir, "nutriverde_logo_pdf.png")

    def slugify_variety(name: str) -> str:
        if not name:
            return ""
        s = unicodedata.normalize("NFD", name)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # remove acento
        s = s.strip().lower()
        s = re.sub(r"\s+", "_", s)          # espaços -> _
        s = re.sub(r"[^a-z0-9_]+", "", s)   # limpa resto
        return s

    variety_slug = slugify_variety(visit.variety or "")
    variety_logo_path = os.path.join(static_dir, "variety_logos", f"{variety_slug}.png")

    def draw_footer(canvas, doc):
        canvas.saveState()

        y = 22
        pad = 50

        # Logo Variedade (esquerda) — menor
        if variety_slug and os.path.exists(variety_logo_path):
            try:
                img = PILImage.open(variety_logo_path)
                aspect = img.height / float(img.width)
                w = 110
                h = w * aspect
                x = pad
                canvas.drawImage(variety_logo_path, x, y, width=w, height=h, mask="auto")
            except:
                pass

        # Logo Nutriverde (direita) — maior
        if os.path.exists(nutriverde_logo_path):
            try:
                img = PILImage.open(nutriverde_logo_path)
                aspect = img.height / float(img.width)
                w = 70
                h = w * aspect
                x = A4[0] - pad - w
                canvas.drawImage(nutriverde_logo_path, x, y, width=w, height=h, mask="auto")
            except:
                pass

        canvas.restoreState()

    # =====================================================
    # 📝 PREPARAÇÃO DO PDF
    # =====================================================
    buffer = BytesIO()

    # ✅ rastrear arquivos temporários para apagar no final
    temp_jpgs = []


    def smart_params(total_photos_all: int):
        # Mais agressivo pra não matar o worker
        if total_photos_all <= 4:  return (1280, 75)
        if total_photos_all <= 8:  return (1200, 70)
        if total_photos_all <= 16: return (1100, 62)
        return (1000, 55)

    def download_to_temp(url: str, timeout=20, max_bytes=12_000_000):
        """
        Baixa a imagem para arquivo temporário com limite em bytes (MB).
        - Primeiro tenta validar pelo Content-Length (quando existe)
        - Se não tiver, conta bytes no stream.
        """
        tmp = None
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout) as r:
                # ✅ 1) Se o servidor enviar Content-Length, valida antes
                try:
                    cl = r.headers.get("Content-Length")
                    if cl and int(cl) > max_bytes:
                        return None
                except:
                    pass

                # ✅ 2) Baixa contando bytes (vale para Content-Length ausente)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
                total = 0

                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        tmp.close()
                        try:
                            os.remove(tmp.name)
                        except:
                            pass
                        return None
                    tmp.write(chunk)

                tmp.close()
                return tmp.name

        except Exception:
            # garante limpeza se algo falhar no meio
            try:
                if tmp and tmp.name:
                    tmp.close()
                    os.remove(tmp.name)
            except:
                pass
            return None

    def compress_to_jpeg_temp(src_path: str, max_px: int, quality: int):
        """
        Converte pra JPEG comprimido em /tmp e devolve o path final.
        """
        try:
            img = PILImage.open(src_path)
            img = ImageOps.exif_transpose(img)

            # thumbnail já reduz, sem explodir tanto RAM quanto load() + resize bruto
            img.thumbnail((max_px, max_px), PILImage.LANCZOS)

            out = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            out_path = out.name
            out.close()

            img.convert("RGB").save(out_path, "JPEG", optimize=True, quality=quality)
            try:
                img.close()
            except:
                pass
            return out_path
        except Exception:
            return None
        finally:
            # sempre remove o bruto baixado
            try:
                os.remove(src_path)
            except:
                pass


    def draw_dark_background(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#101010"))
        canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)
        canvas.restoreState()
        draw_footer(canvas, doc)

    def draw_cover_background(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0E0E0E"))
        canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)

        canvas.setFillColor(colors.HexColor("#00E676"))
        canvas.rect(0, 0, 28, A4[1], fill=True, stroke=False)
        canvas.restoreState()
        draw_footer(canvas, doc)

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=50, rightMargin=40,
        topMargin=60, bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # =====================================================
    # 🎨 ESTILOS PERSONALIZADOS
    # =====================================================
    styles.add(ParagraphStyle(
        name="VisitTitleSmall",
        fontSize=12, leading=14, alignment=TA_CENTER,
        textColor=colors.HexColor("#BBF7D0"), spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name="VisitStageBig",
        fontSize=22, leading=26, alignment=TA_CENTER,
        textColor=colors.HexColor("#FFFFFF"), spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name="VisitDateCenter",
        fontSize=12, leading=14, alignment=TA_CENTER,
        textColor=colors.HexColor("#E0E0E0"), spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name="VisitSectionLabel",
        fontSize=14, leading=16, alignment=TA_CENTER,
        textColor=colors.HexColor("#A5D6A7"), spaceBefore=10, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="VisitSectionValue",
        fontSize=16, leading=20, alignment=TA_CENTER,
        textColor=colors.HexColor("#FFFFFF"), spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name="HrLine",
        alignment=TA_CENTER, fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceBefore=10, spaceAfter=16
    ))
    styles.add(ParagraphStyle(
        name="Caption",
        alignment=TA_CENTER, fontSize=9,
        textColor=colors.HexColor("#BDBDBD"),
        spaceBefore=4, spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        alignment=TA_CENTER, fontSize=9,
        textColor=colors.HexColor("#9E9E9E"),
        spaceBefore=20
    ))

    # =====================================================
    # 📘 CAPA COMPLETA
    # =====================================================
    story = []
    story.append(Spacer(1, 80))

    title_style = ParagraphStyle(
        name="CoverTitle",
        fontSize=22, leading=26, alignment=TA_CENTER,
        textColor=colors.HexColor("#E0F2F1"), spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        name="CoverSubtitle",
        fontSize=14, leading=18, alignment=TA_CENTER,
        textColor=colors.HexColor("#80CBC4"), spaceAfter=25
    )

    story.append(Paragraph("RELATÓRIO TÉCNICO DE", title_style))
    story.append(Paragraph("ACOMPANHAMENTO", title_style))
    story.append(Paragraph("Ciclo Fenológico", subtitle_style))

    client_style = ParagraphStyle(
        name="ClientBig",
        fontSize=22, leading=28, alignment=TA_CENTER,
        textColor=colors.HexColor("#FFFFFF"), spaceAfter=35
    )
    story.append(Paragraph((client.name or "Cliente").strip(), client_style))

    # Logo do PDF (NutriCRM)
    try:
        logo_path = os.path.join(static_dir, "nutricrm_logo_pdf.png")
        if os.path.exists(logo_path):
            img = PILImage.open(logo_path)
            aspect = img.height / float(img.width)
            width = 160
            story.append(Image(logo_path, width=width, height=width * aspect))
            story.append(Spacer(1, 20))
    except:
        pass

    info_label = ParagraphStyle(
        name="InfoLabel", fontSize=12, alignment=TA_LEFT,
        textColor=colors.HexColor("#A5D6A7")
    )
    info_value = ParagraphStyle(
        name="InfoValue", fontSize=12, alignment=TA_LEFT,
        textColor=colors.HexColor("#E0E0E0"), spaceAfter=6
    )

    def add_info(label, value):
        if value:
            story.append(Paragraph(label, info_label))
            story.append(Paragraph(str(value), info_value))

    add_info("Propriedade:", property_.name if property_ else "")
    add_info("Talhão:", plot.name if plot else "")
    add_info("Cultura:", visit.culture or "")
    add_info("Variedade:", visit.variety or "")
    add_info("Consultor:", consultant_name or "")

    if visits_to_include:
        start_date = visits_to_include[-1].date.strftime("%d/%m/%Y")  # mais antigo
        end_date   = visits_to_include[0].date.strftime("%d/%m/%Y")   # mais recente
    else:
        start_date = end_date = visit.date.strftime("%d/%m/%Y")


    add_info("Período de acompanhamento:", f"{start_date} → {end_date}")

    story.append(Spacer(1, 40))
    story.append(PageBreak())



    # =====================================================
    # 🟢 VISITAS (ORDEM AJUSTADA)
    # =====================================================
    total_visits = len(visits_to_include)
    for pos, v in enumerate(visits_to_include):  # pos começa em 0
        idx = total_visits - pos                 # 4,3,2,1 (ou 5,4,3,2,1)


        story.append(Paragraph(f"VISITA {idx}", styles["VisitTitleSmall"]))
        story.append(Paragraph(v.fenologia_real or "—", styles["VisitStageBig"]))

        try:
            dtext = v.date.strftime("%d/%m/%Y")
        except:
            dtext = str(v.date)
        story.append(Paragraph(dtext, styles["VisitDateCenter"]))

        story.append(Spacer(1, 20))

        if v.recommendation:
            story.append(Paragraph("Observações", styles["VisitSectionLabel"]))
            story.append(Paragraph(nl2br(v.recommendation), styles["VisitSectionValue"]))

        story.append(Paragraph("<hr/>", styles["HrLine"]))

        photos = list(getattr(v, "_valid_photos", []) or [])
        if photos:
            # 🔻 limita fotos por visita (economia RAM)
            photos = photos[:MAX_PHOTOS_V]
            total = len(photos)

            cols = 1 if total <= 3 else (2 if total <= 6 else 3)
            max_width = 220 if cols == 1 else 160
            col_width = (A4[0] - 100) / cols

            # total global (para decidir compressão)
            total_all = sum(
                min(len(getattr(x, "photos", []) or []), MAX_PHOTOS_V)
                for x in visits_to_include
            )
            max_px, quality = smart_params(total_all)

            row = []
            count = 0

            for i, photo in enumerate(photos, 1):
                photo_url = resolve_photo_url(photo.url)
                if not photo_url:
                    continue

                try:
                    # 1) baixa pra temp
                    src_path = download_to_temp(photo_url, timeout=20, max_bytes=12_000_000)
                    if not src_path:
                        print(f"⚠️ PDF: download bloqueado/maior que limite url={photo_url}")
                        continue

                    # 2) comprime pra jpeg em temp
                    jpg_path = compress_to_jpeg_temp(src_path, max_px=max_px, quality=quality)
                    if not jpg_path:
                        print(f"⚠️ PDF: falha compress url={photo_url}")
                        continue

                    temp_jpgs.append(jpg_path)


                    # 3) pegar aspect
                    probe = PILImage.open(jpg_path)
                    w, h = probe.size
                    try:
                        probe.close()
                    except:
                        pass

                    aspect = (h / w) if w else 1

                    # 4) passa PATH pro ReportLab
                    img_obj = Image(jpg_path, width=max_width, height=max_width * aspect)

                    # caption
                    base_caption = getattr(photo, "caption", "") or ""
                    lat = getattr(photo, "latitude", None)
                    lon = getattr(photo, "longitude", None)

                    gps_caption = ""
                    if lat is not None and lon is not None:
                        gps_caption = f"📍 {lat:.5f}, {lon:.5f}"

                    final_caption = html_escape(base_caption)
                    if gps_caption:
                        final_caption += f"<br/><small>{html_escape(gps_caption)}</small>"


                    caption_par = Paragraph(final_caption, styles["Caption"])

                    row.append([img_obj, caption_par])
                    count += 1

                    if count == cols or i == total:
                        story.append(
                            Table(
                                [row],
                                colWidths=[col_width] * len(row),
                                hAlign="CENTER",
                                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")])
                            )
                        )
                        story.append(Spacer(1, 14))
                        row = []
                        count = 0


                except Exception as e:
                    print(f"⚠️ PDF: erro processando url={photo_url} erro={e}")
                    continue


            # ✅ AQUI É O LUGAR CERTO (fora do for das fotos)
            if pos < total_visits - 1:
                story.append(PageBreak())       

    # Rodapé texto final
    story.append(Paragraph("<b>NutriCRM</b>", styles["Footer"]))
    story.append(Paragraph("Relatório cumulativo — ciclo fenológico", styles["Footer"]))

    doc.build(story, onFirstPage=draw_cover_background, onLaterPages=draw_dark_background)
    buffer.seek(0)

    # ✅ limpa temporários do /tmp
    for p in temp_jpgs:
        try:
            os.remove(p)
        except:
            pass

    filename = f"{client.name if client else 'Cliente'} - {visit.variety or ''} - Relatório.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)










@bp.route('/visits/bulk', methods=['POST'])
def create_visits_bulk():
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    created = []

    for it in items:
        client_id = it.get('client_id')
        property_id = it.get('property_id')
        plot_id = it.get('plot_id')
        consultant_id = it.get('consultant_id')
        status = (it.get('status') or 'planned').strip().lower()

        if not (client_id and property_id and plot_id and it.get('date')):
            continue

        if not Client.query.get(client_id): continue
        if not Property.query.get(property_id): continue
        if not Plot.query.get(plot_id): continue
        if consultant_id and int(consultant_id) not in CONSULTANT_IDS: continue

        try:
            from datetime import date as _d
            visit_date = _d.fromisoformat(it['date'])
        except Exception:
            continue

        v = Visit(
            client_id=client_id,
            property_id=property_id,
            plot_id=plot_id,
            consultant_id=consultant_id,
            date=visit_date,
            checklist=None,
            diagnosis=None,
            recommendation=it.get('recommendation'),
            status=status
        )
        db.session.add(v)
        created.append(v)

    db.session.commit()
    return jsonify([v.to_dict() | {"status": v.status} for v in created]), 201



@bp.route('/visits/<int:visit_id>', methods=['PUT'])
def update_visit(visit_id: int):
    v = Visit.query.get(visit_id)
    if not v:
        return jsonify(message='visit not found'), 404

    data = request.get_json(silent=True) or {}
    print("📩 PAYLOAD RECEBIDO NO PUT:", data)

    # Campos simples
    for tf in ('checklist','diagnosis','fenologia_real'):
        if tf in data:
            setattr(v, tf, data[tf])

    if "recommendation" in data:
        rec = data.get("recommendation")
        if rec not in (None, "", " "):
            v.recommendation = rec.strip()

    if 'client_id' in data and data['client_id']:
        if not Client.query.get(data['client_id']): 
            return jsonify(message='client not found'), 404
        v.client_id = data['client_id']

    if 'property_id' in data and data['property_id']:
        if not Property.query.get(data['property_id']): 
            return jsonify(message='property not found'), 404
        v.property_id = data['property_id']

    if 'plot_id' in data and data['plot_id']:
        if not Plot.query.get(data['plot_id']): 
            return jsonify(message='plot not found'), 404
        v.plot_id = data['plot_id']

    if 'consultant_id' in data:
        cid = data['consultant_id']
        if cid and int(cid) not in CONSULTANT_IDS:
            return jsonify(message='consultant not found'), 404
        v.consultant_id = cid

    if data.get("preserve_date"):
        data["date"] = v.date.isoformat() if v.date else None

    if 'date' in data:
        if not data['date']:
            v.date = None
        else:
            try:
                from datetime import date as _d
                v.date = _d.fromisoformat(data['date'])
            except Exception:
                return jsonify(message='invalid date, expected YYYY-MM-DD'), 400

    if 'status' in data and data['status']:
        v.status = data['status'].strip().lower()

    print("🧠 Atualizando visita", visit_id, "com dados:", data)

    # ✅ PRODUTOS
    if "products" in data:
        from models import VisitProduct
        VisitProduct.query.filter_by(visit_id=visit_id).delete()
        for p in data["products"]:
            vp = VisitProduct(
                visit_id=visit_id,
                product_name=p.get("product_name", ""),
                dose=p.get("dose", ""),
                unit=p.get("unit", ""),
                application_date=(
                    datetime.strptime(p["application_date"], "%Y-%m-%d")
                    if p.get("application_date") else None
                ),
            )
            db.session.add(vp)

    db.session.commit()
    return jsonify(message='visit updated', visit=v.to_dict() | {"status": v.status}), 200




@bp.route('/visits/<int:visit_id>', methods=['DELETE'])
def delete_visit(visit_id):
    """
    Exclui uma visita. Se for a visita de plantio, remove também o plantio e TODAS
    as visitas geradas automaticamente (fenológicas) vinculadas ao mesmo plantio_id.
    """
    try:
        visit = Visit.query.get(visit_id)
        if not visit:
            print(f"⚠️ Visita {visit_id} não encontrada.")
            return jsonify({'error': 'Visita não encontrada'}), 404

        print(f"🗑 Solicitada exclusão da visita {visit_id}: {visit.recommendation}")

        # ✅ Detecção mais robusta de plantio
        rec = (visit.recommendation or "").lower()
        is_plantio = ("plantio" in rec) or (visit.planting_id is not None)

        if is_plantio:
            planting = Planting.query.get(visit.planting_id) if visit.planting_id else None

            # 1) Se tiver planting_id, apaga todas as visitas vinculadas (SEM filtro de data)
            if planting:
                linked_visits = Visit.query.filter(
                    Visit.planting_id == planting.id,
                    Visit.id != visit.id
                ).all()

                for lv in linked_visits:
                    print(f"   → Removendo visita vinculada {lv.id} ({lv.recommendation})")
                    db.session.delete(lv)

                print(f"🌾 Removendo plantio {planting.id} vinculado.")
                db.session.delete(planting)

            else:
                # 2) Fallback: sem planting_id, apaga "todas do mesmo contexto"
                #    (se você tiver plot_id, USE ELE! É o melhor vínculo do talhão)
                q = Visit.query.filter(
                    Visit.id != visit.id,
                    Visit.client_id == visit.client_id,
                    Visit.property_id == visit.property_id,
                    Visit.culture == visit.culture
                )

                # Se existir plot_id no seu model, habilite essa linha (recomendado):
                if getattr(visit, "plot_id", None):
                    q = q.filter(Visit.plot_id == visit.plot_id)

                linked_visits = q.all()

                for lv in linked_visits:
                    print(f"   → Removendo visita relacionada {lv.id} ({lv.recommendation})")
                    db.session.delete(lv)

            # 3) Por fim, remove a visita de plantio
            db.session.delete(visit)
            db.session.commit()
            print("✅ Plantio e visitas vinculadas excluídos com sucesso.")
            return jsonify({'message': 'Plantio e visitas vinculadas excluídos com sucesso'}), 200

        # Caso comum (visita isolada)
        print(f"🧾 Excluindo visita isolada {visit_id}")
        db.session.delete(visit)
        db.session.commit()
        print(f"✅ Visita {visit_id} excluída com sucesso.")
        return jsonify({'message': 'Visita excluída com sucesso'}), 200

    except Exception as e:
        print(f"❌ Erro interno ao excluir visita {visit_id}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Erro interno ao excluir visita: {str(e)}'}), 500






# ==============================
# 📸 FOTOS — upload, legenda, exclusão (REVISADO)
# ==============================

@bp.route('/visits/<int:visit_id>/photos', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com"])
def upload_photos(visit_id):
    """Upload de múltiplas fotos com legendas (captions) — agora no Cloudflare R2."""
    visit = Visit.query.get_or_404(visit_id)

    # ✅ Modo leve por padrão (evita SIGKILL)
    # /pdf?mode=full -> tenta completo (ainda com limites)
    mode = (request.args.get("mode") or "lite").lower()

    # Limites seguros (você pode ajustar)
    MAX_VISITS   = int(request.args.get("max_visits") or (8 if mode == "lite" else 20))
    MAX_PHOTOS_V = int(request.args.get("max_photos") or (4 if mode == "lite" else 8))


    files = request.files.getlist('photos')
    captions = request.form.getlist('captions')

    if not files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    # ✅ R2 envs
    bucket = os.environ.get("R2_BUCKET")
    public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")

    if not bucket or not public_base:
        return jsonify({"error": "R2 não configurado: faltam variáveis de ambiente"}), 500

    r2 = get_r2_client()

    saved = []

    for i, file in enumerate(files):
        # 🔥 nome único
        unique = uuid.uuid4().hex
        original = secure_filename(file.filename or "foto.jpg")

        # (opcional) força extensão .jpg se vier sem
        if "." not in original:
            original = f"{original}.jpg"

        key = f"visits/{visit_id}/{unique}_{original}"

        # ✅ upload direto pro R2 (sem usar disco do Render)
        r2.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": file.mimetype or "image/jpeg",
                # Se quiser cache agressivo depois, dá pra adicionar CacheControl aqui
            },
        )

        caption = captions[i] if i < len(captions) else ""

        url = f"{public_base}/{key}"

        photo = Photo(
            visit_id=visit_id,
            url=url,
            caption=caption
        )
        db.session.add(photo)
        db.session.flush()

        saved.append({
            "id": photo.id,
            "url": url,
            "caption": caption or ""
        })

    db.session.commit()

    return jsonify({
        "message": f"{len(saved)} foto(s) salvas.",
        "photos": saved
    }), 201



@bp.route('/visits/<int:visit_id>/photos', methods=['GET'])
def list_photos(visit_id):
    visit = Visit.query.get_or_404(visit_id)

    photos = []
    for p in (visit.photos or []):
        photos.append({
            "id": p.id,
            "url": resolve_photo_url(p.url),  # ✅ devolve R2 se já for R2
            "caption": p.caption or ""
        })

    return jsonify(photos), 200




@bp.route('/photos/<int:photo_id>', methods=['PUT', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com"])
def update_photo_caption(photo_id):
    """
    Atualiza a legenda de uma foto específica.
    """
    try:
        data = request.get_json() or {}
        caption = data.get("caption", "").strip()

        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({"error": "Foto não encontrada"}), 404

        photo.caption = caption
        db.session.commit()  # ✅ garante persistência

        print(f"📝 Legenda atualizada -> Foto {photo_id}: {caption}")
        return jsonify({"success": True, "caption": caption}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao atualizar legenda da foto {photo_id}: {e}")
        return jsonify({"error": str(e)}), 500




@bp.route('/photos/<int:photo_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com"])
def delete_single_photo(photo_id):
    """Exclui uma foto específica do banco e do disco."""
    photo = Photo.query.get_or_404(photo_id)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(photo.url)
        filename = os.path.basename(parsed.path)
        file_path = os.path.join(UPLOAD_DIR, filename)

        if os.path.exists(file_path):
            os.remove(file_path)

        db.session.delete(photo)
        db.session.commit()
        return jsonify({"message": "Foto excluída com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao excluir foto: {e}")
        return jsonify({"error": f"Erro ao excluir foto: {e}"}), 500


@bp.route('/visits/<int:visit_id>/photos', methods=['DELETE'])
def delete_all_photos_of_visit(visit_id):
    """Exclui todas as fotos associadas a uma visita."""
    try:
        visit = Visit.query.get_or_404(visit_id)
        count = 0
        for photo in visit.photos:
            from urllib.parse import urlparse
            parsed = urlparse(photo.url)
            filename = os.path.basename(parsed.path)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(photo)
            count += 1

        db.session.commit()
        return jsonify({"message": f"{count} foto(s) excluídas com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao excluir fotos da visita: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# 🔗 Resolver URL pública da foto (R2 / legado)
# ============================================================
def resolve_photo_url(u: str) -> str:
    if not u:
        return ""

    # já é pública (R2/CDN)
    if u.startswith("http://") or u.startswith("https://"):
        return u

    # legado /uploads/... -> aponta pro backend
    if u.startswith("/uploads/"):
        backend_url = (os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com").rstrip("/")
        return f"{backend_url}{u}"

    return u




@bp.route("/visits/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    v = Visit.query.get_or_404(visit_id)

    photos = []
    try:
        for p in (v.photos or []):
            photos.append({
                "id": p.id,
                "url": resolve_photo_url(p.url),
                "caption": p.caption or ""
            })
    except Exception:
        photos = []

    return jsonify({
        "id": v.id,
        "client_id": v.client_id,
        "property_id": v.property_id,
        "plot_id": v.plot_id,
        "consultant_id": v.consultant_id,
        "date": v.date.isoformat() if getattr(v, "date", None) else None,
        "recommendation": v.recommendation or "",
        "status": v.status or "planned",
        "fenologia_real": getattr(v, "fenologia_real", None),
        "latitude": getattr(v, "latitude", None),
        "longitude": getattr(v, "longitude", None),
        "products": getattr(v, "products", []) or [],
        "photos": photos
    })





@bp.route("/view/visit/<int:visit_id>", methods=["GET"])
def public_visit_view(visit_id):
    """🌿 Página pública de visualização de visita (NutriCRM Viewer)"""
    from models import Visit, Client, Property, Plot, Consultant

    # ================================
    # ✅ CORREÇÃO OBRIGATÓRIA AQUI
    # ================================
    backend_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com"

    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    prop = Property.query.get(visit.property_id)
    plot = Plot.query.get(visit.plot_id)
    consultant = Consultant.query.get(visit.consultant_id) if hasattr(visit, "consultant_id") else None

    lat = getattr(plot, "latitude", None)
    lon = getattr(plot, "longitude", None)

    photos = []
    for p in (visit.photos or []):
        photos.append({
            "id": p.id,
            "url": resolve_photo_url(p.url),
            "caption": p.caption or ""
        })


    html_template = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Visita #{{ visit.id }} — NutriCRM</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body { background-color:#f9fafb; font-family:'Inter', sans-serif; padding-bottom:60px; }
            header { background:#1B5E20; color:white; padding:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; }
            header img { height:46px; object-fit:contain; }
            .info-card { background:white; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.05); padding:20px; margin-top:20px; }
            .photos img { width:100%; border-radius:8px; cursor:pointer; transition:transform 0.2s; }
            .photos img:hover { transform:scale(1.02); }
            #map { height:300px; border-radius:10px; margin-top:15px; }
            footer { margin-top:40px; text-align:center; color:#888; }
            .download-btn { background:#2E7D32; color:white; padding:10px 18px; border-radius:6px; text-decoration:none; transition:opacity .2s; }
            .download-btn:hover { opacity:.85; }
            .lightbox { display:none; position:fixed; z-index:9999; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); justify-content:center; align-items:center; }
            .lightbox img { max-width:90%; max-height:90%; }
        </style>
    </head>
    <body>
        <header>
            <img src="/static/nutricrm_logo.png" alt="NutriCRM Logo" />
            <h4>Relatório Técnico — Visita #{{ visit.id }}</h4>
            <a class="download-btn" href="/api/visits/{{ visit.id }}/pdf" target="_blank">📄 Baixar PDF</a>
        </header>

        <main class="container">
            <div class="info-card">
                <h4>Informações Gerais</h4>
                <table class="table table-borderless mt-3">
                    <tr><th>Cliente:</th><td>{{ client.name if client else '-' }}</td></tr>
                    <tr><th>Fazenda:</th><td>{{ prop.name if prop else '-' }}</td></tr>
                    <tr><th>Talhão:</th><td>{{ plot.name if plot else '-' }}</td></tr>
                    <tr><th>Consultor:</th><td>{{ consultant.name if consultant else '-' }}</td></tr>
                    <tr><th>Data:</th><td>{{ visit.date.strftime('%d/%m/%Y') if visit.date else '-' }}</td></tr>
                    <tr><th>Status:</th><td>{{ visit.status }}</td></tr>
                </table>
                {% if lat and lon %}
                <div id="map"></div>
                {% endif %}
            </div>

            {% if visit.diagnosis %}
            <div class="info-card">
                <h4>Diagnóstico</h4>
                <p>{{ visit.diagnosis }}</p>
            </div>
            {% endif %}

            {% if visit.recommendation %}
            <div class="info-card">
                <h4>Recomendações Técnicas</h4>
                <p>{{ visit.recommendation }}</p>
            </div>
            {% endif %}

            {% if photos %}
            <div class="info-card photos">
                <h4>Fotos da Visita</h4>
                <div class="row mt-3">
                    {% for p in photos %}
                    <div class="col-md-6 mb-3">
                        <img src="{{ p.url }}" onclick="openLightbox('{{ p.url }}')" />
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </main>

        <div id="lightbox" class="lightbox" onclick="closeLightbox()">
            <img id="lightbox-img" src="">
        </div>

        <footer>
            <small>NutriCRM © 2025 — Relatório técnico automatizado</small>
        </footer>

        <script>
            function openLightbox(src) {
                document.getElementById('lightbox-img').src = src;
                document.getElementById('lightbox').style.display = 'flex';
            }
            function closeLightbox() {
                document.getElementById('lightbox').style.display = 'none';
            }

            {% if lat and lon %}
            const map = L.map('map').setView([{{ lat }}, {{ lon }}], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            L.marker([{{ lat }}, {{ lon }}]).addTo(map)
                .bindPopup("{{ plot.name if plot else 'Talhão' }}")
                .openPopup();
            {% endif %}
        </script>
    </body>
    </html>
    """

    return render_template_string(
        html_template,
        visit=visit,
        client=client,
        prop=prop,
        plot=plot,
        consultant=consultant,
        photos=photos,
        lat=lat,
        lon=lon
    )


@bp.route("/visits/<int:visit_id>/products", methods=["POST"])
def add_visit_product(visit_id):
    data = request.get_json()

    product = VisitProduct(
        visit_id=visit_id,
        product_name=data.get("product_name", "").strip(),
        dose=data.get("dose", "").strip(),
        unit=data.get("unit", "").strip(),
        application_date=datetime.strptime(data.get("application_date"), "%Y-%m-%d") if data.get("application_date") else None,
    )

    db.session.add(product)
    db.session.commit()

    return jsonify({"success": True, "product": product.to_dict()}), 201



@bp.route("/products/<int:product_id>", methods=["PUT"])
def update_visit_product(product_id):
    data = request.get_json()
    product = VisitProduct.query.get_or_404(product_id)

    product.product_name = data.get("product_name", product.product_name)
    product.dose = data.get("dose", product.dose)
    product.unit = data.get("unit", product.unit)
    product.application_date = (
        datetime.strptime(data["application_date"], "%Y-%m-%d")
        if data.get("application_date")
        else product.application_date
    )

    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict()})



@bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_visit_product(product_id):
    product = VisitProduct.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True})





@bp.route('/phenology/schedule', methods=['GET'])
def get_phenology_schedule():
    """
    Retorna o cronograma fenológico real (do banco de dados)
    com base na tabela phenology_stage.
    """
    from datetime import datetime, timedelta

    culture = request.args.get("culture")
    planting_date = request.args.get("planting_date")

    if not culture or not planting_date:
        return jsonify({"error": "culture and planting_date required"}), 400

    try:
        planting_date = datetime.fromisoformat(planting_date).date()
    except ValueError:
        return jsonify({"error": "invalid planting_date format"}), 400

    # ✅ Agora busca diretamente da tabela correta
    stages = db.session.run(
        text("SELECT code, name, days FROM phenology_stage WHERE culture = :culture ORDER BY days"),
        {"culture": culture}
    ).fetchall()

    if not stages:
        print(f"⚠️ Nenhum estágio encontrado para {culture}.")
        return jsonify([]), 200

    events = []
    for s in stages:
        date = planting_date + timedelta(days=s.days)
        events.append({
            "stage": s.name,
            "code": s.code,
            "suggested_date": date.isoformat(),
        })

    print(f"✅ {len(events)} estágios retornados para {culture}.")
    return jsonify(events), 200



# ============================================================
# 🔧 TESTES E UTILITÁRIOS
# ============================================================


@bp.route('/status')
def status():
    return jsonify({
        "ok": True,
        "clients": Client.query.count(),
        "properties": Property.query.count(),
        "plots": Plot.query.count(),
        "visits": Visit.query.count(),
    }), 200



@bp.route('/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello from Flask!")


@bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'email': u.email} for u in users])


# ---- Clients CRUD -------------------------------------------------
from models import Client


@bp.route('/clients', methods=['GET'])
def get_clients():
    """Return list of clients."""
    clients = Client.query.order_by(Client.id.desc()).all()
    return jsonify([c.to_dict() for c in clients]), 200


@bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    return jsonify(client.to_dict()), 200


@bp.route('/clients', methods=['POST'])
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
    )
    db.session.add(client)
    db.session.commit()
    return jsonify(message='client created', client=client.to_dict()), 201


@bp.route('/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    data = request.get_json() or {}
    # Update allowed fields if present
    for field in ('name', 'document', 'segment', 'vendor'):
        if field in data:
            setattr(client, field, data.get(field))
    db.session.commit()
    return jsonify(message='client updated', client=client.to_dict()), 200


@bp.route('/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    db.session.delete(client)
    db.session.commit()
    return jsonify(message='client deleted'), 200


# ---- Properties CRUD -------------------------------------------------
from models import Property


@bp.route('/properties', methods=['GET'])
def get_properties():
    """List properties. Optional query param: client_id to filter by client."""
    client_id = request.args.get('client_id', type=int)
    q = Property.query
    if client_id:
        q = q.filter_by(client_id=client_id)
    props = q.order_by(Property.id.desc()).all()
    return jsonify([p.to_dict() for p in props]), 200


@bp.route('/properties/<int:prop_id>', methods=['GET'])
def get_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    return jsonify(p.to_dict()), 200


@bp.route('/properties', methods=['POST'])
def create_property():
    data = request.get_json() or {}
    client_id = data.get('client_id')
    name = data.get('name')
    if not client_id or not name:
        return jsonify(message='client_id and name are required'), 400
    # ensure client exists
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404

    prop = Property(
        client_id=client_id,
        name=name,
        city_state=data.get('city_state'),
        area_ha=(float(data.get('area_ha')) if data.get('area_ha') is not None else None),
    )
    db.session.add(prop)
    db.session.commit()
    return jsonify(message='property created', property=prop.to_dict()), 201


@bp.route('/properties/<int:prop_id>', methods=['PUT'])
def update_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    data = request.get_json() or {}
    for field in ('name', 'city_state', 'area_ha', 'client_id'):
        if field in data:
            # convert area_ha to float when provided
            if field == 'area_ha':
                setattr(p, field, float(data.get(field)) if data.get(field) is not None else None)
            else:
                setattr(p, field, data.get(field))

    # If client_id was changed, ensure the client exists
    if 'client_id' in data and data.get('client_id') is not None:
        if not Client.query.get(data.get('client_id')):
            return jsonify(message='client not found'), 404

    db.session.commit()
    return jsonify(message='property updated', property=p.to_dict()), 200


@bp.route('/properties/<int:prop_id>', methods=['DELETE'])
def delete_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='property deleted'), 200


# ---- Plots (Talhões) CRUD -------------------------------------------
from models import Plot


@bp.route('/plots', methods=['GET'])
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
        print(f"❌ Erro em /plots: {e}")
        return jsonify(error=str(e)), 500



@bp.route('/plots/<int:plot_id>', methods=['GET'])
def get_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    return jsonify(pl.to_dict()), 200


@bp.route('/plots', methods=['POST'])
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
    # normalize irrigated to boolean or None
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


@bp.route('/plots/<int:plot_id>', methods=['PUT'])
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


@bp.route('/plots/<int:plot_id>', methods=['DELETE'])
def delete_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    db.session.delete(pl)
    db.session.commit()
    return jsonify(message='plot deleted'), 200


# ---- Plantings (Plantios) CRUD --------------------------------------
from models import Planting
from datetime import datetime


@bp.route('/plantings', methods=['GET'])
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


@bp.route('/plantings/<int:pid>', methods=['GET'])
def get_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    return jsonify(p.to_dict()), 200


@bp.route('/plantings', methods=['POST'])
def create_planting():
    data = request.get_json() or {}
    plot_id = data.get('plot_id')
    if not plot_id:
        return jsonify(message='plot_id is required'), 400

    plot = Plot.query.get(plot_id)
    if not plot:
        return jsonify(message='plot not found'), 404

    # cultura e variedade podem vir do select do frontend
    culture = data.get('culture')  # esperado: "Milho", "Soja", "Algodão" (case-insensitive ok)
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
    db.session.flush()  # para ter p.id

    # === Gerar Visitas automáticas pela fenologia ===
    # Usa a tabela real phenology_stage do banco
    if planting_date and culture:
        from sqlalchemy import text

        # busca do banco conforme cultura
        stages = db.session.run(
            text("SELECT code, name, days FROM phenology_stage WHERE culture = :culture ORDER BY days"),
            {"culture": culture}
        ).fetchall()

        if stages:
            prop = Property.query.get(plot.property_id) if plot.property_id else None
            client = Client.query.get(prop.client_id) if (prop and prop.client_id) else None

            for st in stages:
                if st.days == 0:
                    continue  # ignora o plantio (já criado)

                visit_date = planting_date + datetime.timedelta(days=int(st.days))

                v = Visit(
                    client_id=(client.id if client else None),
                    property_id=(prop.id if prop else None),
                    plot_id=plot.id,
                    planting_id=p.id,
                    consultant_id=None,
                    date=visit_date,
                    checklist=None,
                    diagnosis=None,
                    recommendation=st.name,
                    culture=culture,
                    variety=variety,
                    status='planned'
                )
                db.session.add(v)

            print(f"✅ {len(stages)} visitas geradas para {culture}.")


    db.session.commit()
    return jsonify(message='planting created', planting=p.to_dict()), 201



@bp.route('/plantings/<int:pid>', methods=['PUT'])
def update_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    data = request.get_json() or {}

    if 'plot_id' in data and data.get('plot_id') is not None:
        if not Plot.query.get(data.get('plot_id')):
            return jsonify(message='plot not found'), 404
        p.plot_id = data.get('plot_id')

    if 'culture' in data:
        p.culture = data.get('culture')
    if 'variety' in data:
        p.variety = data.get('variety')
    if 'planting_date' in data:
        if data.get('planting_date') in (None, ''):
            p.planting_date = None
        else:
            try:
                p.planting_date = datetime.fromisoformat(data.get('planting_date')).date()
            except Exception:
                return jsonify(message='invalid planting_date, expected YYYY-MM-DD'), 400

    db.session.commit()
    return jsonify(message='planting updated', planting=p.to_dict()), 200


@bp.route('/plantings/<int:pid>', methods=['DELETE'])
def delete_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='planting deleted'), 200


# ---- Visits (Visitas) CRUD ------------------------------------------
from models import Visit
from datetime import date

# ---- Opportunities CRUD --------------------------------------------
from models import Opportunity


@bp.route('/opportunities', methods=['GET'])
def get_opportunities():
    """List opportunities. Optional filter: client_id"""
    client_id = request.args.get('client_id', type=int)
    q = Opportunity.query
    if client_id:
        q = q.filter_by(client_id=client_id)
    items = q.order_by(Opportunity.id.desc()).all()
    return jsonify([it.to_dict() for it in items]), 200


@bp.route('/opportunities/<int:oid>', methods=['GET'])
def get_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    return jsonify(o.to_dict()), 200


@bp.route('/opportunities', methods=['POST'])
def create_opportunity():
    data = request.get_json() or {}
    client_id = data.get('client_id')
    if not client_id:
        return jsonify(message='client_id is required'), 400
    if not Client.query.get(client_id):
        return jsonify(message='client not found'), 404

    title = data.get('title')
    estimated_value = data.get('estimated_value')
    stage = data.get('stage') or 'prospecção'

    try:
        estimated_value = float(estimated_value) if estimated_value is not None else None
    except Exception:
        return jsonify(message='estimated_value must be a number'), 400

    o = Opportunity(
        client_id=client_id,
        title=title,
        estimated_value=estimated_value,
        stage=stage,
    )
    db.session.add(o)
    db.session.commit()
    return jsonify(message='opportunity created', opportunity=o.to_dict()), 201


@bp.route('/opportunities/<int:oid>', methods=['PUT'])
def update_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    data = request.get_json() or {}
    if 'client_id' in data and data.get('client_id') is not None:
        if not Client.query.get(data.get('client_id')):
            return jsonify(message='client not found'), 404
        o.client_id = data.get('client_id')
    if 'title' in data:
        o.title = data.get('title')
    if 'estimated_value' in data:
        try:
            o.estimated_value = float(data.get('estimated_value')) if data.get('estimated_value') is not None else None
        except Exception:
            return jsonify(message='estimated_value must be a number'), 400
    if 'stage' in data:
        o.stage = data.get('stage') or 'prospecção'

    db.session.commit()
    return jsonify(message='opportunity updated', opportunity=o.to_dict()), 200


@bp.route('/opportunities/<int:oid>', methods=['DELETE'])
def delete_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify(message='opportunity deleted'), 200


@bp.route('/db-test', methods=['GET'])
def db_test():
    """Simple endpoint to test DB connectivity and return user count."""
    try:
        # run a trivial select to verify connection
        result = None
        with db.engine.connect() as conn:
            row = conn.run(text('SELECT 1')).fetchone()
            result = row[0] if row is not None else None

        # also give a user count
        user_count = User.query.count()
        return jsonify(status='ok', ping=result, users=user_count), 200
    except Exception as e:
        return jsonify(status='error', error=str(e)), 500


@bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user. Expects JSON: {email, password}"""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify(message='email and password are required'), 400

    if User.query.filter_by(email=email).first():
        return jsonify(message='user with that email already exists'), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(message='user created', id=user.id, email=user.email), 201


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify(message='email and password are required'), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(message='invalid credentials'), 401

    # create JWT
    secret = os.environ.get('JWT_SECRET', 'dev-secret')
    payload = {
        'sub': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    return jsonify(message='ok', token=token), 200


def _get_current_user_from_token(req):
    auth = req.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, 'missing token'
    token = auth.split(' ', 1)[1]
    secret = os.environ.get('JWT_SECRET', 'dev-secret')
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None, 'token expired'
    except jwt.InvalidTokenError:
        return None, 'invalid token'

    user = User.query.get(payload.get('sub'))
    if not user:
        return None, 'user not found'
    return user, None


@bp.route('/me', methods=['GET'])
def me():
    user, err = _get_current_user_from_token(request)
    if err:
        return jsonify(message=err), 401
    return jsonify(id=user.id, email=user.email), 200

