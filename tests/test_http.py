"""实际 HTTP 入口的集成验收，不向外部服务发送数据。"""
import base64
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from app import LocalServer

ROOT = Path(__file__).resolve().parents[1]


class HTTPFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(ProxyHandler({}))
        with cls.opener.open(cls.url + "/api/meta") as response:
            cls.meta = json.load(response)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)

    def request(self, path, data=None, headers=None):
        request = Request(self.url + path, data=data, headers=headers or {})
        try:
            with self.opener.open(request, timeout=10) as response:
                return response.status, response.read(), response.headers
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def payload(self, extension="csv"):
        return {"filename": "normal." + extension,
                "content_base64": base64.b64encode(
                    (ROOT / "samples" / ("normal." + extension)).read_bytes()).decode(),
                "crs": "WGS84", "is_demo": True}

    def post(self, payload, headers=None):
        return self.request("/api/check", json.dumps(payload).encode(),
                            headers or {"Content-Type": "application/json",
                                        "X-QC-Token": self.meta["token"]})

    def test_csv_and_excel_complete_flow(self):
        for extension in ["csv", "xlsx"]:
            with self.subTest(extension=extension):
                original = (ROOT / "samples" / ("normal." + extension)).read_bytes()
                status, raw, _ = self.post(self.payload(extension))
                self.assertEqual(status, 200, raw)
                result = json.loads(raw)
                self.assertEqual(result["result"]["summary"]["total_rows"], 12)
                self.assertEqual(result["result"]["summary"]["issue_count"], 0)
                self.assertIn("<html", result["report_html"].lower())
                self.assertTrue(result["issues_csv"].startswith("\ufeff"))
                self.assertEqual(original, (ROOT / "samples" / ("normal." + extension)).read_bytes())

    def test_errors_report_matches_golden_manifest(self):
        payload = self.payload()
        payload["filename"] = "issues.csv"
        payload["content_base64"] = base64.b64encode((ROOT / "samples/issues.csv").read_bytes()).decode()
        status, raw, _ = self.post(payload)
        self.assertEqual(status, 200, raw)
        result = json.loads(raw)["result"]
        expected = json.loads((ROOT / "samples/expected.json").read_text(encoding="utf-8"))["issues"]
        self.assertEqual(result["summary"]["issue_count"], expected["issue_count"])
        self.assertEqual(result["summary"]["affected_rows"], expected["affected_rows"])

    def test_token_required(self):
        status, _, _ = self.post(self.payload(), {"Content-Type": "application/json"})
        self.assertEqual(status, 403)

    def test_cross_origin_denied(self):
        status, _, _ = self.post(self.payload(), {
            "Content-Type": "application/json", "X-QC-Token": self.meta["token"],
            "Origin": "https://example.org"})
        self.assertEqual(status, 403)

    def test_unrecognized_host_denied(self):
        status, _, _ = self.request("/api/meta", headers={"Host": "example.org"})
        self.assertEqual(status, 403)

    def test_malformed_json_friendly_error(self):
        status, raw, _ = self.request("/api/check", b"{", {
            "Content-Type": "application/json", "X-QC-Token": self.meta["token"]})
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(raw))

    def test_bad_encoding_and_metadata_rejected(self):
        for key, value in [("content_base64", "!broken!"), ("crs", "unknown"),
                           ("is_demo", "true"), ("allowed_categories", [])]:
            with self.subTest(field=key):
                payload = self.payload()
                payload[key] = value
                status, _, _ = self.post(payload)
                self.assertEqual(status, 400)

    def test_web_and_builtin_downloads(self):
        for path in ["/", "/web/app.js", "/web/style.css", "/api/sample?kind=issues&format=xlsx",
                     "/api/template?format=csv", "/api/template?format=xlsx"]:
            with self.subTest(path=path):
                status, data, _ = self.request(path)
                self.assertEqual(status, 200)
                self.assertTrue(data)

    def test_path_traversal_rejected(self):
        status, _, _ = self.request("/web/%2e%2e/app.py")
        self.assertEqual(status, 404)

    def test_unknown_sample_rejected(self):
        status, _, _ = self.request("/api/sample?kind=private&format=csv")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
