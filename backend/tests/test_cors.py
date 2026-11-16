import asyncio
import unittest

from app.main import app


class CorsTests(unittest.TestCase):
    def test_unhandled_errors_include_cors_headers(self):
        @app.app.get("/test-unhandled-error")
        def unhandled_error():
            raise RuntimeError("test error")

        messages = []
        request_body_sent = False

        async def receive():
            nonlocal request_body_sent
            if not request_body_sent:
                request_body_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/test-unhandled-error",
            "raw_path": b"/test-unhandled-error",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"origin", b"http://localhost:5173")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        }

        with self.assertRaisesRegex(RuntimeError, "test error"):
            asyncio.run(app(scope, receive, send))

        response_start = next(
            message for message in messages if message["type"] == "http.response.start"
        )
        self.assertEqual(response_start["status"], 500)
        response_headers = dict(response_start["headers"])
        self.assertEqual(
            response_headers[b"access-control-allow-origin"].decode(),
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
