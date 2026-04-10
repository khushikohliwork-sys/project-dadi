// ============================================================
// Dadi Chatbot UI — fully integrated
// Works with /chat and /get_history without changing backend logic
// ============================================================

// ---------------- Send message ----------------
async function sendMessage() {
    const userInput = document.getElementById("userInput").value.trim();
    if (!userInput) return;

    appendUserMessage(userInput);
    document.getElementById("userInput").value = "";

    const loaderId = showLoadingIndicator();

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userInput })
        });
        const data = await res.json();

        removeLoadingIndicator();
        appendDadiResponse(data);

    } catch (err) {
        console.error(err);
        removeLoadingIndicator();
        showToast("Beta, kuch gadbad ho gayi, try again!");
    }
}

// ---------------- Append user message ----------------
function appendUserMessage(text) {
    const chatContainer = document.getElementById('chatContainer');
    const time = getCurrentTime();

    const div = document.createElement('div');
    div.className = 'message user-message';
    div.innerHTML = `
        <div class="message-bubble">
            <div>${escapeHtml(text)}</div>
            <div class="message-time">${time}</div>
        </div>`;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ---------------- Append Dadi response ----------------
function appendDadiResponse(data) {
    const chatContainer = document.getElementById('chatContainer');
    const time = getCurrentTime();
    let html = '';

    // Render all XML sections
    if (data.final) {
        html += `<div class="dadi-final">${nl2br(escapeHtml(data.final))}</div>`;
    }
    if (data.diagnosis) {
        html += `<div class="dadi-section">
                    <div class="dadi-label"> Kya ho raha hai</div>
                    <div class="dadi-text">${nl2br(escapeHtml(data.diagnosis))}</div>
                 </div>`;
    }
    if (data.cause) {
        html += `<div class="dadi-section">
                    <div class="dadi-label"> Kyun ho raha hai</div>
                    <div class="dadi-text">${nl2br(escapeHtml(data.cause))}</div>
                 </div>`;
    }
    if (data.remedy) {
        html += `<div class="dadi-section dadi-remedy">
                    <div class="dadi-label"> Ghar ka Nuska</div>
                    <div class="dadi-text">${nl2br(escapeHtml(data.remedy))}</div>
                 </div>`;
    }
    if (data.diet) {
        html += `<div class="dadi-section">
                    <div class="dadi-label">Khana-Peena</div>
                    <div class="dadi-text">${nl2br(escapeHtml(data.diet))}</div>
                 </div>`;
    }
    if (data.habit) {
        html += `<div class="dadi-section">
                    <div class="dadi-label"> Aadat Badlo</div>
                    <div class="dadi-text">${nl2br(escapeHtml(data.habit))}</div>
                 </div>`;
    }
    if (data.followup_questions) {
        html += `<div class="dadi-section dadi-followup">
                    <div class="dadi-text">${nl2br(escapeHtml(data.followup_questions))}</div>
                 </div>`;
    }

    const div = document.createElement('div');
    div.className = 'message assistant-message';
    div.innerHTML = `<div class="message-bubble">${html}
                     <div class="message-time">${time}</div></div>`;

    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ---------------- Loading indicator ----------------
function showLoadingIndicator() {
    const chatContainer = document.getElementById('chatContainer');
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.className = 'message assistant-message';
    div.id = id;
    div.innerHTML = `<div class="message-bubble"><span class="loading"></span> Dadi soch rahi hai...</div>`;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return id;
}
function removeLoadingIndicator() {
    const loaders = document.querySelectorAll('.message .loading');
    loaders.forEach(l => l.parentElement.parentElement.remove());
}

// ---------------- Helpers ----------------
function escapeHtml(text) {
    return text.replace(/&/g, "&amp;")
               .replace(/</g, "&lt;")
               .replace(/>/g, "&gt;");
}
function nl2br(text) { return text.replace(/\n/g, "<br>"); }
function getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

// ---------------- Textarea auto-resize & Enter-to-send ----------------
document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('userInput');
    if (!textarea) return;

    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    });
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // ---------------- Load history on page load ----------------
    loadChatHistory();
});

// ---------------- Load chat history ----------------
// ---------------- Load chat history ----------------
let historyLoaded = false;
async function loadChatHistory() {
    if (historyLoaded) return;
    historyLoaded = true;

    try {
        const res = await fetch("/get_history");
        const data = await res.json();

        const chatContainer = document.getElementById("chatContainer");
        chatContainer.innerHTML = "";

        // Welcome message
        const welcomeDiv = document.createElement("div");
        welcomeDiv.className = "welcome-message";
        welcomeDiv.innerHTML = `
            <div class="doctor-avatar"><i class="fas fa-user-md"></i></div>
            <div class="welcome-content">
                <p>Dadi — Ghar ke Nuskhe</p>
                <p>89 saal ki anubhavi dadi ke ghar ke nuskhe aur Ayurvedic ilaaj</p>
                <p class="disclaimer"><i class="fas fa-exclamation-triangle"></i> This is not a substitute for professional medical advice.</p>
            </div>`;
        chatContainer.appendChild(welcomeDiv);

        const seen = new Set();

        data.history.forEach(msg => {
            const key = msg.role + "|" + msg.content;
            if (seen.has(key)) return; // dedupe
            seen.add(key);

            if (msg.role === "user") {
                // Render user message exactly like live
                appendUserMessage(msg.content);
            } else {
                // Render assistant message using your existing XML parser & UI
                try {
                    const parsed = parse_xml_response(msg.content);
                    appendDadiResponse(parsed);
                } catch (e) {
                    console.error("Failed to parse assistant message:", e);
                    // fallback plain render if parse fails
                    const msgDiv = document.createElement("div");
                    msgDiv.className = "assistant-message";
                    msgDiv.innerHTML = `<div class="message-bubble">${msg.content.replace(/\n/g, "<br>")}</div>`;
                    chatContainer.appendChild(msgDiv);
                }
            }
        });

        chatContainer.scrollTop = chatContainer.scrollHeight;
    } catch (err) {
        console.error("Failed to load chat history:", err);
    }
}

// ---------------- Reset Conversation ----------------
async function resetConversation() {
    if (!confirm("Beta, kya aap chat end karke nayi shuruat karna chahte ho?")) return;

    try {
        const res = await fetch("/reset", { method: "POST" });
        const data = await res.json();

        const chatContainer = document.getElementById("chatContainer");
        chatContainer.innerHTML = `
            <div class="welcome-message">
                <div class="doctor-avatar"><i class="fas fa-user-md"></i></div>
                <div class="welcome-content">
                    <p>Dadi — Ghar ke Nuskhe</p>
                    <p>89 saal ki anubhavi dadi ke ghar ke nuskhe aur Ayurvedic ilaaj</p>
                    <p class="disclaimer"><i class="fas fa-exclamation-triangle"></i> This is not a substitute for professional medical advice.</p>
                </div>
            </div>`;
        document.getElementById("userInput").value = "";
        showToast("Chat ended! Nayi session shuru ho gayi.");

    } catch (err) {
        console.error("Reset failed:", err);
        showToast("Beta, chat reset nahi ho paya, try again!");
    }
}