import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

Base = declarative_base()

class Zone(Base):
    __tablename__ = "zones"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(64), nullable=False)
    osmnx_name = sa.Column(sa.String(64), nullable=False)
    zone_generations = relationship("ZoneGeneration", back_populates="zone")

    def __repr__(self):
        return f"<Zone id={self.id} name={self.name} osxmn_name={self.osmnx_name}>"

class ZoneGeneration(Base):
    __tablename__ = "zone_generations"
    id = sa.Column(sa.Integer, primary_key=True)
    zone_id = sa.Column(sa.Integer, sa.ForeignKey("zones.id"))
    generation = sa.Column(sa.Integer)
    final_timestamp = sa.Column(sa.DateTime)
    zone = relationship("Zone", back_populates="zone_generations")

    def __repr__(self):
        return (
            f"""<ZoneGeneration id={self.id} zone_id={self.zone_id} """
            f"""generation={self.generation} final_timestamp={self.final_timestamp}>"""
        )

class Sector(Base):
    __tablename__ = "sectors"
    id = sa.Column(sa.Integer, primary_key=True)
    geometry = sa.Column(Geometry)

    def __repr__(self):
        return f"<Sector id={self.id} geometry={self.geometry}>"

class Centerline(Base):
    __tablename__ = "centerlines"
    id = sa.Column(sa.Integer, primary_key=True)
    geometry = sa.Column("geometry", Geometry("LINESTRING"))
    first_zone_generation = sa.Column("first_zone_generation", sa.Integer)
    last_zone_generation = sa.Column("last_zone_generation", sa.Integer, nullable=True)
    zone_id = sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False)
    osmid = sa.Column("osmid", sa.Integer, nullable=False)
    name = sa.Column("name", sa.String, nullable=False)
    pickups = relationship("Pickup", back_populates="centerline")

    def __repr__(self):
        return (
            f"""<Centerline name={self.name} id={self.id} geometry={self.geometry} """
            f"""first_zone_generation={self.first_zone_generation} """
            f"""last_zone_generation={self.last_zone_generation} """
            f"""zone_id={self.zone_id}> osmnid={self.osmid}"""
        )

class Pickup(Base):
    __tablename__ = "pickups"
    id = sa.Column("id", sa.Integer, primary_key=True)
    firebase_id = sa.Column("firebase_id", sa.Integer, nullable=False)
    centerline_id =\
        sa.Column("centerline_id", sa.Integer, sa.ForeignKey("centerlines.id"), nullable=False)
    type = sa.Column("type", sa.Integer, nullable=False)
    timestamp = sa.Column("timestamp", sa.DateTime, nullable=False)
    geometry = sa.Column("geometry", Geometry("POINT"), nullable=False)
    snapped_geometry = sa.Column("snapped_geometry", Geometry("POINT"), nullable=False)
    linear_reference = sa.Column("linear_reference", sa.Float(precision=3))
    curb = sa.Column("curb", sa.Integer, nullable=False)
    centerline = relationship("Centerline", back_populates="pickups")

    def __repr__(self):
        return (
            f"""<Pickup id={self.id} """
            f"""geometry={self.geometry} snapped_geometry={self.snapped_geometry} """
            f"""centerline_id={self.centerline_id} firebase_id={self.firebase_id} """
            f"""type={self.type} timestamp={self.timestamp} """
            f"""linear_reference={self.linear_reference} curb={self.curb}>"""
        )
