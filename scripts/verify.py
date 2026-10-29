"""记录本机自动化验收；浏览器验证单独记录，不混为自动化通过。"""
import contextlib
import csv
import io
import json
import platform
import sys
import time
import unittest
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gis_qc.core import check_bytes

def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
    text = capture.getvalue()
    print(text)
    rows = [["编号", "名称", "类别", "经度", "纬度"]]
    rows += [[f"{i:05d}", f"模拟点位{i}", "学校", "113.1", "23.1"] for i in range(10000)]
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    data = stream.getvalue().encode("utf-8-sig")
    started = time.perf_counter()
    checked = check_bytes(data, "模拟一万行.csv", crs="WGS84", is_demo=True)
    elapsed = time.perf_counter() - started
    benchmark_ok = checked["summary"]["total_rows"] == 10000 and checked["summary"]["issue_count"] == 0
    evidence = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "本机自动化检查；人工模拟数据；不是实际客户准确率",
        "environment": {"python": platform.python_version(), "os": platform.system(),
                        "openpyxl": version("openpyxl"), "defusedxml": version("defusedxml")},
        "tests": {"run": result.testsRun, "failures": len(result.failures),
                  "errors": len(result.errors), "skipped": len(result.skipped),
                  "passed": result.wasSuccessful()},
        "synthetic_10000_rows": {"passed": benchmark_ok, "rows": checked["summary"]["total_rows"],
                                 "issue_count": checked["summary"]["issue_count"],
                                 "core_seconds": round(elapsed, 4),
                                 "timing_scope": "仅解析与规则检查，单次本机测量，不含浏览器和报告"},
        "browser": "单独见 browser-verification.json",
        "publication": "测试脚本不判断线上发布状态；正式项目许可证见 LICENSE_STATUS.md"
    }
    target = ROOT / "verification"
    target.mkdir(exist_ok=True)
    (target / "test-log.txt").write_text(text, encoding="utf-8")
    (target / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if result.wasSuccessful() and benchmark_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
