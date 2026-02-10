// Chatbot logic
let chatHistory = [];
const CHAT_STORAGE_KEY = "chat_history_v1";
function toggleChat() {
    const chatWindow = document.getElementById("chatWindow");
    const isOpening = !chatWindow.classList.contains("active");

    chatWindow.classList.toggle("active");

    if (isOpening) {
        setTimeout(() => {
            document.getElementById("chatInput").focus();
        }, 300);
    }
}

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const userMessage = input.value.trim();

    if (!userMessage) return;

    addMessageToChat(userMessage, "user");
    input.value = "";

    chatHistory.push({
        text: userMessage,
        sender: "user",
        timestamp: new Date(),
    });
    persistChatHistory();

    // Bot responses disabled for now. Plug your local AI here later.
    scrollToBottom();
}

function addMessageToChat(text, sender) {
    const messagesContainer = document.getElementById("chatMessages");
    const messageDiv = document.createElement("div");

    messageDiv.className = `message ${sender}-message`;
    messageDiv.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-time">${getCurrentTime()}</div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

function scrollToBottom() {
    const chatBody = document.getElementById("chatBody");
    if (!chatBody) return;
    chatBody.scrollTop = chatBody.scrollHeight;
}

function getCurrentTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, "0")}:${now
        .getMinutes()
        .toString()
        .padStart(2, "0")}`;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function handleKeyPress(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function initializeChat() {
    const messagesContainer = document.getElementById("chatMessages");
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <p>Здравствуйте! Можете задать любой интересующий Вас вопрос по анализу и я постараюсь Вам помочь!</p>
        </div>
    `;
}

function addQuickReplies() {
    // Optional: add quick reply buttons to your UI.
}

function persistChatHistory() {
    // Store in sessionStorage to persist across page navigation,
    // but clear on full reload or browser close.
    sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatHistory));
}

function restoreChatHistory() {
    const navEntry = performance.getEntriesByType("navigation")[0];
    if (navEntry && navEntry.type === "reload") {
        sessionStorage.removeItem(CHAT_STORAGE_KEY);
        return;
    }

    const saved = sessionStorage.getItem(CHAT_STORAGE_KEY);
    if (!saved) return;

    try {
        const parsed = JSON.parse(saved);
        if (!Array.isArray(parsed)) return;
        chatHistory = parsed;
        parsed.forEach((msg) => {
            addMessageToChat(msg.text, msg.sender);
        });
    } catch (error) {
        console.error("Failed to restore chat history", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // IMPORTANT: Include chatbot.html markup, chatbot.css styles, and this JS on every page
    // where the chat should appear. This keeps the DOM structure consistent across pages.
    initializeChat();
    restoreChatHistory();
    addQuickReplies();
    scrollToBottom();

    const input = document.getElementById("chatInput");
    if (input) {
        input.addEventListener("focus", function () {
            this.scrollIntoView({ behavior: "smooth", block: "center" });
        });
    }

    document.addEventListener("click", (event) => {
        const chatWindow = document.getElementById("chatWindow");
        const chatBtn = document.querySelector(".chat-bot-btn");

        if (
            chatWindow.classList.contains("active") &&
            !chatWindow.contains(event.target) &&
            !chatBtn.contains(event.target)
        ) {
            toggleChat();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            const chatWindow = document.getElementById("chatWindow");
            if (chatWindow.classList.contains("active")) {
                toggleChat();
            }
        }
    });
});

window.toggleChat = toggleChat;
window.sendMessage = sendMessage;
window.handleKeyPress = handleKeyPress;
