#!/usr/bin/env python
"""
Script para criar usuário admin inicial.
Executar: python scripts/create_admin.py

Cria um usuário admin com:
- username: admin
- password: admin123 (mudar após primeiro login!)
"""

import sys
import os

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, User, Consultant


def create_admin():
    with app.app_context():
        # Verifica se já existe admin
        existing = User.query.filter_by(username='admin').first()
        if existing:
            print(f"❌ Usuário 'admin' já existe (id={existing.id})")
            return

        # Cria usuário admin
        admin = User(
            username='admin',
            is_admin=True,
            active=True,
        )
        admin.set_password('admin123')

        db.session.add(admin)
        db.session.commit()

        print(f"✅ Usuário admin criado!")
        print(f"   Username: admin")
        print(f"   Senha: admin123")
        print(f"   ⚠️  MUDE A SENHA APÓS O PRIMEIRO LOGIN!")


def create_consultant_users():
    """Cria usuários para cada consultor existente."""
    with app.app_context():
        consultants = Consultant.query.all()

        for c in consultants:
            # Verifica se já existe usuário para este consultor
            existing = User.query.filter_by(consultant_id=c.id).first()
            if existing:
                print(f"⏭️  Consultor '{c.name}' já tem usuário: {existing.username}")
                continue

            # Cria username a partir do nome (minúsculo, sem espaços)
            username = c.name.lower().replace(' ', '').replace('.', '')

            # Verifica se username já existe
            if User.query.filter_by(username=username).first():
                username = f"{username}{c.id}"

            user = User(
                username=username,
                consultant_id=c.id,
                is_admin=False,
                active=True,
            )
            # Senha inicial = username (deve ser mudada)
            user.set_password(username)

            db.session.add(user)
            print(f"✅ Usuário criado para {c.name}: {username} (senha: {username})")

        db.session.commit()
        print("\n⚠️  Lembre-se de mudar as senhas dos usuários!")


if __name__ == '__main__':
    print("=" * 50)
    print("Criando usuários do sistema")
    print("=" * 50)

    create_admin()
    print()
    create_consultant_users()

    print("\n" + "=" * 50)
    print("Concluído!")
    print("=" * 50)
