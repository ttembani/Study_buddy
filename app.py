from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from datetime import datetime
import time
import os
from functools import wraps
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from fpdf import FPDF
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import cohere

# Load environment variables first
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

# Initialize services
def initialize_services():
    # Initialize Cohere
    co = None
    try:
        cohere_api_key = os.getenv('COHERE_API_KEY')
        if cohere_api_key:
            co = cohere.Client(cohere_api_key)
            print("Cohere client initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Cohere client: {str(e)}")

    # Initialize Firebase
    db = None
    try:
        private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n')
        if private_key:
            firebase_config = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                "private_key": private_key,
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
            }
            cred = credentials.Certificate(firebase_config)
            fb_app = firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Firebase initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Firebase: {str(e)}")
    
    return co, db

co, db = initialize_services()

# Import utilities after services are initialized
try:
    from rag_helper import ask_study_buddy, GEMINI_API_KEY
    from utils.cohere_handler import generate_answer
    from utils.db_handler import save_qa_to_db
    from utils.speech_handler import transcribe_audio
    from utils.vision_handler import extract_text_from_image
except ImportError as e:
    print(f"Import error: {str(e)}")
    # Provide fallbacks or raise if these are critical
    ask_study_buddy = lambda x: "Service unavailable"
    GEMINI_API_KEY = None
    generate_answer = lambda x: "Answer service unavailable"
    save_qa_to_db = lambda *args: None
    transcribe_audio = lambda x: "Transcription unavailable"
    extract_text_from_image = lambda x: "Text extraction unavailable"

# In-memory user store
users = {}

# Helper functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash("Please log in first.", "info")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_email' in session:
        return redirect(url_for('home'))
    if 'session_id' not in session:
        session['session_id'] = str(datetime.now().timestamp())
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Endpoint for health checks"""
    services_ok = {
        'cohere': co is not None,
        'firebase': db is not None,
        'gemini': GEMINI_API_KEY is not None
    }
    status = 200 if all(services_ok.values()) else 503
    return jsonify({
        'status': 'healthy' if status == 200 else 'degraded',
        'services': services_ok
    }), status

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_email' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        password = request.form.get('password', '')
        user = users.get(email)
        if user and user['password'] == password:
            session['user_email'] = email
            flash("Logged in successfully!", "success")
            return redirect(url_for('home'))
        flash("Invalid email or password.", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_email' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if email in users:
            flash("Email already registered.", "error")
        elif password != password2:
            flash("Passwords do not match.", "error")
        else:
            users[email] = {'password': password}
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('user_email', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/ask', methods=['POST'])
def ask():
    try:
        question = request.form['question']
        response = ask_study_buddy(question)
        return jsonify({'answer': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/test_key")
def test_key():
    if GEMINI_API_KEY:
        return f"Gemini API Key Loaded: {GEMINI_API_KEY[:4]}... (length: {len(GEMINI_API_KEY)})"
    return "Gemini API Key NOT loaded!"

@app.route('/study', methods=['GET', 'POST'])
@login_required
def study():
    answer = ""
    if request.method == 'POST':
        question = request.form['question']
        answer = generate_answer(question)
        save_qa_to_db(session['user_email'], question, answer)
    return render_template('study.html', answer=answer)

@app.route('/voice', methods=['GET', 'POST'])
@login_required
def voice():
    answer = ""
    if request.method == 'POST':
        audio_file = request.files.get('audio')
        if audio_file and audio_file.filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_file.filename)
            audio_file.save(file_path)
            transcribed_text = transcribe_audio(file_path)
            answer = generate_answer(transcribed_text)
            save_qa_to_db(session['user_email'], transcribed_text, answer)
    return render_template('voice.html', answer=answer)

@app.route('/image', methods=['GET', 'POST'])
@login_required
def image():
    extracted_text = session.get('image_text', '')
    answer = ""

    if request.method == 'POST':
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
                image_file.save(file_path)
                extracted_text = extract_text_from_image(file_path)
                session['image_text'] = extracted_text
                flash("Image uploaded and text extracted!", "success")
        elif 'question' in request.form:
            question = request.form['question']
            context = session.get('image_text', '')
            if context:
                prompt = f"{question}\n\nContext:\n{context}"
                answer = generate_answer(prompt)
                save_qa_to_db(session['user_email'], question, answer)
            else:
                flash("Please upload an image first.", "warning")

    return render_template('image.html', extracted_text=extracted_text, answer=answer)

@app.route('/pdf', methods=['GET', 'POST'])
@login_required
def pdf():
    extracted_text = ""
    answer = ""

    if request.method == 'POST':
        if 'pdf' in request.files:
            pdf_file = request.files['pdf']
            if pdf_file and pdf_file.filename.endswith('.pdf'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
                pdf_file.save(file_path)
                reader = PdfReader(file_path)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + "\n"
                session['pdf_context'] = extracted_text
                flash("PDF uploaded and content extracted!", "success")
            else:
                flash("Invalid file type. Please upload a PDF.", "error")
        elif 'question' in request.form:
            question = request.form['question']
            context = session.get('pdf_context', '')
            if context:
                answer = generate_answer(question + "\nContext:\n" + context)
                session['last_pdf_answer'] = answer
                save_qa_to_db(session['user_email'], question, answer)
            else:
                flash("Please upload a PDF first.", "warning")

    return render_template('pdf.html', extracted_text=session.get('pdf_context', ''), answer=answer)

@app.route('/download_pdf_answer')
@login_required
def download_pdf_answer():
    content = session.get('last_pdf_answer', '')
    if not content:
        flash("No answer to download.", "warning")
        return redirect(url_for('pdf'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in content.split('\n'):
        pdf.multi_cell(0, 10, line)

    output_path = os.path.join("static", "generated_answer.pdf")
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', email=session.get('user_email'))

@app.route('/upload_text', methods=['POST'])
def upload_text():
    if not db:
        return "Database not available", 500
        
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
        return "An error occurred", 500

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/ask_question', methods=['POST'])
def ask_question():
    if not co or not db:
        return jsonify({'error': 'AI service is currently unavailable'}), 503
        
    start_time = time.time()
    question = request.form.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    try:
        docs = db.collection('study_materials')\
                .order_by('timestamp', direction='DESCENDING')\
                .limit(3)\
                .get()
        context = "\n".join([doc.to_dict().get('content', '') for doc in docs])
        
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
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    if not db:
        return jsonify({'error': 'Database not available'}), 500
        
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
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
