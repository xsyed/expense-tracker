from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AdvisorDeploymentConfigTests(SimpleTestCase):
    def test_compose_runs_single_advisor_worker_with_web_dependency(self) -> None:
        compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

        self.assertIn("advisor-worker:", compose)
        self.assertIn("container_name: expense-tracker-advisor-worker", compose)
        self.assertIn('command: ["python", "manage.py", "process_advisor_runs", "--poll-interval", "2"]', compose)
        self.assertIn("condition: service_healthy", compose)
        self.assertIn('test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]', compose)

    def test_nginx_disables_buffering_for_advisor_sse(self) -> None:
        nginx_config = (PROJECT_ROOT / "deploy/nginx/scorptech.ca").read_text(encoding="utf-8")

        self.assertIn("location ~ ^/expense-tracker/api/advisor/runs/[0-9]+/events/$", nginx_config)
        self.assertIn("proxy_buffering off;", nginx_config)
        self.assertIn("proxy_read_timeout 1h;", nginx_config)
        self.assertIn("add_header X-Accel-Buffering no always;", nginx_config)
        self.assertIn("proxy_pass http://127.0.0.1:8000;", nginx_config)

    def test_advisor_sse_url_uses_script_prefix(self) -> None:
        advisor_js = (PROJECT_ROOT / "static/js/advisor_pill.js").read_text(encoding="utf-8")

        self.assertIn("new window.EventSource(SCRIPT_PREFIX + `/api/advisor/runs/${run.id}/events/`", advisor_js)
