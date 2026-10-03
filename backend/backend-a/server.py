from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class BackendHandler(BaseHTTPRequestHandler):

    def send_response_data(self, response, backend):
        body = json.dumps(response).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", '"backend-A-v1"')
        self.send_header("X-Backend", backend)
        self.end_headers()

        return body

    def do_GET(self):

        if self.path == "/" or self.path == "/api/status":
            response = {
                "backend": "A",
                "status": "ok"
            }
        else:
            response = {
                "backend": "A",
                "status": "not_found"
            }

        body = self.send_response_data(response, "A")
        self.wfile.write(body)

    def do_HEAD(self):

        if self.path == "/" or self.path == "/api/status":
            response = {
                "backend": "A",
                "status": "ok"
            }
        else:
            response = {
                "backend": "A",
                "status": "not_found"
            }

        self.send_response_data(response, "A")


server = HTTPServer(("0.0.0.0", 3001), BackendHandler)

print("Backend A running on port 3001")

server.serve_forever()
