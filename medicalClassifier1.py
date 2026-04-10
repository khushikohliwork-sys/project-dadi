import requests
import re

class MedicalClassifier:
    def __init__(self, api_key, model, api_caller=None):
        """
        api_key: your Groq API key
        model: Groq model name
        api_caller: function to call Groq API, injected from app.py
        """
        self.api_key = api_key
        self.model = model
        self.api_caller = api_caller  # injected function

    # ============================================================
    # STEP 1: CHECK INPUT FORMAT (FAST, NO API CALL)
    # ============================================================
    def is_valid_user_format(self, text):
        """
        Check if user follows:
        name, age, sex, problem (simple regex)
        """
        pattern = r"name.*age.*sex.*problem"
        return bool(re.search(pattern, text.lower()))

    # ============================================================
    # STEP 2: EMERGENCY DETECTION (NO API CALL → FAST)
    # ============================================================
    def detect_emergency(self, text):
        emergency_keywords = [
            "chest pain", "difficulty breathing", "unconscious",
            "heavy bleeding", "stroke", "heart attack", "seizure",
            "not breathing", "choking", "poisoning", "overdose",
            "suicidal", "severe burn"
        ]
        text = text.lower()
        return any(word in text for word in emergency_keywords)

    # ============================================================
    # STEP 3: MEDICAL QUERY CLASSIFICATION (LLM)
    # ============================================================
    def is_medical_query(self, user_input):
        """
        Returns True if user_input is a medical/health query.
        Uses the injected api_caller function.
        """
        if not self.api_caller:
            # fallback if api_caller not provided
            return False

        messages = [
            {"role": "system", "content": "Reply ONLY with YES or NO."},
            {"role": "user", "content": f"Is this related to health or body symptoms?\n\n{user_input}"}
        ]

        try:
            result = self.api_caller(messages, temperature=0, max_tokens=10)
            response_text = result["choices"][0]["message"]["content"].strip()
            return response_text.upper() == "YES"
        except Exception as e:
            print("Medical query classification failed:", e)
            return False

    # ============================================================
    # FINAL CLASSIFICATION
    # ============================================================
    def classify(self, user_input):
        """
        Returns one of:
        - emergency
        - incomplete
        - non_medical
        - valid
        """
        if self.detect_emergency(user_input):
            return "emergency"

        if not self.is_valid_user_format(user_input):
            return "incomplete"

        if not self.is_medical_query(user_input):
            return "non_medical"

        return "valid"