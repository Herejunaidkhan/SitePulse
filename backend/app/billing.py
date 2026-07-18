"""Metering + usage-based invoicing (§10)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import db


def current_usage(session: Session, org_id: str) -> dict:
    site_ids = [s.id for s in session.query(db.Site.id).filter(db.Site.org_id == org_id)]
    camera_count = session.query(db.Camera).filter(db.Camera.site_id.in_(site_ids)).count() if site_ids else 0
    sensor_count = session.query(db.IotSensor).filter(db.IotSensor.site_id.in_(site_ids)).count() if site_ids else 0

    org = session.get(db.Organization, org_id)
    plan = session.get(db.BillingPlan, org.billing_plan_id) if org and org.billing_plan_id else None
    if plan is None:
        plan = session.query(db.BillingPlan).first()

    base_fee = plan.base_fee if plan else 500.0
    camera_price = plan.camera_unit_price if plan else 45.0
    sensor_price = plan.sensor_unit_price if plan else 15.0

    total = base_fee + camera_count * camera_price + sensor_count * sensor_price

    return {
        "plan_name": plan.name if plan else "Standard",
        "base_fee": base_fee,
        "camera_count": camera_count,
        "camera_unit_price": camera_price,
        "sensor_count": sensor_count,
        "sensor_unit_price": sensor_price,
        "estimated_total": round(total, 2),
    }
