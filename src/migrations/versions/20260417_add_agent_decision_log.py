"""add agent_decision_log

Revision ID: add_agent_decision_log_20260417
Revises: add_field_data_only_20260413
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "add_agent_decision_log_20260417"
down_revision = "add_field_data_only_20260413"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_decision_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("chat_id", sa.String(length=64), nullable=True),
        sa.Column("consultant_id", sa.Integer(), nullable=True),
        sa.Column("raw_message", sa.Text(), nullable=True),
        sa.Column("current_state", sa.String(length=80), nullable=True),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("intent_confidence", sa.String(length=20), nullable=True),
        sa.Column("intent_matched_by", sa.String(length=40), nullable=True),
        sa.Column("entities_json", sa.Text(), nullable=True),
        sa.Column("decision_action", sa.String(length=80), nullable=True),
        sa.Column("decision_reason", sa.String(length=300), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("agent_decision_log", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_platform"),
            ["platform"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_chat_id"),
            ["chat_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_consultant_id"),
            ["consultant_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_intent"),
            ["intent"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_decision_action"),
            ["decision_action"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_decision_log_created_at"),
            ["created_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("agent_decision_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_created_at"))
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_decision_action"))
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_intent"))
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_consultant_id"))
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_chat_id"))
        batch_op.drop_index(batch_op.f("ix_agent_decision_log_platform"))

    op.drop_table("agent_decision_log")
