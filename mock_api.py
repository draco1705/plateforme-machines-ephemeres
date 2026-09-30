import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import uuid

reservations = []
workers = {}

class MockAPIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        if self.path == '/reservations':
            self._set_headers()
            self.wfile.write(json.dumps(reservations).encode('utf-8'))
        elif self.path == '/workers':
            self._set_headers()
            self.wfile.write(json.dumps(list(workers.values())).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            data = {}

        if self.path == '/login':
            self._set_headers()
            self.wfile.write(json.dumps({"token": "mock-jwt-token"}).encode('utf-8'))
            
        elif self.path == '/reservations':
            self._set_headers(201)
            new_res = {
                "id": str(uuid.uuid4()),
                "machine": data.get("machine", "kali"),
                "status": "RUNNING",
                "worker": "worker1",
                "time_remaining": data.get("duration", 3600)
            }
            reservations.append(new_res)
            self.wfile.write(json.dumps(new_res).encode('utf-8'))
            
        elif self.path == '/workers/register':
            self._set_headers(201)
            worker_id = data.get("id", str(uuid.uuid4()))
            workers[worker_id] = {
                "id": worker_id,
                "ip": data.get("ip"),
                "cpu": data.get("cpu"),
                "ram": data.get("ram"),
                "status": "AVAILABLE",
                "last_heartbeat": time.time()
            }
            self.wfile.write(json.dumps(workers[worker_id]).encode('utf-8'))
            
        elif self.path == '/workers/heartbeat':
            worker_id = data.get("id")
            if worker_id in workers:
                workers[worker_id]["last_heartbeat"] = time.time()
                workers[worker_id]["stats"] = data.get("stats")
                self._set_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Worker not found"}).encode('utf-8'))
                
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_DELETE(self):
        if self.path.startswith('/reservations/'):
            res_id = self.path.split('/')[-1]
            global reservations
            reservations = [r for r in reservations if r["id"] != res_id]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "deleted"}).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=MockAPIHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting mock API server on port {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
