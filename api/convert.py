from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import tempfile
import os
import io
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import traceback
import cgi

# 설정
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """CORS preflight 처리"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """GET 요청 - API 정보"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_data = {
            'message': 'Basic Pitch MIDI Converter',
            'method': 'POST',
            'supported_formats': list(ALLOWED_EXTENSIONS),
            'max_file_size': '10MB'
        }
        
        self.wfile.write(json.dumps(response_data).encode())
    
    def do_POST(self):
        """POST 요청 - 변환 처리"""
        try:
            print("🎵 변환 요청 받음")
            
            # Content-Type 확인
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self._send_error(400, 'Content-Type must be multipart/form-data')
                return
            
            # 파일 파싱
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            if 'file' not in form:
                self._send_error(400, 'No file provided')
                return
            
            file_item = form['file']
            if not file_item.filename:
                self._send_error(400, 'No file selected')
                return
            
            print(f"📁 파일명: {file_item.filename}")
            
            if not allowed_file(file_item.filename):
                self._send_error(400, f'Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}')
                return
            
            # 파일 데이터 읽기
            file_data = file_item.file.read()
            file_size = len(file_data)
            print(f"📊 파일 크기: {file_size} bytes")
            
            if file_size > MAX_FILE_SIZE:
                self._send_error(400, 'File too large (max 10MB)')
                return
            
            if file_size == 0:
                self._send_error(400, 'Empty file')
                return
            
            # 임시 파일 생성
            file_extension = file_item.filename.rsplit('.', 1)[1].lower()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            print(f"💾 임시 파일 생성: {temp_file_path}")
            
            try:
                # Basic Pitch 실행
                print("🎼 Basic Pitch 변환 시작...")
                
                model_output, midi_data, note_events = predict(
                    temp_file_path,
                    model_path=ICASSP_2022_MODEL_PATH
                )
                
                print(f"✅ 변환 완료! {len(note_events)} 개 노트 감지")
                
                # MIDI 데이터를 바이트로 변환
                midi_buffer = io.BytesIO()
                midi_data.write(midi_buffer)
                midi_bytes = midi_buffer.getvalue()
                
                print(f"🎹 MIDI 파일 크기: {len(midi_bytes)} bytes")
                
                # MIDI 파일 응답
                self.send_response(200)
                self.send_header('Content-Type', 'audio/midi')
                self.send_header('Content-Disposition', 'attachment; filename=converted.mid')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(midi_bytes)))
                self.end_headers()
                
                self.wfile.write(midi_bytes)
                
            except Exception as conversion_error:
                print(f"❌ 변환 실패: {str(conversion_error)}")
                print(f"📋 상세 오류: {traceback.format_exc()}")
                
                self._send_error(500, f'Conversion failed: {str(conversion_error)}')
                
            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    print("🗑️ 임시 파일 삭제")
        
        except Exception as e:
            print(f"❌ 서버 오류: {str(e)}")
            print(f"📋 상세 오류: {traceback.format_exc()}")
            
            self._send_error(500, f'Server error: {str(e)}')
    
    def _send_error(self, status_code, message):
        """에러 응답 전송"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        error_data = {'error': message}
        self.wfile.write(json.dumps(error_data).encode())
