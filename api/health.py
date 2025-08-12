from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """서버 상태 확인"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'service': 'Basic Pitch MIDI Converter',
            'version': '1.0.0'
        }
        
        self.wfile.write(json.dumps(response).encode())
