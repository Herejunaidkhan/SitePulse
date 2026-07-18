"""Worker/asset location tracking (§6.2): wearable BLE/UWB ground trail, used for
post-incident reconstruction, density heat maps, and dwell-time analytics."""
from __future__ import annotations

import datetime as dt
import random

from sqlalchemy.orm import Session

from app import db


def simulate_ping(session: Session, site_id: str, worker_id: str, zone_id: str | None = None, source: str = "wearable") -> db.WorkerLocationTrail:
    if zone_id is None:
        zones = session.query(db.Zone).filter(db.Zone.site_id == site_id).all()
        zone_id = random.choice(zones).id if zones else None

    ping = db.WorkerLocationTrail(
        id=db.new_id("loc"), worker_id=worker_id, site_id=site_id, zone_id=zone_id,
        timestamp=db.now(), source=source,
    )
    session.add(ping)
    session.flush()
    return ping


def trail_for_range(session: Session, site_id: str, start: dt.datetime, end: dt.datetime, zone_id: str | None = None):
    q = session.query(db.WorkerLocationTrail).filter(
        db.WorkerLocationTrail.site_id == site_id,
        db.WorkerLocationTrail.timestamp >= start,
        db.WorkerLocationTrail.timestamp <= end,
    )
    if zone_id:
        q = q.filter(db.WorkerLocationTrail.zone_id == zone_id)
    return q.order_by(db.WorkerLocationTrail.timestamp.asc()).all()


def dwell_time_by_zone(session: Session, site_id: str, since_hours: int = 24) -> list[dict]:
    """Approximate dwell time per zone by counting pings (each ping ~= one sampling interval)."""
    since = db.now() - dt.timedelta(hours=since_hours)
    pings = (
        session.query(db.WorkerLocationTrail)
        .filter(db.WorkerLocationTrail.site_id == site_id, db.WorkerLocationTrail.timestamp >= since)
        .all()
    )
    zones = {z.id: z.name for z in session.query(db.Zone).filter(db.Zone.site_id == site_id)}
    counts: dict[str, int] = {}
    for ping in pings:
        if ping.zone_id:
            counts[ping.zone_id] = counts.get(ping.zone_id, 0) + 1
    return [{"zone_id": zid, "zone_name": zones.get(zid, "Unknown"), "ping_count": count} for zid, count in counts.items()]
