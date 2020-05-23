"""Initialize DB.

NOTE: the table definitions here must be kept in sync with those in python.common.orm.

Revision ID: a3fa9dac3f4e
Revises: 
Create Date: 2020-05-22 13:04:13.231880

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision = "a3fa9dac3f4e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Zones are meaningful regions, e.g. "San Francisco", meant to be imported all at once.
    # Zones have zone generations. Centerlines are keyed to specific zone generations.
    op.create_table(
        "Zones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("osmnx_name", sa.String(64), nullable=False)  # used by the importer
    )
    # Zone generations allow for changes in the street grid over time.
    op.create_table(
        "ZoneGenerations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("Zones.id"), nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("final_timestamp", sa.DateTime, nullable=True)  # NULL means "current"
    )
    # Sectors are areas of interest (e.g. neighborhoods). These are mainly useful for UX.
    op.create_table(
        "Sectors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("geometry", Geometry("MULTIPOLYGON"))
    )
    # Centerlines are the workhorse of the Rubbish app.
    # Each centerline is an individual street segment of a constrained complexity.
    # Rubbish pickups are keyed to centerline and side-of-street.
    # Centerlines are keyed to a zone and a range of zone generations.
    op.create_table(
        "Centerlines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("geometry", Geometry("LINESTRING")),
        sa.Column("first_zone_generation", sa.Integer),
        sa.Column("last_zone_generation", sa.Integer, nullable=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("Zones.id"), nullable=False)
    )
    # Pickups are the event type of interest.
    # Note that most non-geometric properties are in Firebase.
    op.create_table(
        "Pickups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("firebase_id", sa.Integer, nullable=False),  # foreign key to the app DB
        sa.Column("centerline_id", sa.Integer, sa.ForeignKey("Centerlines.id"), nullable=False),
        sa.Column("type", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("geometry", Geometry("POINT"), nullable=False),
        sa.Column("snapped_geometry", Geometry("POINT"), nullable=False),
        sa.Column("linear_reference", sa.Float(precision=3)),
        sa.Column("curb", sa.Integer, nullable=False),  # side-of-street
    )


def downgrade():
    op.drop_table("Pickups")
    op.drop_table("Centerlines")
    op.drop_table("Sectors")
    op.drop_table("ZoneGenerations")
    op.drop_table("Zones")
