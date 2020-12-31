"""
Change type of curb field from ENUM(..., "center") to ENUM(..., "middle").

Revision ID: 314f1a2e85e9
Revises: a3fa9dac3f4e
Create Date: 2020-12-30 18:55:14.292171

"""
from alembic import op
# import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = '314f1a2e85e9'
down_revision = 'a3fa9dac3f4e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("pickups", "curb", type_=ENUM("left", "right", "middle", name="curb"))


def downgrade():
    op.alter_column("pickups", "curb", type_=ENUM("left", "right", "center", name="curb"))
