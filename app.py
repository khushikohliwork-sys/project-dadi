from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import requests
import re
import os

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
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

classifier = MedicalClassifier(GROQ_API_KEY, GROQ_MODEL)

# ============================================================
# YOUR ORIGINAL PROMPT (UNCHANGED)
# ============================================================
DADI_SYSTEM_PROMPT = """
You are Dadi — an 89-year-old Indian grandmother with deep, practical knowledge of Ayurveda and ghar ke nuske.

You diagnose through observation, food habits, routine, and body signals — never modern medicine.

-------------------------
CORE RULES
-------------------------

NEVER:
• Give remedies before enough critical information is collected
• Suggest modern medicine (no tablets, no injections)
• Use complex Ayurveda jargon
• Write long paragraphs (max 2–3 lines per section)
• Assume critical info missing
• Give generic advice
• Ask irrelevant lifestyle questions before main info
• Sound like a doctor, influencer, or AI

ALWAYS:
• Ask 2–3 critical follow-up questions per round in bullet points
• Start follow-ups with a single “Dadi ko batao” intro
• Identify root cause before giving any remedy
• Link issue to digestion / heat / cold / imbalance
• Prefer kitchen-based remedies first
• Keep tone simple, experienced, slightly firm (Hinglish)
• Respond strictly in <response> XML format
• Continuously check for critical missing info each round
• Track follow-up rounds; after 2–3 rounds, give remedy, diet, habit, final advice
• Once remedy is given, do NOT ask any more follow-up questions

-------------------------
INPUT UNDERSTANDING
-------------------------

Extract:
• Name, Age, Sex
• Symptoms / problem
• Duration
• Severity / intensity
• Major food or lifestyle clues relevant to symptoms

Ask only critical missing info 2–3 at a time in bullet points.  
After 2–3 follow-up rounds, proceed to remedy, diet, habit, final advice.  
Minor optional info (urine color, mild headache, dryness) does NOT block remedy.

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

-------------------------
TONE & FLOW
-------------------------

1. Ask follow-ups in bullet points, max 2–3 questions per round.
2. Count rounds; after 2–3 rounds, give remedy, diet, habit, final advice even if minor info missing.
3. Only critical missing info must stop remedy; minor optional info can be skipped after 2–3 rounds.
4. Keep each section short (2–3 lines), practical, slightly firm, caring, Hinglish.
5. Once remedy is given, **do not ask any more follow-up questions**. Conversation can end, or user can report back later.
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
# PROFILE EXTRACTION (STRICT FORMAT)
# ============================================================
def extract_user_profile(text):
    text = text.lower()
    profile = {}

    # Extract name (look for 'my name is' or just 'i am' followed by name)
    name_match = re.search(r"(?:my name is|i am|name)\s*[:\-]?\s*([a-zA-Z]+)", text)
    if name_match:
        profile["name"] = name_match.group(1).capitalize()

    # Extract age
    age_match = re.search(r"(\d{1,3})\s*(years|yo|yr|years old)?", text)
    if age_match:
        profile["age"] = age_match.group(1)

    # Extract sex
    sex_match = re.search(r"(male|female|other|f|m)", text)
    if sex_match:
        profile["sex"] = sex_match.group(1).capitalize()

    # Extract problem / symptoms (everything after 'problem' or first verb phrase)
    problem_match = re.search(r"(?:problem is|issue is|having|suffering from)\s*(.*)", text)
    if problem_match:
        profile["problem"] = problem_match.group(1).strip()
    else:
        # fallback: take all text minus extracted fields
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
        return jsonify({"final": "Beta message nahi bheja, phir se try karo"}), 400

    # --- Profile extraction ---
    profile = session.get("profile")
    if not profile:
        profile = extract_user_profile(user_message)
        if not profile:
            return jsonify({
                "final": "Beta pehle proper format mein batao:\n\nMy name is ..., age is ..., sex is ..., and my problem is ..."
            })
        session["profile"] = profile
        session["user_info"] = {}  # to store follow-up answers
    else:
        # Append new symptom info to problem
        profile["problem"] += f", {user_message}"
        session["profile"] = profile

    # --- Auto-update session["user_info"] from user message ---
    # This is a simple keyword-based approach; can be improved with NLP if needed
    user_info = session.get("user_info", {})

    # Example checks: duration, severity, water intake, other symptoms
    # You can expand these rules as needed
    if "din" in user_message or "day" in user_message:
        user_info["duration"] = user_message
    if "tez" in user_message or "mild" in user_message or "body ache" in user_message:
        user_info["severity"] = user_message
    if "paani" in user_message or "liter" in user_message or "water" in user_message:
        user_info["water_intake"] = user_message
    if "throat" in user_message or "headache" in user_message:
        user_info["other_symptoms"] = user_message

    session["user_info"] = user_info

    # --- History tracking ---
    history = session.get("history", [])
    history.append({"role": "user", "content": user_message})
    session["history"] = history

    # --- Build messages for API ---
    messages = [{"role": "system", "content": DADI_SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"""
Name: {profile['name']}
Age: {profile['age']}
Sex: {profile['sex']}
Problem: {profile['problem']}
Additional info: {user_info}
"""
    })
    messages += history[-4:]  # last 4 messages

    # --- Call API ---
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 800
            },
            timeout=30
        )
        response.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    raw = response.json()["choices"][0]["message"]["content"]

    # --- Remove thinking before sending ---
    cleaned = remove_thinking(raw)
    history.append({"role": "assistant", "content": cleaned})
    session["history"] = history

    parsed = parse_xml_response(cleaned)
    return jsonify(parsed)
@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "reset"})

# ============================================================
if __name__ == "__main__":
    app.run(debug=True, port=5000)