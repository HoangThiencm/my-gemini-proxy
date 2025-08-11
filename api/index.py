import os
import random
import base64
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

app = Flask(__name__)

API_KEYS_STRING = os.environ.get('GEMINI_API_KEYS', '')
API_KEYS = [key.strip() for key in API_KEYS_STRING.split(',') if key.strip()]

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'POST' and path == 'api/generate':
        return handle_generate()
    return jsonify({"status": "ok", "message": "Proxy server is running."}), 200

def handle_generate():
    if not API_KEYS:
        return jsonify({"error": "No API keys configured on the server."}), 500

    data = request.get_json()
    if not data or 'image_b64' not in data or 'prompt' not in data or 'model_id' not in data:
        return jsonify({"error": "Missing image_b64, prompt, or model_id in request."}), 400

    image_data = base64.b64decode(data['image_b64'])
    prompt = data['prompt']
    model_id = data['model_id']

    random.shuffle(API_KEYS)
    last_error = None

    for api_key in API_KEYS:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_id)
            image_part = {"mime_type": "image/png", "data": image_data}
            response = model.generate_content([prompt, image_part])
            processed_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            return jsonify({"result": processed_text})
        except (google_exceptions.PermissionDenied, google_exceptions.ResourceExhausted) as e:
            print(f"Key ...{api_key[-4:]} failed: {e}")
            last_error = str(e)
            continue
        except Exception as e:
            print(f"An unexpected error occurred with key ...{api_key[-4:]}: {e}")
            return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500

    return jsonify({"error": f"All API keys failed. Last error: {last_error}"}), 503
