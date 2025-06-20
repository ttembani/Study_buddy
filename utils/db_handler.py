import firebase_admin # type: ignore
from firebase_admin import credentials, firestore # type: ignore

# Only initialize once
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def save_qa_to_db(user_id, question, answer):
    doc_ref = db.collection("user_sessions").document(user_id).collection("qa").document()
    doc_ref.set({
        "question": question,
        "answer": answer
    })
