"""Calendrier de préparation et validation de ses données persistantes."""
from datetime import date
import json
import re
from uuid import uuid4

TEMPLATE_TYPES = {"PPG", "CAP", "CUI", "ENP", "FRC", "ISI", "MID", "MON", "REC"}

def planning_text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError("Libellé ou note de planning incorrect.")
    return value.strip()


def planning_date(value):
    try:
        day = date.fromisoformat(value)
        if day.isoformat() == value and 1900 <= day.year <= 9998:
            return value
    except (TypeError, ValueError):
        pass
    raise ValueError("Date de planning incorrecte.")


def duration(value):
    if type(value) is not int or not 0 <= value <= 1440:
        raise ValueError("La durée doit être comprise entre 0 et 1 440 minutes.")
    return value


def validate_planning(data, source_exists):
    if not isinstance(data, dict):
        raise ValueError("Planning incorrect.")
    types, sessions = data.get("types"), data.get("sessions")
    if not isinstance(types, list) or len(types) > 80 or not isinstance(sessions, list) or len(sessions) > 1000:
        raise ValueError("Le planning accepte 80 types et 1 000 séances au maximum.")
    if any(not isinstance(item, dict) for item in [*types, *sessions]):
        raise ValueError("Séance ou type incorrect.")
    names, codes = {}, set()
    for item in types:
        name = planning_text(item.get("name"), 80, True)
        if name.casefold() in names:
            raise ValueError("Chaque type doit avoir un nom distinct.")
        entry = dict(name=name, minutes=duration(item.get("minutes")))
        code = item.get("code")
        if code is not None:
            if not isinstance(code, str) or code not in TEMPLATE_TYPES or code in codes:
                raise ValueError("Type de modèle de préparation incorrect.")
            codes.add(code)
            entry["code"] = code
        names[name.casefold()] = entry
    clean_sessions = []
    for item in sessions:
        kind = planning_text(item.get("type"), 80, True)
        if kind.casefold() not in names:
            raise ValueError("Type de séance inconnu.")
        session = dict(date=planning_date(item.get("date")), type=names[kind.casefold()]["name"],
                       minutes=duration(item.get("minutes")), note=planning_text(item.get("note", ""), 500))
        if item.get("goalOffset") is not None:
            offset = item["goalOffset"]
            if type(offset) is not int or not -84 <= offset <= -1:
                raise ValueError("Échéance de rétroplanning incorrecte.")
            session["goalOffset"] = offset
        clean_sessions.append(session)
    goal = data.get("goal")
    if goal is not None:
        if not isinstance(goal, dict):
            raise ValueError("Course objectif incorrecte.")
        trace = goal.get("sourceId") or ""
        if not isinstance(trace, str) or (trace and (not re.fullmatch("[a-f0-9]{64}", trace) or not source_exists(trace))):
            raise ValueError("La trace de la course objectif est indisponible.")
        goal = dict(date=planning_date(goal.get("date")), name=planning_text(goal.get("name"), 120, True),
                    sourceId=trace, filename=planning_text(goal.get("filename", ""), 180) if trace else "")
    return dict(types=list(names.values()), sessions=clean_sessions, goal=goal)


def planning_table(db):
    # Une restauration issue d'une ancienne version peut remplacer la base sans cette table.
    db.execute("""CREATE TABLE IF NOT EXISTS training_planning
                  (id INTEGER PRIMARY KEY CHECK(id=1), revision TEXT NOT NULL, payload TEXT NOT NULL)""")


def read_planning(store):
    with store.connection() as db:
        planning_table(db)
        row = db.execute("SELECT revision, payload FROM training_planning WHERE id=1").fetchone()
    return dict(revision=row["revision"], planning=json.loads(row["payload"])) if row else dict(revision=None, planning=None)


def save_planning(store, options):
    plan = validate_planning(options.get("planning"), lambda key:
                            (store.path.parent / "parcours-importes" / (key + ".gpx")).is_file())
    revision = uuid4().hex
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        planning_table(db)
        current = db.execute("SELECT revision FROM training_planning WHERE id=1").fetchone()
        if options.get("revision") != (current["revision"] if current else None):
            return None
        db.execute("INSERT OR REPLACE INTO training_planning VALUES (1, ?, ?)",
                   (revision, json.dumps(plan, ensure_ascii=False)))
    return dict(revision=revision, planning=plan)
