"""GIS 点位质检本地入口。仅绑定本机，不作为互联网服务部署。"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from gis_qc.core import InputError, check_bytes
from gis_qc.report import build_report, export_csv

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0-local"
MAX_BYTES = 5 * 1024 * 1024
MAX_REQUEST = 8 * 1024 * 1024
MAX_ROWS = 10000
CATEGORIES = ["学校", "医疗", "交通", "文体", "公共服务"]
CRS_OPTIONS = ["未声明", "WGS84", "CGCS2000"]


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "PointQC/0.1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        # 仅记录请求状态，不把客户表格内容或完整 URL 写入日志。
        print(f"[HTTP] {self.command} {getattr(self, 'response_status', '')}", flush=True)

    def _allowed_request(self):
        port = self.server.server_port
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in allowed_hosts:
            self._json({"error": "请通过本机启动地址访问工具。"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in allowed_hosts}:
            self._json({"error": "此请求不是来自本机工具页面。"}, 403)
            return False
        return True

    def _send(self, content, mime, status=200, attachment=None):
        self.response_status = status
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _static(self, directory, relative):
        base = directory.resolve()
        target = (base / relative).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            self._json({"error": "未找到该文件。"}, 404)
            return
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if mime.startswith("text/") or target.suffix == ".js":
            mime += "; charset=utf-8"
        self._send(target.read_bytes(), mime)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._allowed_request():
            return
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path == "/api/meta":
            self._json({"token": self.server.token, "version": VERSION,
                        "limits": {"max_bytes": MAX_BYTES, "max_rows": MAX_ROWS},
                        "default_categories": CATEGORIES, "crs_options": CRS_OPTIONS})
        elif path == "/api/template":
            extension = parse_qs(parsed.query).get("format", ["csv"])[0]
            if extension not in {"csv", "xlsx"}:
                self._json({"error": "模板格式应为 CSV 或 XLSX。"}, 400)
                return
            target = ROOT / "samples" / f"template.{extension}"
            if not target.is_file():
                self._json({"error": "模板尚未生成，请运行样例生成脚本。"}, 404)
                return
            mime = "text/csv; charset=utf-8" if extension == "csv" else (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self._send(target.read_bytes(), mime, attachment=target.name)
        elif path == "/api/sample":
            params = parse_qs(parsed.query)
            kind = params.get("kind", ["normal"])[0]
            extension = params.get("format", ["csv"])[0]
            if kind not in {"normal", "issues"} or extension not in {"csv", "xlsx"}:
                self._json({"error": "请选择内置正常或异常 CSV / Excel 样例。"}, 400)
                return
            target = ROOT / "samples" / f"{kind}.{extension}"
            if not target.is_file():
                self._json({"error": "内置样例缺失，请按运行说明重新生成。"}, 404)
                return
            mime = "text/csv; charset=utf-8" if extension == "csv" else (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self._send(target.read_bytes(), mime, attachment=target.name)
        elif path in {"/", "/index.html"}:
            self._static(ROOT / "web", "index.html")
        elif path.startswith("/web/"):
            self._static(ROOT / "web", path[5:])
        elif path in {"/demo", "/demo/"}:
            self._static(ROOT / "docs", "index.html")
        elif path.startswith("/demo/"):
            self._static(ROOT / "docs", path[6:])
        elif path == "/README.md":
            self._static(ROOT, "README.md")
        elif path == "/favicon.ico":
            self._send(b"", "image/x-icon", 204)
        else:
            self._json({"error": "未找到该页面。"}, 404)

    def do_POST(self):
        if not self._allowed_request():
            return
        if urlsplit(self.path).path != "/api/check":
            self._json({"error": "未找到该操作。"}, 404)
            return
        if not secrets.compare_digest(self.headers.get("X-QC-Token", ""), self.server.token):
            self._json({"error": "页面会话已失效，请刷新后重试。"}, 403)
            return
        if self.headers.get_content_type() != "application/json":
            self._json({"error": "请求格式应为 JSON。"}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST:
                raise InputError("请求为空或过大，文件上限为 5 MiB。")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise InputError("文件传输不完整，请重新选择文件。")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise InputError("请求内容应为一个对象。")
            filename = payload.get("filename")
            encoded = payload.get("content_base64")
            crs = payload.get("crs", "未声明")
            is_demo = payload.get("is_demo", False)
            categories = payload.get("allowed_categories")
            if not isinstance(filename, str) or not filename or len(filename) > 240:
                raise InputError("文件名缺失或过长。")
            filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
            if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:
                raise InputError("首版仅支持 .csv 与 .xlsx 文件。")
            if not isinstance(encoded, str):
                raise InputError("未收到文件内容。")
            if crs not in CRS_OPTIONS or not isinstance(is_demo, bool):
                raise InputError("坐标系或样例标记格式不正确。")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise InputError("文件编码损坏，请重新选择文件。") from exc
            if len(data) > MAX_BYTES:
                raise InputError("文件超过 5 MiB，请按批次拆分。")
            result = check_bytes(data, filename, crs=crs,
                                 allowed_categories=categories, is_demo=is_demo)
            self._json({"result": result, "report_html": build_report(result),
                        "issues_csv": export_csv(result).decode("utf-8")})
        except (InputError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            # 隐藏输入内容与内部文件路径，异常类别供本机排查。
            print(f"[ERROR] {type(exc).__name__}", file=sys.stderr, flush=True)
            self._json({"error": "检查未完成。请使用固定模板重试，或记录问题反馈。"}, 500)


def main():
    parser = argparse.ArgumentParser(description="GIS 点位与属性数据质检（本地工具）")
    parser.add_argument("--port", type=int, default=8765, help="本机端口，默认 8765")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("端口须在 1024 至 65535 之间。")
    try:
        server = LocalServer(("127.0.0.1", args.port))
    except OSError as exc:
        print(f"无法启动端口 {args.port}。请关闭旧窗口，或指定其他端口。({exc.errno})")
        return 1
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"GIS point QC {VERSION}\nLocal: {url}\nPress Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.6, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
