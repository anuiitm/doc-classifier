"""
api.py
------
REST API around the classification engine, so other LTF systems (LOS, SFDC,
the review portal) can call it over HTTP.

Run:
    python api.py
    # -> http://127.0.0.1:7000

Endpoints:
    GET  /health
    POST /classify        multipart/form-data with a 'file' field (a PDF)
    POST /classify-batch  multipart with multiple 'files'
    GET  /                serves static/index.html
    POST /review          accepts JSON to approve/decline
"""

import os
import uuid
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from engine.gemini_engine import classify_file_gemini as classify_file

app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)

MAX_MB = 25
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = os.path.join(os.path.dirname(__file__), "doc_classifier.db")

def _save_and_classify(file_storage, lang):
    orig_name = secure_filename(file_storage.filename or "upload.pdf")
    base, ext = os.path.splitext(orig_name)
    if not ext:
        ext = ".pdf"
    
    unique_name = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(save_path)
    
    try:
        # Call Gemini!
        result = classify_file(save_path)
        result["file"] = orig_name
        result["server_filename"] = unique_name
        
        # Gemini directly returns extracted_fields, no need to run the old regex extractors.
        if "raw_text" in result:
            del result["raw_text"]
            
        return result
    except Exception as e:
        return {"file": orig_name, "ok": False, "error": str(e), "decision": "ERROR"}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "doc-classifier", "version": "1.0.0"})


@app.route("/classify", methods=["POST"])
def classify_one():
    if "file" not in request.files:
        return jsonify({"error": "send a PDF in the 'file' field"}), 400
    lang = request.form.get("lang", "eng")
    result = _save_and_classify(request.files["file"], lang)
    return jsonify(result)


@app.route("/classify-batch", methods=["POST"])
def classify_many():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "send PDFs in the 'files' field"}), 400
    lang = request.form.get("lang", "eng")
    return jsonify([_save_and_classify(f, lang) for f in files])


@app.route("/review", methods=["POST"])
def review_document():
    data = request.json
    filename = data.get("filename")
    doc_type = data.get("doc_type")
    identifier = data.get("identifier")
    status = data.get("status") # APPROVED or DECLINED
    reason = data.get("reason", "")
    
    if not all([filename, doc_type, status]):
        return jsonify({"error": "Missing required fields"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert into document_reviews
        cursor.execute(
            "INSERT INTO document_reviews (filename, doc_type, identifier, status, reason) VALUES (?, ?, ?, ?, ?)",
            (filename, doc_type, identifier, status, reason)
        )
        
        # If APPROVED, insert into the specific table based on doc_type
        if status == "APPROVED":
            customer_id = "dummy_portal_user"
            doc_id = identifier if identifier else f"dummy_{uuid.uuid4().hex[:8]}"
            if doc_type == "AADHAAR":
                cursor.execute("INSERT OR IGNORE INTO id_documents (document_id, customer_id, document_type) VALUES (?, ?, ?)", (doc_id, customer_id, "AADHAAR"))
            elif doc_type == "PAN":
                cursor.execute("INSERT OR IGNORE INTO pan_cards (pan_no, customer_id) VALUES (?, ?)", (doc_id, customer_id))
            elif doc_type == "VOTER_ID":
                cursor.execute("INSERT OR IGNORE INTO id_documents (document_id, customer_id, document_type) VALUES (?, ?, ?)", (doc_id, customer_id, "VOTER"))
            elif doc_type == "DRIVING_LICENCE":
                cursor.execute("INSERT OR IGNORE INTO id_documents (document_id, customer_id, document_type) VALUES (?, ?, ?)", (doc_id, customer_id, "DL"))
            elif doc_type == "PASSPORT":
                cursor.execute("INSERT OR IGNORE INTO id_documents (document_id, customer_id, document_type) VALUES (?, ?, ?)", (doc_id, customer_id, "PASSPORT"))
            elif doc_type in ["BANK_STATEMENT", "PASSBOOK", "CHEQUE"]:
                cursor.execute("INSERT OR IGNORE INTO bank_accounts (account_no, customer_id) VALUES (?, ?)", (doc_id, customer_id))
                
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n  Document Classification Gemini API")
    print("  http://127.0.0.1:7002   (Portal UI)")
    print("  http://127.0.0.1:7002/classify   (API endpoint)\n")
    app.run(host="127.0.0.1", port=7002, debug=False)
