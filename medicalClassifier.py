import requests
import re

class MedicalClassifier:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    # ============================================================
    # CORE API CALL
    # ============================================================
    def call_groq(self, messages, temperature=0):
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 10   # 👈 classifier needs very small output
                },
                timeout=20
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            else:
                print("Classifier API Error:", response.text)
                return None

        except Exception as e:
            print("Classifier Exception:", e)
            return None

    # ============================================================
    # 🔹 STEP 1: CHECK INPUT FORMAT (IMPORTANT FOR YOUR APP)
    # ============================================================
    def is_valid_user_format(self, text):
        """
        Check if user follows:
        name, age, sex, problem
        """
        pattern = r"name.*age.*sex.*problem"
        return bool(re.search(pattern, text.lower()))

    # ============================================================
    # 🔹 STEP 2: EMERGENCY DETECTION (NO API CALL → FAST)
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
    # 🔹 STEP 3: MEDICAL QUERY CLASSIFICATION (LLM)
    # ============================================================
    def is_medical_query(self, user_input):
        messages = [
            {
                "role": "system",
                "content": "Reply ONLY with YES or NO."
            },
            {
                "role": "user",
                "content": f"Is this related to health or body symptoms?\n\n{user_input}"
            }
        ]

        response = self.call_groq(messages)
        return response == "YES"

    # ============================================================
    # 🔹 FINAL ROUTER (THIS IS WHAT YOU WILL USE)
    # ============================================================
    def classify(self, user_input):
        """
        Returns:
        - emergency
        - incomplete
        - non_medical
        - valid
        """

        # 1. Emergency (highest priority)
        if self.detect_emergency(user_input):
            return "emergency"

        # 2. Format check (for first message)
        if not self.is_valid_user_format(user_input):
            return "incomplete"

        # 3. Medical check
        if not self.is_medical_query(user_input):
            return "non_medical"

        return "valid"