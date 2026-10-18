# Imports muscles, equipment and exercises from the public wger API into our database.
# wger is only called here, once, from your computer. The website itself keeps reading
# from our own database, so it still works if wger is slow or offline.

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from typing import Iterator, Optional

from sqlalchemy import func, select

import app.models
from app.db.session import SessionLocal
from app.models import Equipment, Exercise, ExerciseMuscle, MuscleGroup

BASE = "https://wger.de/api/v2"
ENGLISH = 2          # wger's language id for English
PAGE_SIZE = 100

MUSCLE_RENAMES: dict = {} #used for demo data test

# I don't see wger has difficulty, role or duration.
# These are our own defaults, not wger data. Change them if needed
HARDER_EQUIPMENT = {"barbell", "sz-bar", "kettlebell"}
CORE_MINUTES, ACCESSORY_MINUTES = 8, 5

# connecting with wger api
def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "ascenda-csc648-import"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(f"wger request failed: {url} ({error})")
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")

def paginate(url: str) -> Iterator[dict]:
    """Yields every result, following wger's 'next' links page by page."""
    while url:
        data = fetch_json(url)
        yield from data.get("results", [])
        url = data.get("next")
        if url:
            url = url.replace("http://", "https://", 1)

# cleaning and rules (no database needed)
def clean_text(value: Optional[str]) -> str:
    """wger descriptions contain HTML such as <p>; keep plain text."""
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def english_translation(info: dict) -> Optional[dict]:
    for translation in info.get("translations") or []:
        if translation.get("language") == ENGLISH and (translation.get("name") or "").strip():
            return translation
    return None

def muscle_label(muscle: dict) -> str:
    name = (muscle.get("name_en") or "").strip() or (muscle.get("name") or "").strip()
    return MUSCLE_RENAMES.get(name, name)

def is_bodyweight(equipment: dict) -> bool:
    return (equipment.get("name") or "").strip().lower().startswith("none")

def guess_difficulty(equipment_names: list) -> str:
    return "intermediate" if any(n.lower() in HARDER_EQUIPMENT for n in equipment_names) else "beginner"

def guess_role(secondary_muscle_count: int) -> str:
    # exercises that work multiple other muscles are treated as compound exercises
    return "core" if secondary_muscle_count > 0 else "accessory"

# writing to the database
def upsert_lookup(db, model, wger_id: int, name: str):
    """Finds a muscle/equipment row by wger_id, then by name (e.g. one of our demo rows)."""
    row = db.scalar(select(model).where(model.wger_id == wger_id))
    if row is None:
        row = db.scalar(select(model).where(model.name == name))
        if row is not None and row.wger_id is None:
            row.wger_id = wger_id
    if row is None:
        row = model(wger_id=wger_id, name=name[:100])
        db.add(row)
    db.flush()
    return row

def import_lookups(db) -> tuple:
    muscles, equipment = {}, {}
    for m in paginate(f"{BASE}/muscle/?limit={PAGE_SIZE}"):
        if m.get("id") is not None and muscle_label(m):
            muscles[m["id"]] = upsert_lookup(db, MuscleGroup, m["id"], muscle_label(m))
    for e in paginate(f"{BASE}/equipment/?limit={PAGE_SIZE}"):
        if e.get("id") is not None and (e.get("name") or "").strip() and not is_bodyweight(e):
            equipment[e["id"]] = upsert_lookup(db, Equipment, e["id"], e["name"].strip())
    db.commit()
    return muscles, equipment

def import_exercises(db, muscles: dict, equipment: dict, limit: int) -> dict:
    def muscle_for(m: dict):
        if m["id"] not in muscles:  # a muscle the /muscle/ list did not include
            muscles[m["id"]] = upsert_lookup(db, MuscleGroup, m["id"], muscle_label(m))
        return muscles[m["id"]]

    def equipment_for(e: dict):
        if e["id"] not in equipment:
            equipment[e["id"]] = upsert_lookup(db, Equipment, e["id"], e["name"].strip())
        return equipment[e["id"]]

    counts = {"created": 0, "updated": 0, "skipped": 0}
    url = f"{BASE}/exerciseinfo/?language={ENGLISH}&limit={PAGE_SIZE}"

    for info in paginate(url):
        if limit and counts["created"] + counts["updated"] >= limit:
            break

        wger_id = info.get("id")
        translation = english_translation(info)
        if wger_id is None or translation is None:
            counts["skipped"] += 1
            continue

        name = translation["name"].strip()[:200]
        license_info = info.get("license") or {}
        fields = dict(
            name=name,
            category=((info.get("category") or {}).get("name") or None),
            description=clean_text(translation.get("description")) or None,
            source="wger",
            license_name=(license_info.get("short_name") or license_info.get("full_name") or None),
            license_author=(translation.get("license_author") or info.get("license_author") or None),
        )
        if fields["license_name"]:
            fields["license_name"] = fields["license_name"][:100]
        if fields["license_author"]:
            fields["license_author"] = fields["license_author"][:255]

        exercise = db.scalar(select(Exercise).where(Exercise.wger_id == wger_id))
        if exercise is not None:
            for key, value in fields.items():
                setattr(exercise, key, value)
            counts["updated"] += 1
            continue

        # names must be unique in our catalog; skip wger exercises that repeat an existing name
        taken = db.scalar(select(Exercise.id).where(func.lower(Exercise.name) == name.lower()))
        if taken is not None:
            counts["skipped"] += 1
            continue

        primary = [m for m in (info.get("muscles") or []) if m.get("id") is not None]
        secondary = [m for m in (info.get("muscles_secondary") or []) if m.get("id") is not None]
        gear = [e for e in (info.get("equipment") or [])
                if e.get("id") is not None and (e.get("name") or "").strip() and not is_bodyweight(e)]

        links = {}
        for m in primary:
            links[muscle_for(m).id] = True
        for m in secondary:
            links.setdefault(muscle_for(m).id, False)

        gear_rows = {equipment_for(e).id: equipment_for(e) for e in gear}
        role = guess_role(len(secondary))

        exercise = Exercise(
            wger_id=wger_id,
            difficulty=guess_difficulty([row.name for row in gear_rows.values()]),
            default_role=role,
            default_minutes=CORE_MINUTES if role == "core" else ACCESSORY_MINUTES,
            **fields,
        )
        exercise.equipment = list(gear_rows.values())
        exercise.muscle_links = [
            ExerciseMuscle(muscle_group_id=muscle_id, is_primary=is_primary)
            for muscle_id, is_primary in links.items()
        ]
        db.add(exercise)
        db.flush()
        counts["created"] += 1

        if (counts["created"] + counts["updated"]) % 50 == 0:
            db.commit()
            print(f"  ...{counts['created'] + counts['updated']} exercises so far")

    db.commit()
    return counts

def main() -> None:
    parser = argparse.ArgumentParser(description="Import wger muscles, equipment and exercises.")
    parser.add_argument("--max", type=int, default=0, help="stop after this many exercises (0 = all)")
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            print("Importing muscles and equipment...")
            muscles, equipment = import_lookups(db)
            print(f"  {len(muscles)} muscles, {len(equipment)} equipment items")

            print("Importing exercises...")
            counts = import_exercises(db, muscles, equipment, args.max)
        except Exception:
            db.rollback()
            raise

    print(f"Done. created={counts['created']} updated={counts['updated']} skipped={counts['skipped']}")

if __name__ == "__main__":
    main()