"""Initial users, links and click events

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision="0001"
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("name",sa.String(90),nullable=False),
        sa.Column("email",sa.String(254),nullable=False),
        sa.Column("password_hash",sa.String(255),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_users_email","users",["email"],unique=True)
    op.create_table("links",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("owner_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("slug",sa.String(40),nullable=False),
        sa.Column("target_url",sa.Text(),nullable=False),
        sa.Column("title",sa.String(120),nullable=False),
        sa.Column("description",sa.String(280),nullable=False),
        sa.Column("tags",sa.String(240),nullable=False),
        sa.Column("is_active",sa.Boolean(),nullable=False),
        sa.Column("expires_at",sa.DateTime(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.Column("click_count",sa.Integer(),nullable=False))
    op.create_index("ix_links_owner_id","links",["owner_id"])
    op.create_index("ix_links_slug","links",["slug"],unique=True)
    op.create_table("clicks",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("link_id",sa.Integer(),sa.ForeignKey("links.id",ondelete="CASCADE"),nullable=False),
        sa.Column("clicked_at",sa.DateTime(),nullable=False),
        sa.Column("fingerprint",sa.String(64),nullable=False),
        sa.Column("is_unique",sa.Boolean(),nullable=False),
        sa.Column("is_bot",sa.Boolean(),nullable=False),
        sa.Column("referrer",sa.String(200),nullable=False),
        sa.Column("device",sa.String(30),nullable=False),
        sa.Column("browser",sa.String(40),nullable=False),
        sa.Column("platform",sa.String(40),nullable=False),
        sa.Column("utm_source",sa.String(100),nullable=False),
        sa.Column("utm_medium",sa.String(100),nullable=False),
        sa.Column("utm_campaign",sa.String(100),nullable=False))
    op.create_index("ix_clicks_link_id","clicks",["link_id"])
    op.create_index("ix_clicks_clicked_at","clicks",["clicked_at"])
    op.create_index("ix_clicks_link_time","clicks",["link_id","clicked_at"])


def downgrade():
    op.drop_table("clicks")
    op.drop_table("links")
    op.drop_table("users")
