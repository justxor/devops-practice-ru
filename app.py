from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            body, status = {'status': 'ok'}, 200
        elif self.path == '/':
            body, status = {'service': 'devops-lab', 'version': os.getenv('APP_VERSION', 'local')}, 200
        else:
            body, status = {'error': 'not found'}, 404
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
