# routes/sales.py
"""
CRUD de Produtos e Vendas + Relatórios.

Produtos:
- /products (GET, POST)
- /products/<id> (GET, PUT, DELETE)

Vendas:
- /sales (GET, POST)
- /sales/<id> (GET, PUT, DELETE)

Relatórios:
- /sales/report/summary - resumo geral
- /sales/report/by-region - volume/faturamento por região
- /sales/report/by-client - ranking de clientes
- /sales/report/by-category - mix de produtos
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, desc
from datetime import date

from models import db, Product, Sale, Client, Consultant

sales_bp = Blueprint('sales', __name__)


# ============================================================
# 📦 PRODUTOS - CRUD
# ============================================================

@sales_bp.route('/products', methods=['GET'])
def get_products():
    """Lista todos os produtos (ativos por padrão)."""
    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
    category = request.args.get('category')

    query = Product.query
    if not show_inactive:
        query = query.filter(Product.active == True)
    if category:
        query = query.filter(Product.category == category)

    products = query.order_by(Product.category, Product.name).all()
    return jsonify([p.to_dict() for p in products]), 200


@sales_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id: int):
    product = Product.query.get(product_id)
    if not product:
        return jsonify(message='Produto não encontrado'), 404
    return jsonify(product.to_dict()), 200


@sales_bp.route('/products', methods=['POST'])
def create_product():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    default_unit = data.get('default_unit', '').strip()

    if not name or not category or not default_unit:
        return jsonify(message='Nome, categoria e unidade são obrigatórios'), 400

    valid_categories = ['Semente', 'Fertilizante', 'Defensivo', 'Nutrição Foliar', 'Biológico']
    if category not in valid_categories:
        return jsonify(message=f'Categoria inválida. Use: {", ".join(valid_categories)}'), 400

    valid_units = ['Kg', 'L', 'Sacas', 'Ton', 'BB']
    if default_unit not in valid_units:
        return jsonify(message=f'Unidade inválida. Use: {", ".join(valid_units)}'), 400

    culture = (data.get('culture') or '').strip() or None
    seeds_per_ha = data.get('seeds_per_ha')

    if category == 'Semente':
        valid_cultures = ['Soja', 'Milho', 'Algodão']
        if culture and culture not in valid_cultures:
            return jsonify(message=f'Cultura inválida. Use: {", ".join(valid_cultures)}'), 400
        if seeds_per_ha:
            try:
                seeds_per_ha = int(seeds_per_ha)
                if seeds_per_ha < 1000 or seeds_per_ha > 1000000:
                    return jsonify(message='População deve estar entre 1.000 e 1.000.000 sementes/ha'), 400
            except (ValueError, TypeError):
                return jsonify(message='População deve ser um número inteiro'), 400

    product = Product(
        name=name,
        category=category,
        default_unit=default_unit,
        culture=culture,
        seeds_per_ha=seeds_per_ha if category == 'Semente' else None,
        active=True,
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(message='Produto criado', product=product.to_dict()), 201


@sales_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id: int):
    product = Product.query.get(product_id)
    if not product:
        return jsonify(message='Produto não encontrado'), 404

    data = request.get_json() or {}

    if 'name' in data:
        product.name = data['name'].strip()
    if 'category' in data:
        product.category = data['category'].strip()
    if 'default_unit' in data:
        product.default_unit = data['default_unit'].strip()
    if 'active' in data:
        product.active = bool(data['active'])
    if 'culture' in data:
        culture = (data['culture'] or '').strip() or None
        valid_cultures = ['Soja', 'Milho', 'Algodão']
        if culture and culture not in valid_cultures:
            return jsonify(message=f'Cultura inválida. Use: {", ".join(valid_cultures)}'), 400
        product.culture = culture
    if 'seeds_per_ha' in data:
        seeds_per_ha = data['seeds_per_ha']
        if seeds_per_ha is not None:
            try:
                seeds_per_ha = int(seeds_per_ha)
                if seeds_per_ha < 1000 or seeds_per_ha > 1000000:
                    return jsonify(message='População deve estar entre 1.000 e 1.000.000 sementes/ha'), 400
            except (ValueError, TypeError):
                return jsonify(message='População deve ser um número inteiro'), 400
        product.seeds_per_ha = seeds_per_ha

    db.session.commit()
    return jsonify(message='Produto atualizado', product=product.to_dict()), 200


@sales_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id: int):
    product = Product.query.get(product_id)
    if not product:
        return jsonify(message='Produto não encontrado'), 404

    sales_count = Sale.query.filter_by(product_id=product_id).count()
    if sales_count > 0:
        product.active = False
        db.session.commit()
        return jsonify(message='Produto desativado (possui vendas vinculadas)'), 200

    db.session.delete(product)
    db.session.commit()
    return jsonify(message='Produto excluído'), 200


# ============================================================
# 💰 VENDAS - CRUD
# ============================================================

@sales_bp.route('/sales', methods=['GET'])
def get_sales():
    """Lista vendas com filtros opcionais."""
    client_id = request.args.get('client_id', type=int)
    product_id = request.args.get('product_id', type=int)
    consultant_id = request.args.get('consultant_id', type=int)
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    region = request.args.get('region')
    category = request.args.get('category')

    query = Sale.query

    if client_id:
        query = query.filter(Sale.client_id == client_id)
    if product_id:
        query = query.filter(Sale.product_id == product_id)
    if consultant_id:
        query = query.filter(Sale.consultant_id == consultant_id)
    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)
    if region:
        query = query.join(Client).filter(Client.region == region)
    if category:
        query = query.join(Product).filter(Product.category == category)

    sales = query.order_by(desc(Sale.created_at)).all()
    return jsonify([s.to_dict() for s in sales]), 200


@sales_bp.route('/sales/<int:sale_id>', methods=['GET'])
def get_sale(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        return jsonify(message='Venda não encontrada'), 404
    return jsonify(sale.to_dict()), 200


@sales_bp.route('/sales', methods=['POST'])
def create_sale():
    data = request.get_json() or {}

    client_id = data.get('client_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    unit = data.get('unit', '').strip()
    period_type = data.get('period_type', '').strip()
    period_year = data.get('period_year', '').strip()

    if not all([client_id, product_id, quantity, unit, period_type, period_year]):
        return jsonify(message='Cliente, produto, quantidade, unidade e período são obrigatórios'), 400

    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='Cliente não encontrado'), 404

    product = Product.query.get(product_id)
    if not product:
        return jsonify(message='Produto não encontrado'), 404

    valid_units = ['Kg', 'L', 'Sacas', 'Ton', 'BB']
    if unit not in valid_units:
        return jsonify(message=f'Unidade inválida. Use: {", ".join(valid_units)}'), 400

    if period_type not in ['Safra', 'Safrinha']:
        return jsonify(message='Tipo de período inválido. Use: Safra ou Safrinha'), 400

    sale_date_str = data.get('sale_date')
    sale_date = None
    if sale_date_str:
        try:
            sale_date = date.fromisoformat(sale_date_str)
        except ValueError:
            return jsonify(message='Data de venda inválida'), 400

    culture = (data.get('culture') or '').strip() or None
    valid_cultures = ['Soja', 'Milho', 'Algodão']
    if culture and culture not in valid_cultures:
        return jsonify(message=f'Cultura inválida. Use: {", ".join(valid_cultures)}'), 400

    sale = Sale(
        client_id=client_id,
        product_id=product_id,
        consultant_id=data.get('consultant_id'),
        quantity=float(quantity),
        unit=unit,
        value=float(data['value']) if data.get('value') else None,
        period_type=period_type,
        period_year=period_year,
        culture=culture,
        sale_date=sale_date or date.today(),
        notes=data.get('notes'),
    )
    db.session.add(sale)
    db.session.commit()
    return jsonify(message='Venda registrada', sale=sale.to_dict()), 201


@sales_bp.route('/sales/<int:sale_id>', methods=['PUT'])
def update_sale(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        return jsonify(message='Venda não encontrada'), 404

    data = request.get_json() or {}

    if 'client_id' in data:
        sale.client_id = data['client_id']
    if 'product_id' in data:
        sale.product_id = data['product_id']
    if 'consultant_id' in data:
        sale.consultant_id = data['consultant_id']
    if 'quantity' in data:
        sale.quantity = float(data['quantity'])
    if 'unit' in data:
        sale.unit = data['unit'].strip()
    if 'value' in data:
        sale.value = float(data['value']) if data['value'] else None
    if 'period_type' in data:
        sale.period_type = data['period_type'].strip()
    if 'period_year' in data:
        sale.period_year = data['period_year'].strip()
    if 'culture' in data:
        culture = (data['culture'] or '').strip() or None
        valid_cultures = ['Soja', 'Milho', 'Algodão']
        if culture and culture not in valid_cultures:
            return jsonify(message=f'Cultura inválida. Use: {", ".join(valid_cultures)}'), 400
        sale.culture = culture
    if 'sale_date' in data and data['sale_date']:
        sale.sale_date = date.fromisoformat(data['sale_date'])
    if 'notes' in data:
        sale.notes = data['notes']

    db.session.commit()
    return jsonify(message='Venda atualizada', sale=sale.to_dict()), 200


@sales_bp.route('/sales/<int:sale_id>', methods=['DELETE'])
def delete_sale(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        return jsonify(message='Venda não encontrada'), 404

    db.session.delete(sale)
    db.session.commit()
    return jsonify(message='Venda excluída'), 200


# ============================================================
# 📊 RELATÓRIOS
# ============================================================

@sales_bp.route('/sales/report/summary', methods=['GET'])
def sales_summary():
    """Resumo geral de vendas."""
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    region = request.args.get('region')
    category = request.args.get('category')

    query = db.session.query(
        func.count(Sale.id).label('total_sales'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
    )

    if category:
        query = query.join(Product, Sale.product_id == Product.id).filter(Product.category == category)
    if region:
        query = query.join(Client, Sale.client_id == Client.id).filter(Client.region == region)
    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)

    result = query.one()

    # Query para clientes únicos com os mesmos filtros
    clients_query = db.session.query(func.count(func.distinct(Sale.client_id)))
    if category:
        clients_query = clients_query.join(Product, Sale.product_id == Product.id).filter(Product.category == category)
    if region:
        clients_query = clients_query.join(Client, Sale.client_id == Client.id).filter(Client.region == region)
    if period_type:
        clients_query = clients_query.filter(Sale.period_type == period_type)
    if period_year:
        clients_query = clients_query.filter(Sale.period_year == period_year)

    clients_count = clients_query.scalar() or 0

    return jsonify({
        'total_sales': result.total_sales or 0,
        'total_value': float(result.total_value or 0),
        'total_quantity': float(result.total_quantity or 0),
        'unique_clients': clients_count,
    }), 200


@sales_bp.route('/sales/report/by-region', methods=['GET'])
def sales_by_region():
    """Volume e faturamento por região."""
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    category = request.args.get('category')

    query = db.session.query(
        Client.region,
        func.count(Sale.id).label('sales_count'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
        func.count(func.distinct(Sale.client_id)).label('clients_count'),
    ).join(Client, Sale.client_id == Client.id)

    if category:
        query = query.join(Product, Sale.product_id == Product.id).filter(Product.category == category)

    query = query.group_by(Client.region)

    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)

    results = query.order_by(desc('total_value')).all()

    data = []
    for row in results:
        data.append({
            'region': row.region or 'Sem região',
            'sales_count': row.sales_count,
            'total_value': float(row.total_value or 0),
            'total_quantity': float(row.total_quantity or 0),
            'clients_count': row.clients_count,
        })

    return jsonify(data), 200


@sales_bp.route('/sales/report/by-client', methods=['GET'])
def sales_by_client():
    """Ranking de clientes por faturamento."""
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    region = request.args.get('region')
    category = request.args.get('category')
    limit = request.args.get('limit', 20, type=int)

    query = db.session.query(
        Client.id,
        Client.name,
        Client.region,
        func.count(Sale.id).label('sales_count'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
    ).join(Client, Sale.client_id == Client.id)

    if category:
        query = query.join(Product, Sale.product_id == Product.id).filter(Product.category == category)

    query = query.group_by(Client.id, Client.name, Client.region)

    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)
    if region:
        query = query.filter(Client.region == region)

    results = query.order_by(desc('total_value')).limit(limit).all()

    data = []
    for i, row in enumerate(results, 1):
        data.append({
            'rank': i,
            'client_id': row.id,
            'client_name': row.name,
            'region': row.region,
            'sales_count': row.sales_count,
            'total_value': float(row.total_value or 0),
            'total_quantity': float(row.total_quantity or 0),
        })

    return jsonify(data), 200


@sales_bp.route('/sales/report/by-category', methods=['GET'])
def sales_by_category():
    """Mix de produtos por categoria."""
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    region = request.args.get('region')

    query = db.session.query(
        Product.category,
        func.count(Sale.id).label('sales_count'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
    ).join(Product, Sale.product_id == Product.id)

    if region:
        query = query.join(Client, Sale.client_id == Client.id).filter(Client.region == region)

    query = query.group_by(Product.category)

    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)

    results = query.order_by(desc('total_value')).all()

    total_value = sum(float(r.total_value or 0) for r in results)

    data = []
    for row in results:
        value = float(row.total_value or 0)
        data.append({
            'category': row.category,
            'sales_count': row.sales_count,
            'total_value': value,
            'total_quantity': float(row.total_quantity or 0),
            'percentage': round((value / total_value * 100), 1) if total_value > 0 else 0,
        })

    return jsonify(data), 200


@sales_bp.route('/sales/report/by-product', methods=['GET'])
def sales_by_product():
    """Vendas detalhadas por produto."""
    period_type = request.args.get('period_type')
    period_year = request.args.get('period_year')
    category = request.args.get('category')
    region = request.args.get('region')
    limit = request.args.get('limit', 30, type=int)

    query = db.session.query(
        Product.id,
        Product.name,
        Product.category,
        Product.default_unit,
        func.count(Sale.id).label('sales_count'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
    ).join(Product, Sale.product_id == Product.id)

    if region:
        query = query.join(Client, Sale.client_id == Client.id).filter(Client.region == region)

    query = query.group_by(Product.id, Product.name, Product.category, Product.default_unit)

    if period_type:
        query = query.filter(Sale.period_type == period_type)
    if period_year:
        query = query.filter(Sale.period_year == period_year)
    if category:
        query = query.filter(Product.category == category)

    results = query.order_by(desc('total_value')).limit(limit).all()

    data = []
    for i, row in enumerate(results, 1):
        data.append({
            'rank': i,
            'product_id': row.id,
            'product_name': row.name,
            'category': row.category,
            'unit': row.default_unit,
            'sales_count': row.sales_count,
            'total_value': float(row.total_value or 0),
            'total_quantity': float(row.total_quantity or 0),
        })

    return jsonify(data), 200


@sales_bp.route('/sales/report/evolution', methods=['GET'])
def sales_evolution():
    """Evolução de vendas por período (safra/safrinha)."""
    region = request.args.get('region')

    query = db.session.query(
        Sale.period_type,
        Sale.period_year,
        func.count(Sale.id).label('sales_count'),
        func.sum(Sale.value).label('total_value'),
        func.sum(Sale.quantity).label('total_quantity'),
        func.count(func.distinct(Sale.client_id)).label('clients_count'),
    )

    if region:
        query = query.join(Client, Sale.client_id == Client.id).filter(Client.region == region)

    query = query.group_by(Sale.period_type, Sale.period_year)
    results = query.order_by(Sale.period_year, Sale.period_type).all()

    data = []
    for row in results:
        data.append({
            'period_type': row.period_type,
            'period_year': row.period_year,
            'period_label': f"{row.period_type} {row.period_year}",
            'sales_count': row.sales_count,
            'total_value': float(row.total_value or 0),
            'total_quantity': float(row.total_quantity or 0),
            'clients_count': row.clients_count,
        })

    return jsonify(data), 200


# ============================================================
# 🔧 AUXILIARES
# ============================================================

@sales_bp.route('/sales/periods', methods=['GET'])
def get_periods():
    """Retorna períodos disponíveis para seleção."""
    periods = [
        {'type': 'Safra', 'year': '25/26', 'label': 'Safra 25/26'},
        {'type': 'Safrinha', 'year': '26', 'label': 'Safrinha 26'},
        {'type': 'Safra', 'year': '26/27', 'label': 'Safra 26/27'},
        {'type': 'Safrinha', 'year': '27', 'label': 'Safrinha 27'},
        {'type': 'Safra', 'year': '27/28', 'label': 'Safra 27/28'},
        {'type': 'Safrinha', 'year': '28', 'label': 'Safrinha 28'},
        {'type': 'Safra', 'year': '28/29', 'label': 'Safra 28/29'},
        {'type': 'Safrinha', 'year': '29', 'label': 'Safrinha 29'},
    ]
    return jsonify(periods), 200


@sales_bp.route('/products/categories', methods=['GET'])
def get_categories():
    """Retorna categorias de produtos."""
    categories = ['Semente', 'Fertilizante', 'Defensivo', 'Nutrição Foliar', 'Biológico']
    return jsonify(categories), 200


@sales_bp.route('/products/units', methods=['GET'])
def get_units():
    """Retorna unidades disponíveis."""
    units = ['Kg', 'L', 'Sacas', 'Ton', 'BB']
    return jsonify(units), 200


@sales_bp.route('/sales/cultures', methods=['GET'])
def get_cultures():
    """Retorna culturas disponíveis para vendas."""
    cultures = ['Soja', 'Milho', 'Algodão']
    return jsonify(cultures), 200
