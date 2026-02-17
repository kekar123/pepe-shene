// Chatbot logic
let chatHistory = [];
const CHAT_STORAGE_KEY = "chat_history_v1";
const TYPING_INDICATOR_ID = "typingIndicator";
let isAwaitingResponse = false;

function toggleChat() {
    const chatWindow = document.getElementById("chatWindow");
    const isOpening = !chatWindow.classList.contains("active");

    chatWindow.classList.toggle("active");

    if (isOpening) {
        setTimeout(() => {
            document.getElementById("chatInput").focus();
            scrollToBottom();
        }, 300);
    }
}

async function sendMessage() {
    if (isAwaitingResponse) return;

    const input = document.getElementById("chatInput");
    const sendButton = document.querySelector(".send-btn");
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

    isAwaitingResponse = true;
    setInputState(true, input, sendButton);
    showTypingIndicator();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: userMessage,
                history: chatHistory,
            }),
        });

        const data = await response.json();
        const botText =
            (data && data.answer) ||
            "В базе данных нет информации для ответа на этот вопрос.";

        addMessageToChat(botText, "bot");
        chatHistory.push({
            text: botText,
            sender: "bot",
            timestamp: new Date(),
        });
        persistChatHistory();
    } catch (error) {
        const failText = "Ошибка соединения с сервером чата.";
        addMessageToChat(failText, "bot");
        chatHistory.push({
            text: failText,
            sender: "bot",
            timestamp: new Date(),
        });
        persistChatHistory();
    } finally {
        hideTypingIndicator();
        isAwaitingResponse = false;
        setInputState(false, input, sendButton);
        scrollToBottom();
    }
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
    const chatBody =
        document.getElementById("chatBody") ||
        document.querySelector(".chat-body");
    if (!chatBody) return;

    requestAnimationFrame(() => {
        chatBody.scrollTop = chatBody.scrollHeight;
    });
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) return;
    if (document.getElementById(TYPING_INDICATOR_ID)) return;

    const indicator = document.createElement("div");
    indicator.id = TYPING_INDICATOR_ID;
    indicator.className = "message bot-message typing-indicator";
    indicator.setAttribute("aria-live", "polite");
    indicator.innerHTML = `
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;

    messagesContainer.appendChild(indicator);
    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById(TYPING_INDICATOR_ID);
    if (indicator) {
        indicator.remove();
    }
}

function setInputState(disabled, input, sendButton) {
    if (input) {
        input.disabled = disabled;
    }
    if (sendButton) {
        sendButton.disabled = disabled;
    }
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

function initAutoScroll() {
    const chatWindow = document.getElementById("chatWindow");
    if (chatWindow) {
        chatWindow.addEventListener("transitionend", () => {
            if (chatWindow.classList.contains("active")) {
                scrollToBottom();
            }
        });
    }

    scrollToBottom();
    setTimeout(scrollToBottom, 0);
    setTimeout(scrollToBottom, 120);
}

document.addEventListener("DOMContentLoaded", () => {
    // IMPORTANT: Include chatbot.html markup, chatbot.css styles, and this JS on every page
    // where the chat should appear. This keeps the DOM structure consistent across pages.
    initializeChat();
    restoreChatHistory();
    addQuickReplies();
    initAutoScroll();

    const input = document.getElementById("chatInput");
    if (input) {
        input.addEventListener("focus", function () {
            scrollToBottom();
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
