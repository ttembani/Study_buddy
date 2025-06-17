from flask import Flask, render_template, request, redirect
import firebase_admin
from firebase_admin import credentials, firestore
import cohere
import requests
import os
import time

# Initialize Firebase
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Cohere
co = cohere.Client("ND85wjrOHGfyKsH4TiXB9aKQBhNzwUGSD3iecOft")

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    user_text = request.form['user_text']
    db.collection('documents').add({'text': user_text})
    return redirect('/chat')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    image = request.files['image']
    image_path = "temp.png"
    image.save(image_path)
    text = extract_text_from_image(image_path)
    db.collection('documents').add({'text': text})
    return redirect('/chat')

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio' not in request.files:
        return 'No audio file uploaded', 400
    
    audio_file = request.files['audio']
    audio_file.save('audio.mp3')  # Save for processing
    transcript = transcribe_audio('audio.mp3')  # Use your AssemblyAI code
    return f"Transcribed text: {transcript}"

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    answer = ""
    if request.method == 'POST':
        question = request.form['question']
        context = ""
        docs = db.collection('documents').stream()
        for doc in docs:
            context += doc.to_dict().get('text', '') + " "
        response = co.chat(message=question, documents=[{"title": "Study Notes", "text": context}])
        answer = response.text
    return render_template('chat.html', answer=answer)

# OCR.Space API (Free)
def extract_text_from_image(image_path):
    with open(image_path, 'rb') as f:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': f},
            data={
                'apikey': 'K86163064488957',  # Replace with your OCR.Space key if needed
                'language': 'eng',
                'isOverlayRequired': False
            }
        )
    result = response.json()
    if result['IsErroredOnProcessing']:
        return "Failed to extract text."
    return result['ParsedResults'][0]['ParsedText']

def transcribe_audio(file_path):
    with open(file_path, 'rb') as f:
        response = requests.post(
            'https://api.assemblyai.com/v2/upload',
            headers={'authorization': 'b0d0ce0301d4405ab147494e6ccbf0fe'},
            files={'file': f}
        )
    
    # Debug print
    print("Upload status code:", response.status_code)
    print("Upload response text:", response.text)
    
    if response.status_code != 200:
        raise Exception(f"Audio upload failed: {response.text}")
    
    try:
        upload_url = response.json()['upload_url']
    except Exception as e:
        raise Exception(f"Failed to parse upload response JSON: {e}")
    
    transcribe_req = requests.post(
        'https://api.assemblyai.com/v2/transcript',
        headers={'authorization': 'b0d0ce0301d4405ab147494e6ccbf0fe'},
        json={'audio_url': upload_url}
    )
    
    # Check transcription request success
    if transcribe_req.status_code != 200:
        raise Exception(f"Transcription request failed: {transcribe_req.text}")
    
    transcribe_id = transcribe_req.json()['id']
    
    while True:
        polling = requests.get(
            f'https://api.assemblyai.com/v2/transcript/{transcribe_id}',
            headers={'authorization': 'b0d0ce0301d4405ab147494e6ccbf0fe'}
        )
        result = polling.json()
        if result['status'] == 'completed':
            return result['text']
        elif result['status'] == 'error':
            return "Error transcribing"
        time.sleep(2)

if __name__ == '__main__':
    app.run(debug=True)
