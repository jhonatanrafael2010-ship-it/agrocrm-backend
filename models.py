from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Client(db.Model):
    """Client / Customer model matching the form in the UI.

    Fields:
    - id: primary key
    - name: display name of the client
    - document: CPF/CNPJ or other identifier
    - segment: business segment (e.g. A)
    - vendor: name of vendor responsible
    - created_at: timestamp when the record was created
    """

    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    document = db.Column(db.String(100), nullable=True, index=True)
    segment = db.Column(db.String(50), nullable=True)
    vendor = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'document': self.document,
            'segment': self.segment,
            'vendor': self.vendor,
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }

    # relationship to properties (one-to-many)
    properties = db.relationship('Property', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    # relationship to visits
    visits = db.relationship('Visit', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    # relationship to opportunities
    opportunities = db.relationship('Opportunity', backref='client', lazy='dynamic', cascade='all, delete-orphan')


class Property(db.Model):
    """Property / Farm model.

    Fields from the UI form:
    - client_id: foreign key to Client
    - name: farm name (Nome da Fazenda)
    - city_state: Cidade/UF
    - area_ha: Área (ha)
    """

    __tablename__ = 'properties'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    city_state = db.Column(db.String(120), nullable=True)
    area_ha = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': None if not self.client else self.client.name,
            'name': self.name,
            'city_state': self.city_state,
            'area_ha': self.area_ha,
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }

    # relationship to plots (talhões)
    plots = db.relationship('Plot', backref='property', lazy='dynamic', cascade='all, delete-orphan')
    # relationship to visits
    visits = db.relationship('Visit', backref='property', lazy='dynamic', cascade='all, delete-orphan')


class Plot(db.Model):
    """Plot / Talhão model.

    Fields from the UI form:
    - property_id: foreign key to Property
    - name: Nome do Talhão
    - area_ha: Área (ha)
    - irrigated: boolean flag (Irrigado?)
    """

    __tablename__ = 'plots'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    area_ha = db.Column(db.Float, nullable=True)
    irrigated = db.Column(db.Boolean, nullable=True, server_default='0')
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'property_id': self.property_id,
            'property_name': None if not self.property else self.property.name,
            'name': self.name,
            'area_ha': self.area_ha,
            'irrigated': bool(self.irrigated) if self.irrigated is not None else None,
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }
    # relationship to plantings
    plantings = db.relationship('Planting', backref='plot', lazy='dynamic', cascade='all, delete-orphan')
    # relationship to visits
    visits = db.relationship('Visit', backref='plot', lazy='dynamic', cascade='all, delete-orphan')


class Planting(db.Model):
    """Planting (Plantio) model.

    Fields captured from the UI:
    - plot_id: foreign key to Plot
    - culture: cultura (e.g., Milho)
    - variety: string (Variedade)
    - planting_date: date of planting
    """

    __tablename__ = 'plantings'

    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plots.id'), nullable=False, index=True)
    culture = db.Column(db.String(120), nullable=True)
    variety = db.Column(db.String(200), nullable=True)
    planting_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'plot_id': self.plot_id,
            'plot_name': None if not self.plot else self.plot.name,
            'culture': self.culture,
            'variety': self.variety,
            'planting_date': None if not self.planting_date else self.planting_date.isoformat(),
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }
    # relationship to visits
    visits = db.relationship('Visit', backref='planting', lazy='dynamic', cascade='all, delete-orphan')


class Visit(db.Model):
    """Visit (Visita) model.

    Fields from the UI:
    - client_id, property_id, plot_id, planting_id (optional)
    - consultant_id: FK to users (optional)
    - date: date of visit
    - checklist: text
    - diagnosis: text
    - recommendation: text
    """

    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False, index=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plots.id'), nullable=False, index=True)
    planting_id = db.Column(db.Integer, db.ForeignKey('plantings.id'), nullable=True, index=True)
    consultant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    date = db.Column(db.Date, nullable=True)
    checklist = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': None if not self.client else self.client.name,
            'property_id': self.property_id,
            'property_name': None if not self.property else self.property.name,
            'plot_id': self.plot_id,
            'plot_name': None if not self.plot else self.plot.name,
            'planting_id': self.planting_id,
            'consultant_id': self.consultant_id,
            'date': None if not self.date else self.date.isoformat(),
            'checklist': self.checklist,
            'diagnosis': self.diagnosis,
            'recommendation': self.recommendation,
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }

class Opportunity(db.Model):
    """Sales Opportunity model.

    Fields:
    - client_id: which client the opportunity is for
    - title: brief title/description
    - estimated_value: numeric (decimal) estimated revenue/value
    - stage: current stage (default 'prospecção')
    - created_at: timestamp
    """

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
            'client_name': None if not self.client else self.client.name,
            'title': self.title,
            'estimated_value': self.estimated_value,
            'stage': self.stage,
            'created_at': None if not self.created_at else self.created_at.isoformat(),
        }


# ============================
# Culturas e Variedades Fixas
# ============================

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



