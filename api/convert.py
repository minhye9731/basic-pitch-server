from http.server import BaseHTTPRequestHandler
import json
import tempfile
import os
import io
import traceback
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.formparser import parse_form_data
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

# 설정
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB (Vercel 제한 고려)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            print("🎵 변환 요청 받음")
            
            # Content-Type 확인
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error_response(400, 'Content-Type must be multipart/form-data')
                return
            
            # 파일 파싱
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': self.headers.get('Content-Length', '0'),
                'wsgi.input': self.rfile
            }
            
            form = parse_form_data(environ)[1]
            
            if 'file' not in form:
                self.send_error_response(400, 'No file provided')
                return
            
            file_item = form['file']
            if not hasattr(file_item, 'filename') or not file_item.filename:
                self.send_error_response(400, 'No file selected')
                return
            
            print(f"📁 파일명: {file_item.filename}")
            
            if not allowed_file(file_item.filename):
                self.send_error_response(400, f'Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}')
                return
            
            # 파일 데이터 읽기
            file_data = file_item.read()
            file_size = len(file_data)
            print(f"📊 파일 크기: {file_size} bytes")
            
            if file_size > MAX_FILE_SIZE:
                self.send_error_response(400, 'File too large (max 5MB)')
                return
            
            if file_size == 0:
                self.send_error_response(400, 'Empty file')
                return
            
            # 임시 파일 생성
            file_extension = secure_filename(file_item.filename).rsplit('.', 1)[1].lower()
            temp_file_path = f"/tmp/input_{os.getpid()}.{file_extension}"
            
            with open(temp_file_path, 'wb') as temp_file:
                temp_file.write(file_data)
            
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
                
                # 응답 헤더 설정
                self.send_response(200)
                self.send_header('Content-Type', 'audio/midi')
                self.send_header('Content-Disposition', 'attachment; filename="converted.mid"')
                self.send_header('Content-Length', str(len(midi_bytes)))
                self.end_headers()
                
                # MIDI 데이터 전송
                self.wfile.write(midi_bytes)
                
            except Exception as conversion_error:
                print(f"❌ 변환 실패: {str(conversion_error)}")
                print(f"📋 상세 오류: {traceback.format_exc()}")
                
                self.send_error_response(500, f'Conversion failed: {str(conversion_error)}')
                
            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    print("🗑️ 임시 파일 삭제")
        
        except Exception as e:
            print(f"❌ 서버 오류: {str(e)}")
            print(f"📋 상세 오류: {traceback.format_exc()}")
            
            self.send_error_response(500, f'Server error: {str(e)}')
    
    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'service': 'Basic Pitch MIDI Converter',
            'version': '1.0.0'
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def send_error_response(self, status_code, message):
        """에러 응답 전송"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error_response = {
            'error': message,
            'status_code': status_code
        }
        
        self.wfile.write(json.dumps(error_response).encode())
