import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from services.data_loader import JSONToDBLoader

def resolve_json_path():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])

    analysis_dir = BASE_DIR / "analysis_results"
    if not analysis_dir.exists():
        return None

    candidates = sorted(
        analysis_dir.glob("*_analysis.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return candidates[0] if candidates else None

json_path = resolve_json_path()
if not json_path or not json_path.exists():
    print("No analysis JSON found. Provide a path as the first argument.")
    sys.exit(1)

loader = JSONToDBLoader()
result = loader.load_from_json(str(json_path))

print("Load result:")
print(f"Store rows: {result['store_inserted']}")
print(f"Analysis rows: {result['analysis_inserted']}")
print(f"Errors: {len(result['errors'])}")

if result["errors"]:
    for error in result["errors"]:
        print(f"- {error}")
