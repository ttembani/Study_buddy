from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import time
import sqlite3
import threading
from flask_cors import CORS
import os
from rag_helper import ask_study_buddy, get_api_metrics

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Database setup
def init_db():
    with sqlite3.connect('study_buddy.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS conversations
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    api_used TEXT NOT NULL,
                    response_time REAL NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS api_metrics
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    response_time REAL NOT NULL,
                    success INTEGER NOT NULL)''')

init_db()

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(datetime.now().timestamp())
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    start_time = time.time()
    question = request.form.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    try:
        answer, api_used = ask_study_buddy(question)
        response_time = time.time() - start_time
        
        with sqlite3.connect('study_buddy.db') as conn:
            conn.execute('''INSERT INTO conversations VALUES
                          (NULL, ?, ?, ?, ?, ?, ?)''',
                          (session['session_id'], datetime.now().isoformat(),
                           question, answer, api_used, response_time))
        
        return jsonify({
            'answer': answer,
            'api_used': api_used,
            'response_time': round(response_time, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    if 'session_id' not in session:
        return jsonify([])
    
    with sqlite3.connect('study_buddy.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT question, answer, timestamp, api_used 
                         FROM conversations 
                         WHERE session_id = ? 
                         ORDER BY timestamp DESC LIMIT 5''',
                         (session['session_id'],))
        history = [dict(zip(['question', 'answer', 'timestamp', 'api_used'], row)) 
                  for row in cursor.fetchall()]
    
    return jsonify(history)

@app.route('/metrics')
def get_metrics():
    return jsonify(get_api_metrics())

@app.route('/test_key')
def test_key():
    from rag_helper import GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
    return jsonify({
        'Gemini': bool(GEMINI_API_KEY),
        'OpenAI': bool(OPENAI_API_KEY),
        'Anthropic': bool(ANTHROPIC_API_KEY)
    })

def cleanup_old_metrics():
    while True:
        time.sleep(3600)
        with sqlite3.connect('study_buddy.db') as conn:
            conn.execute("DELETE FROM api_metrics WHERE timestamp < datetime('now', '-7 days')")

if __name__ == '__main__':
    # Render-specific configuration
    port = int(os.environ.get('PORT', 5000))
    threading.Thread(target=cleanup_old_metrics, daemon=True).start()
    app.run(host='0.0.0.0', port=port)
