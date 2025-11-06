from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# ============================================================
# 👨‍🌾 Lista fixa de consultores
# ============================================================
CONSULTANTS = [
    {"id": 1, "name": "Jhonatan"},
    {"id": 2, "name": "Felipe"},
    {"id": 3, "name": "Everton"},
    {"id": 4, "name": "Pedro"},
    {"id": 5, "name": "Alexandre"},
]

# ============================================================
# 👤 Usuário
# ============================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return self.password_hash and check_password_hash(self.password_hash, password)


# ============================================================
# 🧑‍🌾 Clientes
# ============================================================
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    document = db.Column(db.String(100), nullable=True, index=True)
    segment = db.Column(db.String(50), nullable=True)
    vendor = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    properties = db.relationship('Property', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    visits = db.relationship('Visit', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    opportunities = db.relationship('Opportunity', backref='client', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'document': self.document,
            'segment': self.segment,
            'vendor': self.vendor,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 🌾 Propriedades / Fazendas
# ============================================================
class Property(db.Model):
    __tablename__ = 'properties'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    city_state = db.Column(db.String(120), nullable=True)
    area_ha = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    plots = db.relationship('Plot', backref='property', lazy='dynamic', cascade='all, delete-orphan')
    visits = db.relationship('Visit', backref='property', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else None,
            'name': self.name,
            'city_state': self.city_state,
            'area_ha': self.area_ha,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 🌱 Talhões
# ============================================================
class Plot(db.Model):
    __tablename__ = 'plots'
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    area_ha = db.Column(db.Float, nullable=True)
    irrigated = db.Column(db.Boolean, nullable=True, server_default='0')
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    plantings = db.relationship('Planting', backref='plot', lazy='dynamic', cascade='all, delete-orphan')
    visits = db.relationship('Visit', backref='plot', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'property_id': self.property_id,
            'property_name': self.property.name if self.property else None,
            'name': self.name,
            'area_ha': self.area_ha,
            'irrigated': bool(self.irrigated) if self.irrigated is not None else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 🌾 Plantios
# ============================================================
class Planting(db.Model):
    __tablename__ = 'plantings'
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plots.id'), nullable=False, index=True)
    culture = db.Column(db.String(120), nullable=True)
    variety = db.Column(db.String(200), nullable=True)
    planting_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    visits = db.relationship('Visit', backref='planting', lazy='select', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'plot_id': self.plot_id,
            'plot_name': self.plot.name if self.plot else None,
            'culture': self.culture,
            'variety': self.variety,
            'planting_date': self.planting_date.isoformat() if self.planting_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 📋 Visitas
# ============================================================
class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=True, index=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plots.id'), nullable=True, index=True)
    planting_id = db.Column(db.Integer, db.ForeignKey('plantings.id'), nullable=True, index=True)
    consultant_id = db.Column(db.Integer, nullable=True, index=True)
    date = db.Column(db.Date, nullable=True)
    checklist = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=True, server_default='planned')
    culture = db.Column(db.String(120), nullable=True)
    variety = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        consultant_name = None
        if self.consultant_id:
            match = next((c["name"] for c in CONSULTANTS if c["id"] == self.consultant_id), None)
            consultant_name = match or f"Consultor {self.consultant_id}"

        client_line = f"👤 {self.client.name}" if self.client else ""
        variety_line = f"🌱 {self.variety}" if self.variety else ""
        stage_line = f"📍 {self.recommendation}" if self.recommendation else ""
        consultant_line = f"👨‍🌾 {consultant_name}" if consultant_name else ""

        display_text = "<br>".join(filter(None, [client_line, variety_line, stage_line, consultant_line]))

        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else None,
            'property_id': self.property_id,
            'property_name': self.property.name if self.property else None,
            'plot_id': self.plot_id,
            'plot_name': self.plot.name if self.plot else None,
            'planting_id': self.planting_id,
            'consultant_id': self.consultant_id,
            'consultant_name': consultant_name,
            'date': self.date.isoformat() if self.date else None,
            'checklist': self.checklist,
            'diagnosis': self.diagnosis,
            'recommendation': (self.recommendation or '').strip(),
            'status': self.status,
            'culture': self.culture,
            'variety': self.variety,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'display_text': display_text,
        }


# ============================================================
# 🧑‍💼 Consultores
# ============================================================
class Consultant(db.Model):
    __tablename__ = "consultants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# 🖼️ Fotos da visita (com legenda)
# ============================================================
class Photo(db.Model):
    __tablename__ = 'photos'
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'))
    url = db.Column(db.String(255))  # link da imagem armazenada
    caption = db.Column(db.String(255), nullable=True)  # ✅ legenda opcional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    visit = db.relationship('Visit', backref=db.backref('photos', cascade='all, delete'))

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'caption': self.caption,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 💼 Oportunidades
# ============================================================
class Opportunity(db.Model):
    __tablename__ = 'opportunities'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=True)
    estimated_value = db.Column(db.Float, nullable=True)
    stage = db.Column(db.String(80), nullable=False, server_default='prospecção')
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else None,
            'title': self.title,
            'estimated_value': self.estimated_value,
            'stage': self.stage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 🌾 Culturas e Variedades Fixas
# ============================================================
class Culture(db.Model):
    __tablename__ = 'cultures'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class Variety(db.Model):
    __tablename__ = 'varieties'
    id = db.Column(db.Integer, primary_key=True)
    culture_id = db.Column(db.Integer, db.ForeignKey('cultures.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    culture = db.relationship('Culture', backref='varieties')


# ============================================================
# 🌱 Estágios Fenológicos
# ============================================================
class PhenologyStage(db.Model):
    __tablename__ = 'phenology_stages'
    id = db.Column(db.Integer, primary_key=True)
    culture = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    days = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'culture': self.culture,
            'code': self.code,
            'name': self.name,
            'days': self.days,
        }
