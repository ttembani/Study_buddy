from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import cohere
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Initialize Firebase
try:
    # With this:
firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
}
cred = credentials.Certificate(firebase_config)
  # Simplified path
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Firebase initialization failed: {str(e)}")
    raise

# Initialize Cohere client
try:
    cohere_api_key = os.getenv('COHERE_API_KEY')
    if not cohere_api_key:
        raise ValueError("COHERE_API_KEY not found in environment variables")
    co = cohere.Client(cohere_api_key)
except Exception as e:
    print(f"Cohere initialization failed: {str(e)}")
    raise

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
        app.logger.error(f"Upload text error: {str(e)}")
        return "An error occurred", 500

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
        # Get context from Firestore
        docs = db.collection('study_materials')\
                .order_by('timestamp', direction='DESCENDING')\
                .limit(3)\
                .get()
        context = "\n".join([doc.to_dict().get('content', '') for doc in docs])
        
        # Generate answer using Cohere
        response = co.generate(
            model='command',
            prompt=f"""You are an AI study assistant. Answer the question based on the context.
            
            Context: {context}
            
            Question: {question}
            
            Answer:""",
            max_tokens=500,
            temperature=0.7
        )
        answer = response.generations[0].text.strip()
        
        # Store conversation
        doc_ref = db.collection('conversations').document()
        doc_ref.set({
            'session_id': session.get('session_id', ''),
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'api_used': 'Cohere',
            'response_time': time.time() - start_time
        })
        
        return jsonify({
            'answer': answer,
            'api_used': 'Cohere',
            'response_time': round(time.time() - start_time, 2)
        })
    except Exception as e:
        app.logger.error(f"Ask question error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    if 'session_id' not in session:
        return jsonify([])
    
    try:
        docs = db.collection('conversations')\
                .where(filter=FieldFilter('session_id', '==', session['session_id']))\
                .order_by('timestamp', direction='DESCENDING')\
                .limit(5)\
                .get()
        
        history = [{
            'question': doc.to_dict().get('question', ''),
            'answer': doc.to_dict().get('answer', ''),
            'timestamp': doc.to_dict().get('timestamp', ''),
            'api_used': doc.to_dict().get('api_used', '')
        } for doc in docs]
        
        return jsonify(history)
    except Exception as e:
        app.logger.error(f"Get history error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)  # Debug=False for production
