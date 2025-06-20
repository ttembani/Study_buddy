from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file  # type: ignore
from utils.cohere_handler import generate_answer
from utils.db_handler import save_qa_to_db
from dotenv import load_dotenv  # type: ignore
import os
from functools import wraps
from PyPDF2 import PdfReader  # type: ignore
from fpdf import FPDF  
from utils.speech_handler import transcribe_audio
from utils.vision_handler import extract_text_from_image


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

# In-memory user store
users = {}

# Decorator for routes requiring login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash("Please log in first.", "info")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('home') if 'user_email' in session else url_for('login'))

@app.route('/home')
@login_required
def home():
    # Simple home page - you can style this in your home.html template
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
        # Image upload & text extraction
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
                image_file.save(file_path)

                extracted_text = extract_text_from_image(file_path)
                session['image_text'] = extracted_text
                flash("Image uploaded and text extracted!", "success")

        # Asking a question based on the image content
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

if __name__ == '__main__':
    app.run(debug=True)
