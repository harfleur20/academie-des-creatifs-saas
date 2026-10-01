"""tara billing integrity fields

Revision ID: 20261001_0005
Revises: 20261001_0004
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0005"
down_revision: str | None = "20261001_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLE = "billing_payment_attempts"
ACTIVATED_FK = "fk_billing_payment_attempts_activated_subscription_id_subscriptions"
TX_INDEX = "ix_billing_payment_attempts_provider_transaction_id"
SUBSCRIPTION_INDEX = "ix_billing_payment_attempts_activated_subscription_id"


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(TABLE)}


def _index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(TABLE) if index.get("name")}


def _foreign_key_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(TABLE)
        if foreign_key.get("name")
    }


def upgrade() -> None:
    # SQLite DDL is non-transactional. A failed historical run of this
    # migration may therefore have created some columns before Alembic stopped.
    # Inspect the real schema so the migration can safely resume.
    columns = _column_names()

    if "checkout_url" not in columns:
        op.add_column(
            TABLE,
            sa.Column("checkout_url", sa.Text(), nullable=True),
        )

    if "provider_transaction_id" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "provider_transaction_id",
                sa.String(length=180),
                nullable=True,
            ),
        )

    columns = _column_names()
    if "activated_subscription_id" not in columns:
        # Add the column first without an inline FK. SQLite cannot ALTER an
        # existing table to append a constraint directly.
        op.add_column(
            TABLE,
            sa.Column("activated_subscription_id", sa.Integer(), nullable=True),
        )

    if "failure_reason" not in _column_names():
        op.add_column(
            TABLE,
            sa.Column("failure_reason", sa.String(length=500), nullable=True),
        )

    # The original migration could fail after adding
    # activated_subscription_id but before creating its FK. Batch mode uses
    # SQLite's copy-and-move strategy and also works on PostgreSQL.
    if ACTIVATED_FK not in _foreign_key_names():
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.create_foreign_key(
                ACTIVATED_FK,
                "subscriptions",
                ["activated_subscription_id"],
                ["id"],
                ondelete="SET NULL",
            )

    indexes = _index_names()
    if TX_INDEX not in indexes:
        op.create_index(
            TX_INDEX,
            TABLE,
            ["provider_transaction_id"],
            unique=True,
        )

    if SUBSCRIPTION_INDEX not in indexes:
        op.create_index(
            SUBSCRIPTION_INDEX,
            TABLE,
            ["activated_subscription_id"],
        )


def downgrade() -> None:
    indexes = _index_names()
    if SUBSCRIPTION_INDEX in indexes:
        op.drop_index(SUBSCRIPTION_INDEX, table_name=TABLE)
    if TX_INDEX in indexes:
        op.drop_index(TX_INDEX, table_name=TABLE)

    # Use batch mode for the FK/column removal as well so downgrade remains
    # SQLite-compatible.
    columns = _column_names()
    with op.batch_alter_table(TABLE) as batch_op:
        foreign_keys = _foreign_key_names()
        if ACTIVATED_FK in foreign_keys:
            batch_op.drop_constraint(ACTIVATED_FK, type_="foreignkey")
        if "failure_reason" in columns:
            batch_op.drop_column("failure_reason")
        if "activated_subscription_id" in columns:
            batch_op.drop_column("activated_subscription_id")
        if "provider_transaction_id" in columns:
            batch_op.drop_column("provider_transaction_id")
        if "checkout_url" in columns:
            batch_op.drop_column("checkout_url")
