"""仅从仓库内人工模拟样例生成公开展示材料。"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gis_qc.core import check_bytes
from gis_qc.report import build_report, export_csv

def main():
    destination = ROOT / "docs"
    destination.mkdir(exist_ok=True)
    summary = {}
    for kind, report_name in [("normal", "sample-normal-report.html"), ("issues", "sample-report.html")]:
        source = ROOT / "samples" / f"{kind}.csv"
        result = check_bytes(source.read_bytes(), source.name, crs="WGS84", is_demo=True)
        (destination / report_name).write_text(build_report(result), encoding="utf-8")
        (destination / f"sample-{kind}-findings.csv").write_bytes(export_csv(result))
        shutil.copyfile(source, destination / f"sample-{kind}.csv")
        summary[kind] = {"summary": result["summary"], "sha256": result["sha256"]}
    (destination / "sample-results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
