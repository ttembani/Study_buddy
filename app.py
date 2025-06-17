from flask import Flask, render_template, request, jsonify
from rag_helper import ask_study_buddy

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    question = request.form['question']
    response = ask_study_buddy(question)
    return jsonify({'answer': response})

@app.route("/test_key")
def test_key():
    from rag_helper import GEMINI_API_KEY  # or however you import it
    if GEMINI_API_KEY:
        return f"Gemini API Key Loaded: {GEMINI_API_KEY[:4]}... (length: {len(GEMINI_API_KEY)})"
    else:
        return "Gemini API Key NOT loaded!"


if __name__ == '__main__':
    app.run(debug=True)
