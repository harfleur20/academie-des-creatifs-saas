"""Canonical public school slugs with preserved aliases.

Revision ID: 20261007_0047
Revises: 20261007_0046
"""

from collections.abc import Sequence
import re
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "20261007_0047"
down_revision = "20261007_0046"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:120]


def upgrade() -> None:
    op.create_table(
        "organization_slug_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_organization_slug_aliases_slug"),
    )
    op.create_index(
        "ix_organization_slug_aliases_org",
        "organization_slug_aliases",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_slug_aliases_organization_id",
        "organization_slug_aliases",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_slug_aliases_slug",
        "organization_slug_aliases",
        ["slug"],
        unique=True,
    )

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT o.id, o.slug, s.site_name "
                "FROM organizations o "
                "JOIN organization_public_sites s ON s.organization_id = o.id "
                "ORDER BY o.id"
            )
        ).mappings()
    )
    original = {str(row["slug"]).lower(): int(row["id"]) for row in rows}
    chosen: set[str] = set()

    for row in rows:
        organization_id = int(row["id"])
        old_slug = str(row["slug"])
        base = _slugify(str(row["site_name"] or "")) or old_slug
        candidate = base
        suffix = 1
        while (
            candidate.lower() in chosen
            or (
                candidate.lower() in original
                and original[candidate.lower()] != organization_id
            )
        ):
            suffix += 1
            marker = f"-{suffix}"
            candidate = f"{base[:120-len(marker)]}{marker}"
        chosen.add(candidate.lower())

        if candidate == old_slug:
            continue

        bind.execute(
            sa.text(
                "INSERT INTO organization_slug_aliases "
                "(organization_id, slug) VALUES (:organization_id, :slug)"
            ),
            {"organization_id": organization_id, "slug": old_slug},
        )
        bind.execute(
            sa.text("UPDATE organizations SET slug = :slug WHERE id = :organization_id"),
            {"organization_id": organization_id, "slug": candidate},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT organization_id, slug FROM organization_slug_aliases "
                "ORDER BY organization_id, id"
            )
        ).mappings()
    )
    restored: set[int] = set()
    for row in rows:
        organization_id = int(row["organization_id"])
        if organization_id in restored:
            continue
        bind.execute(
            sa.text("UPDATE organizations SET slug = :slug WHERE id = :organization_id"),
            {"organization_id": organization_id, "slug": str(row["slug"])},
        )
        restored.add(organization_id)

    op.drop_index("ix_organization_slug_aliases_slug", table_name="organization_slug_aliases")
    op.drop_index("ix_organization_slug_aliases_organization_id", table_name="organization_slug_aliases")
    op.drop_index("ix_organization_slug_aliases_org", table_name="organization_slug_aliases")
    op.drop_table("organization_slug_aliases")
