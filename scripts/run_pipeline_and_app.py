"""
Profile the territory pipeline and optionally launch the Streamlit app.

Examples:
    python scripts/run_pipeline_and_app.py
    python scripts/run_pipeline_and_app.py --no-streamlit --profile-output data/profile.stats
    python scripts/run_pipeline_and_app.py --zip-master other.csv --streamlit-port 8600
"""
from __future__ import annotations

import argparse
import cProfile
import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
# Ensure repo root is importable so `src` can be found when run from scripts/
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def run_profiled_pipeline(
    zip_master: Path,
    rep_activity: Path,
    db_path: Path,
    export_path: Path,
    radius_miles: float,
    max_neighbors: int,
    profile_output: Optional[Path],
    no_profile: bool,
) -> None:
    """Run the pipeline with optional cProfile capture."""
    from src import territory_pipeline as tp

    profiler = None if no_profile else cProfile.Profile()
    if profiler:
        profiler.enable()

    tp.run_pipeline(
        zip_master_path=zip_master,
        rep_activity_path=rep_activity,
        db_path=db_path,
        export_path=export_path,
        radius_miles=radius_miles,
        max_neighbors=max_neighbors,
    )

    if profiler:
        profiler.disable()
        if profile_output:
            profile_output.parent.mkdir(parents=True, exist_ok=True)
            profiler.dump_stats(profile_output)
            print(f"Wrote cProfile stats to {profile_output}")

        stream = io.StringIO()
        stats = (
            profiler
            and cProfile.Stats(profiler, stream=stream).sort_stats(cProfile.SortKey.CUMULATIVE)
        )
        if stats:
            stats.print_stats(30)  # top 30 by cumulative time
            print(stream.getvalue())


def launch_streamlit(streamlit_script: Path, port: int, headless: bool) -> int:
    """Start the Streamlit app as a child process."""
    env = os.environ.copy()
    if headless:
        env["STREAMLIT_HEADLESS"] = "true"

    cmd = [
        "streamlit",
        "run",
        str(streamlit_script),
        "--server.port",
        str(port),
    ]
    print(f"Launching Streamlit: {' '.join(cmd)}")
    return subprocess.call(cmd, env=env, cwd=BASE_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile the territory pipeline and optionally launch Streamlit."
    )
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
    parser.add_argument(
        "--profile-output",
        type=Path,
        default=BASE_DIR / "data" / "profile.stats",
        help="Where to write cProfile stats (ignored if --no-profile).",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Run without cProfile (skips stats collection).",
    )
    parser.add_argument(
        "--no-streamlit",
        action="store_true",
        help="Skip launching the Streamlit app after the pipeline finishes.",
    )
    parser.add_argument(
        "--streamlit-script",
        type=Path,
        default=BASE_DIR / "src" / "streamlit_app.py",
        help="Path to the Streamlit app to launch.",
    )
    parser.add_argument(
        "--streamlit-port",
        type=int,
        default=8501,
        help="Port for the Streamlit server.",
    )
    parser.add_argument(
        "--streamlit-headless",
        action="store_true",
        help="Force Streamlit to run headless (no browser launch).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_profiled_pipeline(
        zip_master=args.zip_master,
        rep_activity=args.rep_activity,
        db_path=args.db_path,
        export_path=args.export_path,
        radius_miles=args.radius_miles,
        max_neighbors=args.max_neighbors,
        profile_output=args.profile_output,
        no_profile=args.no_profile,
    )

    if not args.no_streamlit:
        launch_streamlit(
            streamlit_script=args.streamlit_script,
            port=args.streamlit_port,
            headless=args.streamlit_headless,
        )


if __name__ == "__main__":
    main()
