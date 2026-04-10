from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import re
import os
import time

from medicalClassifier import MedicalClassifier
from openai import OpenAI

# ============================================================
# LOAD ENV
# ============================================================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

# ============================================================
# OPENAI CONFIG
# ============================================================
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def call_openai_api(messages, temperature=0.8, max_tokens=600, retries=3):
    """
    Call OpenAI GPT-5 model with retries
    messages: list of dicts with role/content (user/system)
    """
    for attempt in range(retries):
        try:
            response = openai_client.responses.create(
            model="gpt-5-mini",
            input=messages
        )
            return {"choices":[{"message":{"content": response.output_text}}]}
        except Exception as e:
            wait = 2 ** attempt
            print(f"OpenAI request failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise Exception("Max retries exceeded with OpenAI API 😅")

# ============================================================
# MEDICAL CLASSIFIER
# ============================================================
classifier = MedicalClassifier(
    api_caller=call_openai_api
)

# ============================================================
# DADI PROMPT (UNCHANGED)
# ============================================================
DADI_SYSTEM_PROMPT= """
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
• Ask 2–3 natural follow-up questions (NOT robotic, NOT repetitive)
• Avoid repetitive instructional phrases like "Dadi ko batao"
• Questions should feel like a real conversation, not instructions
• Identify root cause before giving any remedy
• Link issue to digestion / heat / cold / imbalance
• Prefer kitchen-based remedies first
• Keep tone simple, experienced, slightly firm (Hinglish)
• Respond strictly in <response> XML format
• Continuously check for critical missing info each round
• Track follow-up rounds; after 2–3 rounds, give remedy, diet, habit, final advice
• Once remedy is given, do NOT ask any more follow-up questions
• Avoid repeating same phrasing every time
• Vary language naturally like a human

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
# CLEAN RESPONSE
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

    name_match = re.search(r"^([a-zA-Z]+)", text)
    if name_match:
        profile["name"] = name_match.group(1).capitalize()

    age_match = re.search(r"(\d{1,3})\s*(years old|yrs old|yo|yr|years)\b", text)
    if age_match:
        profile["age"] = age_match.group(1)

    sex_match = re.search(r"(male|female|other|f|m)", text)
    if sex_match:
        profile["sex"] = sex_match.group(1).capitalize()

    profile["problem"] = text
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

    # ===== SESSION INIT =====
    profile = session.get("profile", {})
    history = session.get("history", [])
    followup_rounds = session.get("followup_rounds", 0)

    # ===== EXTRACT PROFILE =====
    new_data = extract_user_profile(user_message)
    for key in ["name", "age", "sex"]:
        if not profile.get(key) and new_data.get(key):
            profile[key] = new_data[key]

    if profile.get("problem"):
        profile["problem"] += " AND " + user_message
    else:
        profile["problem"] = user_message
    session["profile"] = profile

    # ===== SAVE USER MESSAGE =====
    history.append({"role": "user", "content": user_message})
    context_history = history[-4:]

    # ===== BUILD PROMPT =====
    messages = [
        {"role": "system", "content": DADI_SYSTEM_PROMPT},
        {"role": "system", "content": f"""
Name: {profile.get('name', 'Unknown')}
Age: {profile.get('age', 'Unknown')}
Sex: {profile.get('sex', 'Unknown')}
Conversation so far: {profile.get('problem', '')}
Followup rounds done: {followup_rounds}

IMPORTANT:
- Always reply as Dadi: warm, empathetic, human-like.
- Never reject or block user input.
- If symptoms appear, give remedies, diet, and habit suggestions.
- Avoid repeating the same advice multiple times.
- Ask follow-up questions naturally, only if needed.
"""}
    ] + context_history

    # ===== CALL OPENAI =====
    try:
        result = call_openai_api(messages)
        raw = result["choices"][0]["message"]["content"]
    except Exception:
        return jsonify({"final": "Beta thoda ruk jao... system busy hai, phir se try karo"})

    # ===== CLEAN AND PARSE =====
    cleaned = remove_thinking(raw).replace("Dadi ko batao", "")
    parsed = parse_xml_response(cleaned)

    # ===== FOLLOW-UP TRACK =====
    if parsed.get("followup_questions"):
        followup_rounds += 1
        session["followup_rounds"] = followup_rounds
        parsed["final"] = ""
    else:
        parsed["followup_questions"] = ""
        if not parsed.get("final"):
            parsed["final"] = "Theek hai beta, apna khayal rakho."

    # ===== SAVE AI RESPONSE =====
    history.append({"role": "assistant", "content": cleaned})
    session["history"] = history[-6:]

    return jsonify(parsed)

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "reset"})

# ============================================================
if __name__ == "__main__":
    app.run(debug=True, port=5000)