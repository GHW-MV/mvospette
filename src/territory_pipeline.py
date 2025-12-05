"""
Lightweight territory ingestion + inference pipeline.

Reads:
    - static/uszips.csv (ZIP master with lat/lng and metadata)
    - static/Zipcodes_Deal_Count_By_Rep.csv (rep ZIP activity with deal counts)

Outputs:
    - data/territory.db (SQLite with zip_master, rep_activity, territory_assignments tables)
    - data/territory_assignments.csv (flattened export for mapping/reporting)

The inference engine follows the Codex directive:
    * normalize ZIPs to 5-digit strings
    * attach active owners directly
    * infer prospective owners for unowned ZIPs using proximity + magnitude + dominance
"""
from __future__ import annotations

import argparse
import csv
import heapq
import logging
import math
import zlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ZipRecord:
    zip: str
    lat: float
    lng: float
    city: str
    state_id: str
    state_name: str
    county_name: str
    population: Optional[int]
    timezone: str


@dataclass
class RepActivity:
    zip: str
    state: str
    owner_name: str
    owner_email: str
    deal_count: int
    status: str  # "ACTIVE" or "INACTIVE"

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"


@dataclass
class TerritoryAssignment:
    zip: str
    lat: float
    lng: float
    city: str
    state_id: str
    state_name: str
    county_name: str
    owner_email: Optional[str]
    owner_name: Optional[str]
    owner_status: Optional[str]
    deal_count: int
    prospective_owner_email: Optional[str]
    prospective_owner_name: Optional[str]
    inference_reason: Optional[str]

def repColor(name: str) -> str:
    """Return a fast, deterministic hex color derived from the rep name."""
    normalized = str(name or "").strip().lower().encode("utf-8")
    hash_code = zlib.crc32(normalized) & 0xFFFFFF
    return f"#{hash_code:06x}"

def normalize_zip(value: str) -> Optional[str]:
    """Normalize arbitrary ZIP strings into 5-char numeric strings."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    return digits.zfill(5)[:5]


def parse_status(value: str) -> str:
    """Normalize status into ACTIVE/INACTIVE."""
    if value is None:
        return "INACTIVE"
    normalized = str(value).strip().lower()
    if normalized in {"1", "active", "true", "yes"}:
        return "ACTIVE"
    return "INACTIVE"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two lat/lng pairs in miles."""
    radius_miles = 3958.8
    to_rad = math.radians
    phi1 = to_rad(lat1)
    phi2 = to_rad(lat2)
    d_phi = to_rad(lat2 - lat1)
    d_lambda = to_rad(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        d_lambda / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_miles * c


def load_zip_master(path: Path) -> Dict[str, ZipRecord]:
    """Load and normalize the ZIP master dataset."""
    zip_index: Dict[str, ZipRecord] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames:
            reader.fieldnames = [(f or "").lstrip("\ufeff").strip() for f in reader.fieldnames]
        required = {
            "zip",
            "lat",
            "lng",
            "city",
            "state_id",
            "state_name",
            "county_name",
            "population",
            "timezone",
        }
        missing = required.difference(set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Missing required columns in ZIP master: {sorted(missing)}")
        for row in reader:
            zip_code = normalize_zip(row.get("zip", ""))
            if not zip_code:
                continue
            try:
                zip_index[zip_code] = ZipRecord(
                    zip=zip_code,
                    lat=float(row["lat"]),
                    lng=float(row["lng"]),
                    city=row.get("city", "").strip(),
                    state_id=row.get("state_id", "").strip(),
                    state_name=row.get("state_name", "").strip(),
                    county_name=row.get("county_name", "").strip(),
                    population=int(row["population"]) if row.get("population") else None,
                    timezone=row.get("timezone", "").strip(),
                )
            except (KeyError, ValueError):
                # Skip malformed rows but continue processing
                continue
    return zip_index


def load_rep_activity(
    path: Path, zip_master: Dict[str, ZipRecord]
) -> List[RepActivity]:
    """Load rep activity, normalize ZIPs, and aggregate by (zip, email)."""
    aggregates: Dict[Tuple[str, str], RepActivity] = {}
    skipped_missing_zip = 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames:
            reader.fieldnames = [(f or "").lstrip("\ufeff").strip() for f in reader.fieldnames]
        required = {
            "d.Property Zip",
            "d.Property State",
            "U.Full Name",
            "User Email",
            "Deal Count",
            "Deal Owner Status",
        }
        missing = required.difference(set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Missing required columns in rep activity: {sorted(missing)}")
        for row in reader:
            zip_code = normalize_zip(row.get("d.Property Zip"))
            if not zip_code or zip_code not in zip_master:
                skipped_missing_zip += 1
                continue
            state = row.get("d.Property State", "").strip()
            owner_name = row.get("U.Full Name", "").strip()
            owner_email = row.get("User Email", "").strip()
            try:
                deal_count = int(float(row.get("Deal Count", 0)))
            except ValueError:
                deal_count = 0
            status = parse_status(row.get("Deal Owner Status"))
            key = (zip_code, owner_email)
            existing = aggregates.get(key)
            if existing:
                existing.deal_count += deal_count
                if status == "ACTIVE":
                    existing.status = "ACTIVE"
                if owner_name:
                    existing.owner_name = owner_name
            else:
                aggregates[key] = RepActivity(
                    zip=zip_code,
                    state=state,
                    owner_name=owner_name,
                    owner_email=owner_email,
                    deal_count=deal_count,
                    status=status,
                )
    if skipped_missing_zip:
        logger.warning("Skipped %d rows with missing/unknown ZIPs.", skipped_missing_zip)
    return list(aggregates.values())


def select_active_owner(activity: Iterable[RepActivity]) -> Dict[str, RepActivity]:
    """Pick the strongest active owner per ZIP by deal_count, break ties by email."""
    active_by_zip: Dict[str, RepActivity] = {}
    for rec in activity:
        if not rec.is_active:
            continue
        current = active_by_zip.get(rec.zip)
        if current is None:
            active_by_zip[rec.zip] = rec
            continue
        if rec.deal_count > current.deal_count or (
            rec.deal_count == current.deal_count
            and rec.owner_email.lower() < current.owner_email.lower()
        ):
            active_by_zip[rec.zip] = rec
    return active_by_zip


def infer_prospective_owner(
    target: ZipRecord,
    active_points: List[TerritoryAssignment],
    radius_miles: float,
    max_neighbors: int,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Infer a prospective owner using magnitude + dominance scoring."""
    neighbors: List[Tuple[TerritoryAssignment, float]] = []
    for pt in active_points:
        distance = haversine_miles(target.lat, target.lng, pt.lat, pt.lng)
        if distance <= radius_miles:
            neighbors.append((pt, distance))

    if not neighbors:
        # widen search but cap to max_neighbors for performance
        expanded = [
            (pt, haversine_miles(target.lat, target.lng, pt.lat, pt.lng))
            for pt in active_points
        ]
        neighbors = heapq.nsmallest(max_neighbors, expanded, key=lambda item: item[1])
    else:
        neighbors = heapq.nsmallest(max_neighbors, neighbors, key=lambda item: item[1])

    if not neighbors:
        return None, None, None

    total_neighbors = len(neighbors)
    stats: Dict[str, Dict[str, float]] = {}
    for neighbor, distance in neighbors:
        dist_miles = max(distance, 0.1)  # protect against divide-by-zero
        rep = neighbor.owner_email or "unknown"
        record = stats.setdefault(
            rep,
            {
                "mag": 0.0,
                "count": 0.0,
                "name": neighbor.owner_name or "",
            },
        )
        record["mag"] += neighbor.deal_count / dist_miles
        record["count"] += 1.0

    best_rep = None
    best_score = -1.0
    best_reason = None
    for rep, stat in stats.items():
        dominance = stat["count"] / total_neighbors
        final_score = 0.5 * stat["mag"] + 0.35 * dominance
        if final_score > best_score:
            best_score = final_score
            best_rep = rep
            best_reason = (
                f"mag={stat['mag']:.3f}; dominance={dominance:.3f}; "
                f"neighbors={total_neighbors}; radius_miles={radius_miles}"
            )

    if best_rep is None:
        return None, None, None

    best_name = stats[best_rep]["name"]
    return best_rep, best_name, best_reason


def build_assignments(
    zip_master: Dict[str, ZipRecord],
    activity: List[RepActivity],
    radius_miles: float,
    max_neighbors: int,
) -> List[TerritoryAssignment]:
    """Create a full country-wide assignment list."""
    active_by_zip = select_active_owner(activity)

    active_points: List[TerritoryAssignment] = []
    for zip_code, owner in active_by_zip.items():
        zr = zip_master[zip_code]
        active_points.append(
            TerritoryAssignment(
                zip=zip_code,
                lat=zr.lat,
                lng=zr.lng,
                city=zr.city,
                state_id=zr.state_id,
                state_name=zr.state_name,
                county_name=zr.county_name,
                owner_email=owner.owner_email,
                owner_name=owner.owner_name,
                owner_status=owner.status,
                deal_count=owner.deal_count,
                prospective_owner_email=None,
                prospective_owner_name=None,
                inference_reason=None,
            )
        )

    assignments: List[TerritoryAssignment] = []
    for zip_code, zr in zip_master.items():
        active_owner = active_by_zip.get(zip_code)
        if active_owner:
            assignments.append(
                TerritoryAssignment(
                    zip=zip_code,
                    lat=zr.lat,
                    lng=zr.lng,
                    city=zr.city,
                    state_id=zr.state_id,
                    state_name=zr.state_name,
                    county_name=zr.county_name,
                    owner_email=active_owner.owner_email,
                    owner_name=active_owner.owner_name,
                    owner_status=active_owner.status,
                    deal_count=active_owner.deal_count,
                    prospective_owner_email=None,
                    prospective_owner_name=None,
                    inference_reason=None,
                )
            )
            continue

        prospective_email, prospective_name, reason = infer_prospective_owner(
            zr, active_points, radius_miles, max_neighbors
        )
        assignments.append(
            TerritoryAssignment(
                zip=zip_code,
                lat=zr.lat,
                lng=zr.lng,
                city=zr.city,
                state_id=zr.state_id,
                state_name=zr.state_name,
                county_name=zr.county_name,
                owner_email=None,
                owner_name=None,
                owner_status=None,
                deal_count=0,
                prospective_owner_email=prospective_email,
                prospective_owner_name=prospective_name,
                inference_reason=reason,
            )
        )
    return assignments


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if not present and clear existing data."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zip_master (
            zip TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            city TEXT,
            state_id TEXT,
            state_name TEXT,
            county_name TEXT,
            population INTEGER,
            timezone TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rep_activity (
            zip TEXT,
            state TEXT,
            owner_name TEXT,
            owner_email TEXT,
            deal_count INTEGER,
            status TEXT,
            FOREIGN KEY(zip) REFERENCES zip_master(zip)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS territory_assignments (
            zip TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            city TEXT,
            state_id TEXT,
            state_name TEXT,
            county_name TEXT,
            owner_email TEXT,
            owner_name TEXT,
            owner_status TEXT,
            deal_count INTEGER,
            prospective_owner_email TEXT,
            prospective_owner_name TEXT,
            inference_reason TEXT,
            FOREIGN KEY(zip) REFERENCES zip_master(zip)
        )
        """
    )
    # Clear tables for idempotent runs.
    conn.execute("DELETE FROM territory_assignments")
    conn.execute("DELETE FROM rep_activity")
    conn.execute("DELETE FROM zip_master")
    conn.commit()


def persist_zip_master(conn: sqlite3.Connection, zip_master: Dict[str, ZipRecord]) -> None:
    conn.executemany(
        """
        INSERT INTO zip_master (zip, lat, lng, city, state_id, state_name, county_name, population, timezone)
        VALUES (:zip, :lat, :lng, :city, :state_id, :state_name, :county_name, :population, :timezone)
        """,
        [zr.__dict__ for zr in zip_master.values()],
    )
    conn.commit()


def persist_rep_activity(conn: sqlite3.Connection, activity: List[RepActivity]) -> None:
    conn.executemany(
        """
        INSERT INTO rep_activity (zip, state, owner_name, owner_email, deal_count, status)
        VALUES (:zip, :state, :owner_name, :owner_email, :deal_count, :status)
        """,
        [ra.__dict__ for ra in activity],
    )
    conn.commit()


def persist_assignments(conn: sqlite3.Connection, assignments: List[TerritoryAssignment]) -> None:
    conn.executemany(
        """
        INSERT INTO territory_assignments (
            zip, lat, lng, city, state_id, state_name, county_name,
            owner_email, owner_name, owner_status, deal_count,
            prospective_owner_email, prospective_owner_name, inference_reason
        ) VALUES (
            :zip, :lat, :lng, :city, :state_id, :state_name, :county_name,
            :owner_email, :owner_name, :owner_status, :deal_count,
            :prospective_owner_email, :prospective_owner_name, :inference_reason
        )
        """,
        [ta.__dict__ for ta in assignments],
    )
    conn.commit()


def export_assignments_csv(assignments: List[TerritoryAssignment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "zip",
        "lat",
        "lng",
        "city",
        "state_id",
        "state_name",
        "county_name",
        "owner_email",
        "owner_name",
        "owner_status",
        "deal_count",
        "prospective_owner_email",
        "prospective_owner_name",
        "inference_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in assignments:
            writer.writerow(row.__dict__)


def export_assignments_parquet(assignments: List[TerritoryAssignment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([a.__dict__ for a in assignments])
    try:
        df.to_parquet(path, index=False)
    except ImportError as exc:
        logger.warning("Parquet export failed (missing dependency): %s", exc)


def run_pipeline(
    zip_master_path: Path,
    rep_activity_path: Path,
    db_path: Path,
    export_path: Path,
    radius_miles: float,
    max_neighbors: int,
) -> None:
    logger.info("Loading ZIP master...")
    zip_master = load_zip_master(zip_master_path)
    logger.info("Loaded %d ZIP records.", len(zip_master))

    logger.info("Loading rep activity...")
    activity = load_rep_activity(rep_activity_path, zip_master)
    logger.info("Loaded %d rep activity records after normalization.", len(activity))

    logger.info("Building assignments...")
    assignments = build_assignments(zip_master, activity, radius_miles, max_neighbors)
    owned = sum(1 for a in assignments if a.owner_email)
    logger.info(
        "Assignments ready. Active-owned ZIPs: %d; prospective: %d.",
        owned,
        len(assignments) - owned,
    )

    logger.info("Initializing database at %s ...", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    init_db(conn)
    persist_zip_master(conn, zip_master)
    persist_rep_activity(conn, activity)
    persist_assignments(conn, assignments)
    conn.close()
    logger.info("Database populated.")

    logger.info("Exporting assignments to %s ...", export_path)
    export_assignments_csv(assignments, export_path)
    parquet_path = export_path.with_suffix(".parquet")
    logger.info("Exporting assignments to %s ...", parquet_path)
    export_assignments_parquet(assignments, parquet_path)
    logger.info("Export complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Territory ingestion + inference pipeline")
    parser.add_argument(
        "--zip-master",
        type=Path,
        default=BASE_DIR / "static" / "uszips.csv",
        help="Path to ZIP master CSV.",
    )
    parser.add_argument(
        "--rep-activity",
        type=Path,
        default=BASE_DIR / "static" / "Zipcodes_Deal_Count_By_Rep.csv",
        help="Path to rep activity CSV.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=BASE_DIR / "data" / "territory.db",
        help="Path to SQLite DB output.",
    )
    parser.add_argument(
        "--export-path",
        type=Path,
        default=BASE_DIR / "data" / "territory_assignments.csv",
        help="Path to CSV export of assignments.",
    )
    parser.add_argument(
        "--radius-miles",
        type=float,
        default=25.0,
        help="Neighbor search radius in miles for inference.",
    )
    parser.add_argument(
        "--max-neighbors",
        type=int,
        default=15,
        help="Maximum neighbors to consider when widening search.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        zip_master_path=args.zip_master,
        rep_activity_path=args.rep_activity,
        db_path=args.db_path,
        export_path=args.export_path,
        radius_miles=args.radius_miles,
        max_neighbors=args.max_neighbors,
    )
