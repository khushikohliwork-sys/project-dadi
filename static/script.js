// ============================================================
// script.js — Dadi Chatbot UI (Optimized for XML backend)
// ============================================================

// Send message → calls Flask /chat route
async function sendMessage() {
    const userInput = document.getElementById("userInput").value.trim();
    if (!userInput) return;

    appendUserMessage(userInput);
    document.getElementById("userInput").value = "";

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userInput })
        });
        const data = await res.json();

        // Always render all XML sections
        appendDadiResponse(data);
        // updateJSONPanel(data); // optional: show raw JSON

    } catch (err) {
        console.error(err);
        showToast("Beta, kuch gadbad ho gayi, try again!");
    }
}

// ============================================================
// Append user message to chat
// ============================================================
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

// ============================================================
// Append Dadi response from parsed XML data
// ============================================================
function appendDadiResponse(data) {
    const chatContainer = document.getElementById('chatContainer');
    const time = getCurrentTime();

    let html = '';

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
                    <div class="dadi-label"> Dadi ko batao</div>
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

// ============================================================
// Loading indicator
// ============================================================
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

// ============================================================
// Helpers
// ============================================================
function escapeHtml(text) {
    return text.replace(/&/g, "&amp;")
               .replace(/</g, "&lt;")
               .replace(/>/g, "&gt;");
}

function nl2br(text) {
    return text.replace(/\n/g, "<br>");
}

function getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

// ============================================================
// Textarea auto-resize & Enter-to-send
// ============================================================
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
});