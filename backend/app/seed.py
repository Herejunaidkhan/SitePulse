from __future__ import annotations

import datetime as dt
import random
import uuid

from app import alerting, auth, cv_stub, db, emr, risk_engine


def _make_site(session, org, name, address, zone_specs, worker_specs, equipment_specs, camera_specs, ppe_specs):
    site = db.Site(id=db.new_id("site"), org_id=org.id, name=name, address=address, status="active", onboarding_stage="live")
    session.add(site)
    session.flush()

    zones = {}
    for key, zname, ztype, risk in zone_specs:
        z = db.Zone(id=db.new_id("zone"), site_id=site.id, name=zname, zone_type=ztype, risk_category=risk)
        session.add(z)
        session.flush()
        zones[key] = z

    for zkey, ppe_type, trade in ppe_specs:
        session.add(db.PPERequirement(id=db.new_id("ppe"), zone_id=zones[zkey].id, ppe_type=ppe_type, trade_applicability=trade))

    workers = []
    for wname, trade, badge, consent in worker_specs:
        w = db.Worker(
            id=db.new_id("worker"), site_id=site.id, org_id=org.id, name=wname, trade=trade, badge_id=badge,
            wearable_device_id=f"wd-{uuid.uuid4().hex[:6]}", biometric_consent=consent,
        )
        session.add(w)
        workers.append(w)

    equipment = []
    for etype, state in equipment_specs:
        eq = db.Equipment(id=db.new_id("equip"), site_id=site.id, type=etype, operating_state=state)
        session.add(eq)
        equipment.append(eq)

    for ctype, location in camera_specs:
        session.add(db.Camera(id=db.new_id("cam"), site_id=site.id, type=ctype, install_location=location))

    session.flush()
    return site, zones, workers, equipment


def _backfill_history(session, site, safety_user_id, days=12, events_per_day=(1, 4)):
    """Populate days of realistic history so the demo doesn't open empty."""
    now = db.now()
    zone_list = session.query(db.Zone).filter(db.Zone.site_id == site.id).all()
    if not zone_list:
        return

    for day_offset in range(days, 0, -1):
        day_start = now - dt.timedelta(days=day_offset)
        for _ in range(random.randint(*events_per_day)):
            event_time = day_start.replace(hour=random.randint(6, 17), minute=random.randint(0, 59), second=0, microsecond=0)

            detection = cv_stub.simulate_detection(session, site.id)
            detection.timestamp = event_time
            session.flush()

            risk_event = risk_engine.score_detection(session, detection)
            risk_event.created_at = event_time
            session.flush()

            alerts = alerting.create_alerts_for_risk_event(session, risk_event)
            for a in alerts:
                a.sent_at = event_time
                a.delivered_at = event_time

            roll = random.random()
            if roll < 0.55:
                ack_time = event_time + dt.timedelta(minutes=random.randint(1, 30))
                resolve_time = ack_time + dt.timedelta(minutes=random.randint(5, 180))
                risk_event.status = "resolved"
                risk_event.acknowledged_at = ack_time
                risk_event.resolved_at = resolve_time
                risk_event.resolved_by = safety_user_id
                risk_event.intervention_notes = random.choice([
                    "Briefed crew and corrected PPE before resuming work.",
                    "Equipment operator paused swing until zone was clear.",
                    "Added temporary barricade and re-tagged the opening.",
                    "Worker re-fitted harness and reconnected to anchor point.",
                ])
                for a in alerts:
                    a.acknowledged_at = ack_time
                    a.response_time_seconds = (ack_time - a.sent_at).total_seconds()
                bonus = emr.create_bonus_if_eligible(session, risk_event)
                if bonus and random.random() < 0.6:
                    bonus.verification_status = "verified"
                    bonus.verified_by = safety_user_id
            elif roll < 0.68:
                risk_event.status = "false_positive"
                risk_event.resolved_at = event_time + dt.timedelta(minutes=random.randint(5, 60))
                risk_event.resolved_by = safety_user_id
            elif roll < 0.85:
                ack_time = event_time + dt.timedelta(minutes=random.randint(1, 45))
                risk_event.status = "acknowledged"
                risk_event.acknowledged_at = ack_time
                for a in alerts:
                    a.acknowledged_at = ack_time
                    a.response_time_seconds = (ack_time - a.sent_at).total_seconds()
            # else: leave "open" so recent history still has live alerts

            if random.random() < 0.15:
                session.add(db.IncidentLog(
                    id=db.new_id("incident"), site_id=site.id, risk_event_id=risk_event.id,
                    type=random.choice(["near_miss", "violation"]), reported_by=safety_user_id,
                    description="Logged during routine walk-through following this alert.",
                    severity=risk_event.risk_category, injury_flag=False, created_at=event_time,
                ))

            session.flush()

    session.add(db.CalibrationLog(
        id=db.new_id("calib"), site_id=site.id, threshold_type="ppe_confidence_min",
        old_value="0.55", new_value="0.65", changed_by=safety_user_id, changed_at=now - dt.timedelta(days=6),
        justification="Reduce false positives from reflective vests at dawn shift change.",
    ))
    session.add(db.CalibrationLog(
        id=db.new_id("calib"), site_id=site.id, threshold_type="proximity_danger_radius_m",
        old_value="4.0", new_value="3.0", changed_by=safety_user_id, changed_at=now - dt.timedelta(days=3),
        justification="Tightened after near-miss review showed 4m was too conservative for this site's equipment.",
    ))
    session.commit()


def seed():
    db.init_db()
    session = db.SessionLocal()
    try:
        plan = db.BillingPlan(id=db.new_id("plan"), name="Pro", base_fee=500.0, camera_unit_price=45.0, sensor_unit_price=15.0)
        session.add(plan)
        session.flush()

        org = db.Organization(
            id=db.new_id("org"), name="GreenGrid Construction", tier="pro",
            billing_plan_id=plan.id, insurer_api_key=f"ins_{uuid.uuid4().hex[:20]}",
        )
        session.add(org)
        session.flush()

        patterns = [
            db.OshaIncidentPattern(
                id=db.new_id("osha"), pattern_name="Fall from unprotected edge",
                description="Worker at height near an unguarded edge or opening without an anchored fall-arrest connection.",
                correlated_detection_types="fall_risk_posture,unguarded_edge",
                base_severity_weight=40.0, source_citation="29 CFR 1926.501",
            ),
            db.OshaIncidentPattern(
                id=db.new_id("osha"), pattern_name="Struck-by mobile equipment",
                description="Worker within the danger zone or swing radius of operating heavy equipment.",
                correlated_detection_types="proximity",
                base_severity_weight=30.0, source_citation="29 CFR 1926.601",
            ),
            db.OshaIncidentPattern(
                id=db.new_id("osha"), pattern_name="Head injury - missing hard hat",
                description="Worker in an active construction zone without required head protection.",
                correlated_detection_types="ppe_violation",
                base_severity_weight=15.0, source_citation="29 CFR 1926.100",
            ),
        ]
        session.add_all(patterns)
        session.flush()

        users = [
            db.User(id=db.new_id("user"), org_id=org.id, site_id=None, email="admin@sitepulse.demo",
                    password_hash=auth.hash_password("password123"), name="Sam Rivera", role="admin"),
            db.User(id=db.new_id("user"), org_id=org.id, site_id=None, email="safety@sitepulse.demo",
                    password_hash=auth.hash_password("password123"), name="Jordan Blake", role="safety_officer"),
            db.User(id=db.new_id("user"), org_id=org.id, site_id=None, email="foreman@sitepulse.demo",
                    password_hash=auth.hash_password("password123"), name="Casey Nguyen", role="foreman"),
        ]
        session.add_all(users)
        session.flush()
        safety_user_id = users[1].id

        # ---------------------------------------------------------- Site A: high-rise
        site_a, _, _, _ = _make_site(
            session, org, "Riverside Tower - Site A", "450 Riverside Dr",
            zone_specs=[
                ("edge", "Level 12 East Edge", "edge", "critical"),
                ("crane", "Crane Swing Radius - Tower Crane 1", "crane_swing", "high"),
                ("staging", "Ground Level Staging", "general", "low"),
                ("rebar", "Level 6 Rebar Deck", "general", "medium"),
            ],
            worker_specs=[
                ("Marcus Alvarez", "ironworker", "B-1001", True),
                ("Priya Nair", "electrician", "B-1002", True),
                ("Devon Cole", "carpenter", "B-1003", False),
                ("Lena Ortiz", "crane_operator", "B-1004", True),
            ],
            equipment_specs=[("tower_crane", "active"), ("excavator", "idle")],
            camera_specs=[("fixed", "Level 12 East corner"), ("fixed", "Crane cab"), ("wearable", "Foreman hard hat")],
            ppe_specs=[
                ("edge", "harness", "all"), ("edge", "hard_hat", "all"),
                ("crane", "hi_vis_vest", "all"),
                ("rebar", "hard_hat", "all"), ("rebar", "safety_glasses", "ironworker"),
            ],
        )

        # ---------------------------------------------------------- Site B: bridge rehab
        site_b, _, _, _ = _make_site(
            session, org, "Harbor Bridge Rehab - Site B", "1 Harbor Crossing",
            zone_specs=[
                ("deck", "Bridge Deck - Pier 4 Access", "edge", "critical"),
                ("barge", "Barge Crane Zone", "crane_swing", "high"),
                ("yard", "Staging Yard", "general", "low"),
                ("chamber", "Cable Anchorage Chamber", "confined_space", "high"),
            ],
            worker_specs=[
                ("Ray Delgado", "welder", "H-2001", True),
                ("Simone Achebe", "rigger", "H-2002", True),
                ("Tomas Reyes", "diver_support", "H-2003", True),
                ("Fiona Walsh", "inspector", "H-2004", False),
            ],
            equipment_specs=[("barge_crane", "active"), ("welding_rig", "active")],
            camera_specs=[("fixed", "Pier 4 access ladder"), ("fixed", "Barge crane cab"), ("wearable", "Inspector helmet")],
            ppe_specs=[
                ("deck", "harness", "all"), ("deck", "hi_vis_vest", "all"),
                ("barge", "hard_hat", "all"),
                ("chamber", "harness", "all"), ("chamber", "gloves", "all"),
            ],
        )

        # ---------------------------------------------------------- Site C: rail yard
        site_c, _, _, _ = _make_site(
            session, org, "Metro Rail Yard - Site C", "88 Depot Road",
            zone_specs=[
                ("track", "Active Track 3", "general", "high"),
                ("catenary", "Overhead Catenary Zone", "edge", "critical"),
                ("bay", "Rolling Stock Bay", "general", "medium"),
                ("perimeter", "Yard Perimeter", "general", "low"),
            ],
            worker_specs=[
                ("Aisha Rahman", "track_worker", "R-3001", True),
                ("Ben Okafor", "signal_technician", "R-3002", True),
                ("Grace Lindqvist", "electrician", "R-3003", True),
                ("Marco Ferretti", "yard_supervisor", "R-3004", True),
            ],
            equipment_specs=[("ballast_tamper", "active"), ("crane_truck", "idle")],
            camera_specs=[("fixed", "Track 3 signal mast"), ("fixed", "Catenary gantry"), ("wearable", "Supervisor vest")],
            ppe_specs=[
                ("track", "hi_vis_vest", "all"), ("track", "hard_hat", "all"),
                ("catenary", "harness", "all"), ("catenary", "gloves", "electrician"),
                ("bay", "hard_hat", "all"),
            ],
        )

        session.commit()

        for site in (site_a, site_b, site_c):
            _backfill_history(session, site, safety_user_id, days=12, events_per_day=(1, 4))

        print(f"Seeded org={org.id} with 3 sites: {site_a.id}, {site_b.id}, {site_c.id}")
        print("Demo logins (password: password123): admin@sitepulse.demo, safety@sitepulse.demo, foreman@sitepulse.demo")
        print(f"Insurer/GC reporting API key for {org.name}: {org.insurer_api_key}")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
