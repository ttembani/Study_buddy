from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore
import cohere
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Initialize Firebase
cred = credentials.Certificate(r"C:\\Users\27631\\Documents\\Study_buddy-3\\firebase_config.json.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Cohere client
cohere_api_key = os.getenv('COHERE_API_KEY')
co = cohere.Client(cohere_api_key)

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(datetime.now().timestamp())
    return render_template('index.html')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form.get('user_text', '').strip()
    if not text:
        return redirect(url_for('index'))
    
    try:
        doc_ref = db.collection('study_materials').document()
        doc_ref.set({
            'type': 'text',
            'content': text,
            'timestamp': datetime.now().isoformat(),
            'session_id': session.get('session_id', '')
        })
        return redirect(url_for('chat'))
    except Exception as e:
        return str(e), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Basic implementation for image upload
    return "Image upload functionality not implemented yet", 501

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    # Basic implementation for audio upload
    return "Audio upload functionality not implemented yet", 501

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    start_time = time.time()
    question = request.form.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    try:
        docs = db.collection('study_materials').order_by('timestamp', direction='DESCENDING').limit(3).get()
        context = "\n".join([doc.to_dict().get('content', '') for doc in docs])
        
        response = co.generate(
            model='command',
            prompt=f"""You are an AI study assistant. Answer the question based on the provided context.
            
            Context: {context}
            
            Question: {question}
            
            Answer:""",
            max_tokens=500,
            temperature=0.7
        )
        
        answer = response.generations[0].text.strip()
        response_time = time.time() - start_time
        
        doc_ref = db.collection('conversations').document()
        doc_ref.set({
            'session_id': session.get('session_id', ''),
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'api_used': 'Cohere',
            'response_time': response_time
        })
        
        return jsonify({
            'answer': answer,
            'api_used': 'Cohere',
            'response_time': round(response_time, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    if 'session_id' not in session:
        return jsonify([])
    
    try:
        docs = db.collection('conversations')\
                .where('session_id', '==', session['session_id'])\
                .order_by('timestamp', direction='DESCENDING')\
                .limit(5)\
                .get()
        
        history = []
        for doc in docs:
            data = doc.to_dict()
            history.append({
                'question': data.get('question', ''),
                'answer': data.get('answer', ''),
                'timestamp': data.get('timestamp', ''),
                'api_used': data.get('api_used', '')
            })
        
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)