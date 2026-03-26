from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import requests
import re
import os
from threading import Lock

from medicalClassifier import MedicalClassifier

# ============================================================
# LOAD ENV
# ============================================================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

# ============================================================
# GROQ CONFIG
# ============================================================
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# 🔁 ROUND ROBIN SETUP
API_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
]

API_KEYS = [k for k in API_KEYS if k]

key_index = 0
key_lock = Lock()

def get_next_key():
    global key_index
    with key_lock:
        key = API_KEYS[key_index]
        key_index = (key_index + 1) % len(API_KEYS)
        print("Using API KEY:", key[:10])
    return key

# Keep classifier using first key (optional)
classifier = MedicalClassifier(API_KEYS[0], GROQ_MODEL)

# ============================================================
# PROMPT (UNCHANGED)
# ============================================================


def detect_intent(message):
    prompt = f"""
Classify the user message into ONE of these categories:
- greeting
- health_problem

Message: "{message}"

Answer ONLY one word.
"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {get_next_key()}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 5
            },
            timeout=10
        )

        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"].strip().lower()

        return result

    except:
        return "health_problem" 
DADI_SYSTEM_PROMPT = """
You are Dadi — an 89-year-old Indian grandmother with deep, practical knowledge of Ayurveda and ghar ke nuske.

You diagnose through observation, food habits, routine, and body signals — never modern medicine.

-------------------------
CRITICAL RULES
-------------------------
1. NEVER give medical advice — you're Dadi, not a doctor
2. Be conversational, natural — talk like a real grandmother
3. Use simple Hinglish — mix Hindi and English naturally
4. Be warm, caring, sometimes slightly firm
5. If someone asks non-health questions, politely redirect to health topics
6. Only give remedies AFTER understanding the problem fully
7. Keep responses concise and relevant

ALWAYS:
• Ask 2–3 critical follow-up questions per round in bullet points
• Identify root cause before giving any remedy
• Link issue to digestion / heat / cold / imbalance
• Prefer kitchen-based remedies first
• Keep tone simple, experienced, slightly firm (Hinglish)
• Respond strictly in <response> XML format
• Continuously check for critical missing info each round
• Track follow-up rounds; after 2–3 rounds, give remedy, diet, habit, final advice
• Once remedy is given, do NOT ask any more follow-up questions

RESPONSE GUIDELINES:
• If user asks about non-health topics: "Arre beta, main dadi hoon, bimariyon ka ilaaj jaanti hoon. Aapko koi takleef hai?"
• If information is incomplete: Ask specific questions about age, symptoms, food, routine
• If you have enough info: Give 1–2 simple kitchen remedies with timing and quantity
• Always end with warmth and care

-------------------------
INPUT UNDERSTANDING
-------------------------
Extract:
• Name, Age, Sex
• Symptoms / problem
• Duration
• Severity / intensity
• Major food or lifestyle clues relevant to symptoms

Ask **only critical missing info 2–3 at a time in bullet points.**
After 2–3 follow-up rounds, proceed to remedy, diet, habit, final advice.  
Minor optional info (urine color, mild headache, dryness) does NOT block remedy.

-------------------------
CRITICAL MISSING INFO BY SYMPTOM
-------------------------
- Respiratory / cold symptoms (khansi, zukam, cough, flu): always ask age, duration, fever/temperature, sore throat, headache, body ache.
- Fever / infection related: always ask temperature, duration, chills, associated symptoms.
- Digestive issues: always ask food habits, digestion, bowel movements, duration.
- Pain / injury / joint / muscle issues (knee, shoulder, back, muscle): 
  always ask intensity, duration, recent activity or exercise, affected area, rest/recovery, diet affecting strength (calcium/protein), warm/cold imbalance.
  Do NOT ask about digestion, bowel movements, or unrelated symptoms unless the user specifically mentions them.
- General wellness / other: ask age, duration, relevant habits, food, or discomforts..

-------------------------
RESPONSE FORMAT (MANDATORY XML)
-------------------------
<response>
<thinking>
• Symptoms observed:
• Likely pattern (heat/cold/dry/heavy):
• Food linkage:
• Lifestyle linkage:
• Missing information:
• Follow-up rounds done: [number] → proceed to remedy if ≥2-3
</thinking>

<diagnosis></diagnosis>
<cause></cause>
<remedy></remedy>
<diet></diet>
<habit></habit>
<followup_questions>
<!-- Fill only if followup_rounds < 3 AND critical info is missing -->
<!-- Leave empty if followup_rounds ≥ 3 OR all critical info collected -->
</followup_questions>
<final></final>
</response>

STYLE:
- Use "beta", "arre", "theek hai", "sunna" naturally
- Keep sentences short and simple
- Show genuine concern
- Share little wisdom from experience

IMPORTANT: Be specific and relevant. Don't give long lists or generic advice. Talk like a real grandmother would — caring, practical, to the point.
"""
# ============================================================
# REMOVE <thinking>
# ============================================================
def remove_thinking(text):
    return re.sub(r"<thinking>[\s\S]*?</thinking>", "", text, flags=re.IGNORECASE)

# ============================================================
# XML PARSER
# ============================================================
def parse_xml_response(raw_text):
    def extract(tag):
        match = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", raw_text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    return {
        "diagnosis": extract("diagnosis"),
        "cause": extract("cause"),
        "remedy": extract("remedy"),
        "diet": extract("diet"),
        "habit": extract("habit"),
        "followup_questions": extract("followup_questions"),
        "final": extract("final")
    }

# ============================================================
# PROFILE EXTRACTION
# ============================================================
def extract_user_profile(text):
    text = text.lower()
    profile = {}

    name_match = re.search(r"(?:my name is|i am|name)\s*[:\-]?\s*([a-zA-Z]+)", text)
    if name_match:
        profile["name"] = name_match.group(1).capitalize()

    age_match = re.search(r"(\d{1,3})\s*(years|yo|yr|years old)?", text)
    if age_match:
        profile["age"] = age_match.group(1)

    sex_match = re.search(r"(male|female|other|f|m)", text)
    if sex_match:
        profile["sex"] = sex_match.group(1).capitalize()

    problem_match = re.search(r"(?:problem is|issue is|having|suffering from)\s*(.*)", text)
    if problem_match:
        profile["problem"] = problem_match.group(1).strip()
    else:
        temp = text
        for v in profile.values():
            temp = temp.replace(v.lower(), "")
        profile["problem"] = temp.strip() or "unspecified"

    return profile

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    session.clear()
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"final": "Beta message nahi bheja"}), 400

    # ================= SESSION INIT =================
    profile = session.get("profile")
    user_info = session.get("user_info", {})
    history = session.get("history", [])
    followup_rounds = session.get("followup_rounds", 0)

    # ================= INTENT CHECK =================
    intent = detect_intent(user_message)

    # ---------------- Non-health message ----------------
    # Only trigger if either first message or long enough text
    if intent != "health_problem":
        if profile and len(user_message) < 10:
            # Short replies like 'haan', 'nahin', 'nothing' → treat as health follow-up
            intent = "health_problem"
        else:
            return jsonify({
                "diagnosis": "",
                "cause": "",
                "remedy": "",
                "diet": "",
                "habit": "",
                "followup_questions": "",
                "final": "Arre beta, main dadi hoon, bimariyon ka ilaaj jaanti hoon. Aapko koi takleef hai?"
            })

    # ---------------- First health message ----------------
    if not profile:
        profile = extract_user_profile(user_message)
        session["profile"] = profile
        session["user_info"] = user_info
        session["followup_rounds"] = followup_rounds
        history.append({"role": "user", "content": user_message})
        session["history"] = history

    # ---------------- Ongoing health conversation ----------------
    else:
        problem = profile.get("problem", "")
        profile["problem"] = problem + (", " if problem else "") + user_message
        session["profile"] = profile
        # Append new user message
        history.append({"role": "user", "content": user_message})
        history = history[-10:]  # keep last 10 messages
        session["history"] = history

    # ================= BUILD MESSAGES =================
    messages = [{"role": "system", "content": DADI_SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"""
Name: {profile.get('name', 'Unknown')}
Age: {profile.get('age', 'Unknown')}
Sex: {profile.get('sex', 'Unknown')}
Problem: {profile.get('problem', '')}
Additional info: {user_info}
Followup rounds done: {followup_rounds}
"""
    })
    messages += history[-4:]  # only last 4 messages to avoid token overflow

    # ================= API CALL =================
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {get_next_key()}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800
            },
            timeout=30
        )
        response.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    raw = response.json()["choices"][0]["message"]["content"]
    cleaned = remove_thinking(raw)

    # ================= PARSE RESPONSE =================
    parsed = parse_xml_response(cleaned)

    # ================= INCREMENT FOLLOW-UP ROUNDS =================
    if parsed.get("followup_questions"):
        followup_rounds += 1
    session["followup_rounds"] = followup_rounds

    # ================= SAVE HISTORY =================
    history.append({"role": "assistant", "content": cleaned})
    history = history[-10:]
    session["history"] = history

    return jsonify(parsed)

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "reset"})

# ============================================================
if __name__ == "__main__":
    app.run(debug=True, port=5000)