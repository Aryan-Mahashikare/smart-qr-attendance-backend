from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import time
import uuid
import io
import qrcode

app = Flask(__name__)
CORS(app)

# ======================
# In-memory state
# ======================
current_qr = {
    "token": None,
    "expires_at": 0,
    "duration": 0
}

attendance = set()

# ======================
# Helper
# ======================
def is_expired():
    return time.time() > current_qr["expires_at"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ======================
# Routes
# ======================

@app.route("/")
def root():
    return "Smart QR Attendance Backend Running"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ---------- TEACHER ----------

@app.route("/generate_qr", methods=["POST"])
def generate_qr():
    data = request.json
    duration = data.get("duration")

    if duration not in [30, 45, 60]:
        return jsonify({"error": "Invalid duration"}), 400

    token = str(uuid.uuid4())
    current_qr["token"] = token
    current_qr["duration"] = duration
    current_qr["expires_at"] = time.time() + duration
    attendance.clear()

    student_url = f"https://smart-qr-attendance-backend.onrender.com/student?token={token}"

    img = qrcode.make(student_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = send_file(buf, mimetype="image/png")
    response.headers["Cache-Control"] = "no-store"
    return response

@app.route("/attendance", methods=["GET"])
def get_attendance():
    return jsonify(sorted(attendance))

@app.route("/qr_status", methods=["GET"])
def qr_status():
    if not current_qr["token"]:
        return jsonify({"active": False})

    remaining = int(current_qr["expires_at"] - time.time())
    return jsonify({
        "active": not is_expired(),
        "remaining": max(0, remaining),
        "duration": current_qr["duration"]
    })

# ---------- STUDENT ----------

@app.route("/student")
def serve_student():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.json
    username = data.get("username")
    token = data.get("token")

    if not username or not token:
        return jsonify({"error": "Invalid data"}), 400

    if token != current_qr["token"]:
        return jsonify({"error": "Invalid QR"}), 403

    if is_expired():
        return jsonify({"error": "QR has expired"}), 403

    attendance.add(username.strip())

    return jsonify({
        "status": "marked",
        "cooldown": current_qr["duration"]
    })

# ---------- PWA FILES ----------

@app.route("/student/manifest.json")
def manifest():
    return send_from_directory(
        BASE_DIR,
        "manifest.json",
        mimetype="application/manifest+json"
    )

@app.route("/student/sw.js")
def service_worker():
    return send_from_directory(
        BASE_DIR,
        "sw.js",
        mimetype="application/javascript"
    )

# ======================
# Entry
# ======================
if __name__ == "__main__":
    app.run(debug=True)
