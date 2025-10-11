"""Database utilities for simple schema adjustments without losing data.

Functions provided:
- create_tables(app): run SQLAlchemy create_all()
- drop_unknown_tables(app): drop tables present in DB but not defined in models
- add_missing_columns(app): add missing columns to existing tables (ALTER TABLE ADD COLUMN)

Notes:
- These helpers are intended for simple development/testing workflows. For production
  schema migrations use Alembic (recommended).
- Adding columns will always create nullable columns (never add NOT NULL without a default)
  to avoid data loss or errors when existing rows are present.
"""
from typing import List
from sqlalchemy import MetaData, Table, text
from sqlalchemy.exc import SQLAlchemyError
from models import db


def create_tables(app) -> None:
    """Create all tables defined in SQLAlchemy models."""
    with app.app_context():
        db.create_all()


def drop_unknown_tables(app, *, preview: bool = True) -> List[str]:
    """Drop tables that exist in the database but are not defined by the models.

    Returns list of dropped table names. If preview=True, returns the list without dropping.
    """
    dropped = []
    with app.app_context():
        engine = db.get_engine(app)
        existing_meta = MetaData()
        existing_meta.reflect(bind=engine)

        model_table_names = set(db.metadata.tables.keys())
        existing_table_names = set(existing_meta.tables.keys())

        unknown = existing_table_names - model_table_names
        if not unknown:
            return []

        if preview:
            return list(unknown)

        for tname in unknown:
            try:
                tbl = existing_meta.tables[tname]
                tbl.drop(engine)
                dropped.append(tname)
            except SQLAlchemyError as e:
                # continue on error but record
                print(f"Failed to drop {tname}: {e}")
    return dropped


def add_missing_columns(app) -> List[str]:
    """Add columns that are defined in models but missing in the existing DB tables.

    Returns a list of added columns in format 'table.column'.
    Behavior:
    - Adds columns using ALTER TABLE ... ADD COLUMN ...
    - Always adds columns as nullable to avoid data loss.
    - Does not remove or alter existing columns.
    """
    added = []
    with app.app_context():
        engine = db.get_engine(app)
        existing_meta = MetaData()
        existing_meta.reflect(bind=engine)

        for tname, model_table in db.metadata.tables.items():
            # get existing table if present
            if tname not in existing_meta.tables:
                # table doesn't exist in DB; create it fully
                try:
                    model_table.create(engine)
                    added.append(f"{tname} (created)")
                except SQLAlchemyError as e:
                    print(f"Failed to create table {tname}: {e}")
                continue

            existing_table = existing_meta.tables[tname]
            model_cols = {c.name: c for c in model_table.columns}
            existing_cols = set(existing_table.columns.keys())

            missing = [name for name in model_cols.keys() if name not in existing_cols]
            if not missing:
                continue

            for col_name in missing:
                col = model_cols[col_name]
                # Try to compile column type for the target dialect
                try:
                    col_type = col.type.compile(engine.dialect)
                except Exception:
                    # fallback to generic string representation
                    col_type = str(col.type)

                # Build ALTER TABLE statement; keep new column nullable to avoid data loss
                sql = f'ALTER TABLE "{tname}" ADD COLUMN "{col_name}" {col_type}'

                # If there is a server_default, include DEFAULT
                if col.server_default is not None:
                    # server_default may be a ClauseElement; try to render a text
                    try:
                        default_text = str(col.server_default.arg)
                        sql += f' DEFAULT {default_text}'
                    except Exception:
                        pass

                # Note: do NOT add NOT NULL constraints here
                try:
                    with engine.connect() as conn:
                        conn.execute(text(sql))
                    added.append(f"{tname}.{col_name}")
                except SQLAlchemyError as e:
                    print(f"Failed to add column {tname}.{col_name}: {e}")
    return added


if __name__ == '__main__':
    import argparse
    from app import create_app

    parser = argparse.ArgumentParser(description='DB utilities')
    parser.add_argument('--create', action='store_true', help='Run create_all()')
    parser.add_argument('--drop-preview', action='store_true', help='Preview unknown tables to drop')
    parser.add_argument('--drop', action='store_true', help='Drop unknown tables')
    parser.add_argument('--add-columns', action='store_true', help='Add missing columns to existing tables')

    args = parser.parse_args()
    app = create_app()

    if args.create:
        create_tables(app)
        print('create_all() executed')

    if args.drop_preview:
        unknown = drop_unknown_tables(app, preview=True)
        print('Unknown tables:', unknown)

    if args.drop:
        dropped = drop_unknown_tables(app, preview=False)
        print('Dropped tables:', dropped)

    if args.add_columns:
        added = add_missing_columns(app)
        print('Added columns/tables:', added)
