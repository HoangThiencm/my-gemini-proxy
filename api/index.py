# --- START OF FILE api/index.py (UPGRADED FOR EXAM ANALYZER) ---

import os
import random
import base64
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

app = Flask(__name__)

# Đọc biến môi trường cho API keys
API_KEYS_STRING = os.environ.get('GEMINI_API_KEYS', '')
API_KEYS = [key.strip() for key in API_KEYS_STRING.split(',') if key.strip()]

# Đọc biến môi trường cho Modules
MODULES_STRING = os.environ.get('GEMINI_MODULES', 'Gemini 1.5 Flash,gemini-1.5-flash')
AVAILABLE_MODULES = []
for item in MODULES_STRING.split(';'):
    parts = item.strip().split(',')
    if len(parts) == 2:
        AVAILABLE_MODULES.append({'name': parts[0].strip(), 'id': parts[1].strip()})

def get_available_key():
    """Lấy một key ngẫu nhiên từ danh sách."""
    if not API_KEYS:
        return None
    return random.choice(API_KEYS)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    """Bắt tất cả các request và điều hướng đến đúng handler."""
    if request.method == 'POST':
        # Endpoint mới để phân tích toàn bộ đề thi (nhận PDF)
        if path == 'api/locate_questions':
            return handle_task_with_file_upload()
        # Endpoint mới để phân tích từng câu hỏi (nhận ảnh)
        elif path == 'api/analyze_question':
            return handle_task_with_image_upload()
            
    # Endpoint để lấy danh sách model
    elif request.method == 'GET' and path == 'api/modules':
        return jsonify(AVAILABLE_MODULES)
        
    return jsonify({"status": "ok", "message": "Exam Analyzer Proxy is running."}), 200

def handle_task_with_file_upload():
    """Xử lý các tác vụ yêu cầu gửi cả file (PDF) và prompt."""
    data = request.get_json()
    if not data or 'prompt' not in data or 'model_id' not in data or 'file_b64' not in data:
        return jsonify({"error": "Yêu cầu thiếu prompt, model_id, hoặc file_b64."}), 400

    prompt = data['prompt']
    model_id = data['model_id']
    file_data = base64.b64decode(data['file_b64'])
    
    # Giả định mime_type là application/pdf cho tác vụ này
    file_part = {"mime_type": "application/pdf", "data": file_data}
    
    return run_generation_with_retry([prompt, file_part], model_id)

def handle_task_with_image_upload():
    """Xử lý các tác vụ yêu cầu gửi ảnh và prompt."""
    data = request.get_json()
    if not data or 'prompt' not in data or 'model_id' not in data or 'image_b64' not in data:
        return jsonify({"error": "Yêu cầu thiếu prompt, model_id, hoặc image_b64."}), 400

    prompt = data['prompt']
    model_id = data['model_id']
    image_data = base64.b64decode(data['image_b64'])
    
    image_part = {"mime_type": "image/png", "data": image_data}
    
    return run_generation_with_retry([prompt, image_part], model_id)

def run_generation_with_retry(content_parts, model_id):
    """
    Hàm chung để chạy generate_content và tự động thử lại với key khác nếu thất bại.
    """
    if not API_KEYS:
        return jsonify({"error": "Không có API key nào được cấu hình trên server."}), 500
        
    shuffled_keys = random.sample(API_KEYS, len(API_KEYS))
    last_error = None

    for api_key in shuffled_keys:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_id)
            
            # Yêu cầu trả về JSON
            generation_config = {"response_mime_type": "application/json"}

            response = model.generate_content(content_parts, generation_config=generation_config)
            
            # Trả về kết quả JSON trực tiếp
            return jsonify(response.parts[0].json)

        except (google_exceptions.PermissionDenied, google_exceptions.ResourceExhausted) as e:
            print(f"Key ...{api_key[-4:]} failed: {e}")
            last_error = str(e)
            continue # Thử key tiếp theo
        except Exception as e:
            print(f"An unexpected error occurred with key ...{api_key[-4:]}: {e}")
            return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500

    # Nếu đã thử hết các key mà vẫn lỗi
    return jsonify({"error": f"Tất cả API keys đều thất bại. Lỗi cuối cùng: {last_error}"}), 503
