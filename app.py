from flask import Flask, request, send_file, jsonify
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import tempfile
import os
import io
from werkzeug.utils import secure_filename
import traceback

app = Flask(__name__)

# 설정
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.after_request
def after_request(response):
    """CORS 헤더 추가"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

@app.route('/', methods=['GET'])
def home():
    """홈페이지"""
    return jsonify({
        'message': 'Basic Pitch MIDI Converter API',
        'endpoints': {
            'convert': '/api/convert'
        },
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size': '10MB'
    })

@app.route('/api/convert', methods=['GET', 'POST', 'OPTIONS'])
def convert():
    """변환 엔드포인트"""
    
    # OPTIONS 요청 처리
    if request.method == 'OPTIONS':
        return '', 200
    
    # GET 요청 - API 정보
    if request.method == 'GET':
        return jsonify({
            'message': 'Basic Pitch MIDI Converter',
            'method': 'POST',
            'supported_formats': list(ALLOWED_EXTENSIONS),
            'max_file_size': '10MB'
        })
    
    # POST 요청 - 변환 처리
    try:
        print("🎵 변환 요청 받음")
        
        # 파일 검증
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        print(f"📁 파일명: {file.filename}")
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}'}), 400
        
        # 파일 읽기 및 크기 확인
        file_content = file.read()
        file_size = len(file_content)
        print(f"📊 파일 크기: {file_size} bytes")
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': 'File too large (max 10MB)'}), 400
        
        if file_size == 0:
            return jsonify({'error': 'Empty file'}), 400
        
        # 임시 파일 생성
        file_extension = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
            temp_file.write(file_content)
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
            
            # MIDI 데이터를 메모리로
            midi_buffer = io.BytesIO()
            midi_data.write(midi_buffer)
            midi_buffer.seek(0)
            
            print(f"🎹 MIDI 파일 크기: {len(midi_buffer.getvalue())} bytes")
            
            return send_file(
                midi_buffer,
                mimetype='audio/midi',
                as_attachment=True,
                download_name='converted.mid'
            )
            
        except Exception as conversion_error:
            print(f"❌ 변환 실패: {str(conversion_error)}")
            print(f"📋 상세 오류: {traceback.format_exc()}")
            
            return jsonify({
                'error': 'Conversion failed',
                'details': str(conversion_error)
            }), 500
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print("🗑️ 임시 파일 삭제")
        
    except Exception as e:
        print(f"❌ 서버 오류: {str(e)}")
        print(f"📋 상세 오류: {traceback.format_exc()}")
        
        return jsonify({
            'error': 'Server error',
            'details': str(e)
        }), 500

# Vercel용 핸들러
def handler(environ, start_response):
    return app(environ, start_response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
