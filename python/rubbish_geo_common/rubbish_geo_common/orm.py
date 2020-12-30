import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from rubbish_geo_common.consts import RUBBISH_TYPES

Base = declarative_base()

class Zone(Base):
    __tablename__ = "zones"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(64), nullable=False)
    osmnx_name = sa.Column(sa.String(64), nullable=False)
    bounding_box = sa.Column(Geometry("POLYGON"), nullable=False)
    zone_generations = relationship("ZoneGeneration", back_populates="zone")

    def __repr__(self):
        return (
            f"""<Zone id={self.id} name={self.name} osxmn_name={self.osmnx_name} """
            f"""bounding_box={self.bounding_box}>"""
        )

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
    name = sa.Column(sa.String)
    geometry = sa.Column(Geometry)

    def __repr__(self):
        return f"<Sector id={self.id} name={self.name} geometry={self.geometry}>"

class Centerline(Base):
    __tablename__ = "centerlines"
    id = sa.Column(sa.Integer, primary_key=True)
    geometry = sa.Column("geometry", Geometry("LINESTRING"))
    first_zone_generation = sa.Column("first_zone_generation", sa.Integer)
    last_zone_generation = sa.Column("last_zone_generation", sa.Integer, nullable=True)
    zone_id = sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False)
    osmid = sa.Column("osmid", sa.Integer, nullable=False)
    name = sa.Column("name", sa.String, nullable=False)
    length_in_meters = sa.Column("length_in_meters", sa.Float, nullable=False)
    pickups = relationship("Pickup", back_populates="centerline")
    blockface_statistics = relationship("BlockfaceStatistic", back_populates="centerline")

    def __repr__(self):
        return (
            f"""<Centerline name={self.name} id={self.id} geometry={self.geometry} """
            f"""first_zone_generation={self.first_zone_generation} """
            f"""last_zone_generation={self.last_zone_generation} """
            f"""length_in_meters={self.length_in_meters} zone_id={self.zone_id} """
            f"""osmnid={self.osmid}>"""
        )

class Pickup(Base):
    __tablename__ = "pickups"
    id = sa.Column("id", sa.Integer, primary_key=True)
    firebase_id = sa.Column("firebase_id", sa.String, nullable=False)
    firebase_run_id = sa.Column("firebase_run_id", sa.String, nullable=False)
    centerline_id =\
        sa.Column("centerline_id", sa.Integer, sa.ForeignKey("centerlines.id"), nullable=False)
    type = sa.Column("type", ENUM(*RUBBISH_TYPES, name="rubbish_type"), nullable=False)
    timestamp = sa.Column("timestamp", sa.DateTime, nullable=False)
    geometry = sa.Column("geometry", Geometry("POINT"), nullable=False)
    snapped_geometry = sa.Column("snapped_geometry", Geometry("POINT"), nullable=False)
    linear_reference = sa.Column("linear_reference", sa.Float(precision=3), nullable=False)
    curb = sa.Column("curb", ENUM('left', 'right', 'middle', name='curb'), nullable=False)
    centerline = relationship("Centerline", back_populates="pickups")

    def __repr__(self):
        return (
            f"""<Pickup id={self.id} """
            f"""geometry={self.geometry} snapped_geometry={self.snapped_geometry} """
            f"""centerline_id={self.centerline_id} firebase_id={self.firebase_id} """
            f"""firebase_run_id={self.firebase_run_id} """
            f"""type={self.type} timestamp={self.timestamp} """
            f"""linear_reference={self.linear_reference} curb={self.curb}>"""
        )

class BlockfaceStatistic(Base):
    __tablename__ = "blockface_statistics"
    id = sa.Column("id", sa.Integer, primary_key=True)
    centerline_id =\
        sa.Column("centerline_id", sa.Integer, sa.ForeignKey("centerlines.id"), nullable=False)
    curb = sa.Column("curb", ENUM('left', 'right', 'middle', name='curb'), nullable=False)
    rubbish_per_meter = sa.Column("rubbish_per_meter", sa.Float, nullable=False)
    num_runs = sa.Column("num_runs", sa.Integer, nullable=False)
    centerline = relationship("Centerline", back_populates="blockface_statistics")

    def __repr__(self):
        return (
            f"""<BlockfaceStatistic id={self.id} centerline_id={self.centerline_id} """
            f"""curb={self.curb} rubbish_per_meter={self.rubbish_per_meter} """
            f"""num_runs={self.num_runs}>"""
        )

__all__ = ['Zone', 'ZoneGeneration', 'Sector', 'Centerline', 'Pickup', 'BlockfaceStatistic']
