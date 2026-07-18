"""IoT sensor ingestion stub: proximity (RFID/UWB ground-truth) and vitals (fatigue proxy)."""
from __future__ import annotations

import datetime as dt
import json
import random

from sqlalchemy.orm import Session

from app import db

PROXIMITY_DANGER_METERS = 3.0
FATIGUE_HEART_RATE_THRESHOLD = 120
FATIGUE_SHIFT_MINUTES_THRESHOLD = 480  # 8h


def _get_or_create_sensor(session: Session, site_id: str, sensor_type: str, equipment_id: str | None, worker_id: str | None) -> db.IotSensor:
    query = session.query(db.IotSensor).filter(db.IotSensor.site_id == site_id, db.IotSensor.type == sensor_type)
    if equipment_id:
        query = query.filter(db.IotSensor.equipment_id == equipment_id)
    if worker_id:
        query = query.filter(db.IotSensor.worker_id == worker_id)
    sensor = query.first()
    if sensor is None:
        sensor = db.IotSensor(
            id=db.new_id("sensor"), site_id=site_id, type=sensor_type,
            equipment_id=equipment_id, worker_id=worker_id, status="online",
        )
        session.add(sensor)
        session.flush()
    return sensor


def simulate_reading(
    session: Session,
    site_id: str,
    sensor_type: str,
    equipment_id: str | None = None,
    worker_id: str | None = None,
    value: dict | None = None,
) -> db.SensorReading:
    sensor = _get_or_create_sensor(session, site_id, sensor_type, equipment_id, worker_id)

    if value is None:
        if sensor_type == "proximity":
            value = {"distance_m": round(random.uniform(0.5, 8.0), 2)}
        elif sensor_type == "vitals":
            value = {
                "heart_rate": random.randint(70, 150),
                "shift_minutes": random.randint(60, 600),
            }
        else:
            value = {}

    reading = db.SensorReading(
        id=db.new_id("reading"), sensor_id=sensor.id, timestamp=db.now(),
        value_json=json.dumps(value),
    )
    session.add(reading)
    sensor.last_reading_at = reading.timestamp
    session.flush()
    return reading


def latest_proximity_confirmation(session: Session, site_id: str, equipment_id: str | None, since_minutes: int = 5) -> dict | None:
    """Ground-truth check: does a proximity sensor on this equipment confirm a dangerously close reading recently?"""
    if not equipment_id:
        return None
    since = db.now() - dt.timedelta(minutes=since_minutes)
    reading = (
        session.query(db.SensorReading)
        .join(db.IotSensor, db.SensorReading.sensor_id == db.IotSensor.id)
        .filter(db.IotSensor.site_id == site_id, db.IotSensor.type == "proximity", db.IotSensor.equipment_id == equipment_id)
        .filter(db.SensorReading.timestamp >= since)
        .order_by(db.SensorReading.timestamp.desc())
        .first()
    )
    if reading is None:
        return None
    value = json.loads(reading.value_json)
    distance = value.get("distance_m")
    if distance is None or distance > PROXIMITY_DANGER_METERS:
        return None
    return {"distance_m": distance, "sensor_reading_id": reading.id}


def latest_fatigue_proxy(session: Session, worker_id: str | None, since_minutes: int = 60) -> dict | None:
    """Vitals wearable used only as a risk-context signal, never a medical diagnosis (§8)."""
    if not worker_id:
        return None
    since = db.now() - dt.timedelta(minutes=since_minutes)
    reading = (
        session.query(db.SensorReading)
        .join(db.IotSensor, db.SensorReading.sensor_id == db.IotSensor.id)
        .filter(db.IotSensor.type == "vitals", db.IotSensor.worker_id == worker_id)
        .filter(db.SensorReading.timestamp >= since)
        .order_by(db.SensorReading.timestamp.desc())
        .first()
    )
    if reading is None:
        return None
    value = json.loads(reading.value_json)
    heart_rate = value.get("heart_rate", 0)
    shift_minutes = value.get("shift_minutes", 0)
    elevated = heart_rate >= FATIGUE_HEART_RATE_THRESHOLD or shift_minutes >= FATIGUE_SHIFT_MINUTES_THRESHOLD
    if not elevated:
        return None
    return {"heart_rate": heart_rate, "shift_minutes": shift_minutes}
