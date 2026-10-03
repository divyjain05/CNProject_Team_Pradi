from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class BackendHandler(BaseHTTPRequestHandler):

    def send_response_data(self, response, backend):
        body = json.dumps(response).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", '"backend-B-v1"')
        self.send_header("X-Backend", backend)
        self.end_headers()

        return body

    def do_GET(self):

        if self.path == "/" or self.path == "/api/status":
            response = {
                "backend": "B",
                "status": "ok"
            }
        else:
            response = {
                "backend": "B",
                "status": "not_found"
            }

        body = self.send_response_data(response, "B")
        self.wfile.write(body)

    def do_HEAD(self):

        if self.path == "/" or self.path == "/api/status":
            response = {
                "backend": "B",
                "status": "ok"
            }
        else:
            response = {
                "backend": "B",
                "status": "not_found"
            }

        self.send_response_data(response, "B")


server = HTTPServer(("0.0.0.0", 3002), BackendHandler)

print("Backend B running on port 3002")

server.serve_forever()
