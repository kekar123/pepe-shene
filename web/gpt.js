// В функции toggleInfoPanel меняем:
function toggleInfoPanel() {
    const infoPanel = document.getElementById('infoPanel');
    const toggleBtn = document.querySelector('.info-toggle-btn');
    
    infoPanel.classList.toggle('active');
    
    if (infoPanel.classList.contains('active')) {
        // Убираем изменение текста, оставляем только иконку
        toggleBtn.innerHTML = '<span class="btn-icon">✕</span><span class="btn-text">Закрыть</span>';
    } else {
        toggleBtn.innerHTML = '<span class="btn-icon"></span><span class="btn-text">Показать информацию</span>';
    }
}

// В обработчике закрытия панели меняем условие:
document.addEventListener('click', function(event) {
    const infoPanel = document.getElementById('infoPanel');
    const toggleBtn = document.querySelector('.info-toggle-btn');
    
    if (infoPanel.classList.contains('active') && 
        !infoPanel.contains(event.target) && 
        !toggleBtn.contains(event.target) &&
        event.clientX > 400) { // Закрываем только если кликнули справа от панели
        toggleInfoPanel();
    }
    
});
// Делаем кнопку видимой сразу
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.querySelector('.info-toggle-btn');
    toggleBtn.classList.add('visible');
    
    // ... остальной код без изменений
});



/*бооооот*/
// =============================================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И КОНФИГУРАЦИЯ
// =============================================

// База знаний бота - вопросы и ответы
const botKnowledgeBase = {
    // Категория: ABC анализ
    'abc анализ': {
        responses: [
            "ABC анализ — это метод классификации товаров по степени их важности. Категория A (55% товаров, 80% оборота), B (30% товаров, 15% оборота), C (15% товаров, 5% оборота).",
            "ABC анализ помогает выделить наиболее важные товары для оптимизации складских запасов и логистики.",
            "Для проведения ABC анализа нужны данные: наименование товара, выручка или количество продаж за период."
        ],
        keywords: ['abc', 'анализ abc', 'категории', 'классификация']
    },
    
    // Категория: XYZ анализ
    'xyz анализ': {
        responses: [
            "XYZ анализ оценивает стабильность спроса. X — стабильный спрос, Y — сезонные колебания, Z — нерегулярный спрос.",
            "Комбинированный ABC-XYZ анализ дает полную картину: важность товара + предсказуемость спроса.",
            "XYZ категория определяется по коэффициенту вариации продаж."
        ],
        keywords: ['xyz', 'анализ xyz', 'стабильность', 'спрос', 'вариация']
    },
    
    // Категория: Логистика
    'логистика': {
        responses: [
            "Для категории A рекомендую размещение в золотой зоне (0.8-1.6 м от пола), страховой запас 30-40 дней, еженедельная инвентаризация.",
            "Категория B: средняя зона склада, запас 15-20 дней, инвентаризация раз в 2 недели.",
            "Категория C: удаленная зона, минимум запаса (7-10 дней) или работа под заказ, ежемесячная проверка."
        ],
        keywords: ['логистика', 'склад', 'размещение', 'запас', 'зона']
    },
    
    // Категория: Общие вопросы
    'привет': {
        responses: [
            "Здравствуйте! Я аналитический помощник. Задавайте вопросы по ABC/XYZ анализу, логистике и оптимизации.",
            "Привет! Готов помочь с анализом товарных категорий и рекомендациями по складскому хранению."
        ],
        keywords: ['привет', 'здравствуй', 'добрый день', 'здравствуйте', 'hello', 'hi']
    },
    
    // Категория: Помощь
    'помощь': {
        responses: [
            "Я могу помочь с: 1) ABC анализом 2) XYZ анализом 3) Логистическими рекомендациями 4) Интерпретацией результатов",
            "Задавайте вопросы про: категории товаров, размещение на складе, страховые запасы, анализ эффективности."
        ],
        keywords: ['помощь', 'help', 'что ты умеешь', 'возможности', 'функции']
    },
    
    // Категория: Файлы
    'файл': {
        responses: [
            "Для анализа загрузите Excel файл со столбцами: 'Наименование товара', 'Выручка (У.Е.)' и данные по кварталам.",
            "Формат файла: .xlsx или .csv. Обязательные поля: название товара и финансовые показатели."
        ],
        keywords: ['файл', 'excel', 'загрузить', 'формат', 'данные', 'выручка']
    }
};

// История диалога
let chatHistory = [];

// =============================================
// ОСНОВНЫЕ ФУНКЦИИ
// =============================================

/**
 * Переключение видимости окна чата
 */
function toggleChat() {
    const chatWindow = document.getElementById('chatWindow');
    const isOpening = !chatWindow.classList.contains('active');
    
    chatWindow.classList.toggle('active');
    
    // Если открываем чат - фокусируемся на поле ввода
    if (isOpening) {
        setTimeout(() => {
            document.getElementById('chatInput').focus();
        }, 300);
    }
}

/**
 * Отправка сообщения пользователя
 */
function sendMessage() {
    const input = document.getElementById('chatInput');
    const userMessage = input.value.trim();
    
    // Проверка на пустое сообщение
    if (!userMessage) return;
    
    // Добавляем сообщение пользователя
    addMessageToChat(userMessage, 'user');
    
    // Очищаем поле ввода
    input.value = '';
    
    // Сохраняем в историю
    chatHistory.push({
        text: userMessage,
        sender: 'user',
        timestamp: new Date()
    });
    
    // Имитация "печатает..." на 1 секунду
    showTypingIndicator();
    
    // Генерируем ответ через 1-2 секунды
    setTimeout(() => {
        hideTypingIndicator();
        const botResponse = generateBotResponse(userMessage);
        addMessageToChat(botResponse, 'bot');
        
        // Сохраняем ответ бота в историю
        chatHistory.push({
            text: botResponse,
            sender: 'bot',
            timestamp: new Date()
        });
        
        // Прокрутка к последнему сообщению
        scrollToBottom();
    }, 1000 + Math.random() * 1000);
}

/**
 * Генерация ответа бота на основе сообщения пользователя
 */
function generateBotResponse(userMessage) {
    const message = userMessage.toLowerCase();
    
    // Поиск по ключевым словам в базе знаний
    for (const [category, data] of Object.entries(botKnowledgeBase)) {
        for (const keyword of data.keywords) {
            if (message.includes(keyword)) {
                const responses = data.responses;
                return responses[Math.floor(Math.random() * responses.length)];
            }
        }
    }
    
    // Если не найдено совпадений - стандартные ответы
    const defaultResponses = [
        "Понял ваш вопрос. Могу уточнить: интересует ли вас ABC анализ, XYZ анализ или логистические рекомендации?",
        "Для более точного ответа уточните, пожалуйста, ваш вопрос. Например: 'Как провести ABC анализ?' или 'Какие рекомендации для категории A?'",
        "Загрузите данные в формате Excel для проведения полного анализа. Нужны столбцы: наименование товара и выручка.",
        "Рекомендую посмотреть раздел с рекомендациями по логистике для разных категорий товаров."
    ];
    
    return defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
}

/**
 * Добавление сообщения в чат
 */
function addMessageToChat(text, sender) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    
    messageDiv.className = `message ${sender}-message`;
    messageDiv.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-time">${getCurrentTime()}</div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Показать индикатор "Бот печатает..."
 */
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typingIndicator';
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.innerHTML = `
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

/**
 * Скрыть индикатор печати
 */
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

/**
 * Прокрутка чата к нижней части
 */
function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Получение текущего времени в формате HH:MM
 */
function getCurrentTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
}

/**
 * Экранирование HTML для безопасности
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Обработка нажатия Enter в поле ввода
 */
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

/**
 * Быстрые ответы для чата
 */
function addQuickReply(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    input.focus();
}

/**
 * Очистка истории чата
 */
function clearChatHistory() {
    const messagesContainer = document.getElementById('chatMessages');
    // Оставляем только приветственное сообщение
    const welcomeMessage = messagesContainer.querySelector('.welcome-message');
    messagesContainer.innerHTML = '';
    messagesContainer.appendChild(welcomeMessage);
    
    // Очищаем историю
    chatHistory = [];
    
    // Добавляем сообщение об очистке
    addMessageToChat('История диалога очищена. Чем еще могу помочь?', 'bot');
}

// =============================================
// ИНИЦИАЛИЗАЦИЯ И ОБРАБОТЧИКИ СОБЫТИЙ
// =============================================

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация чата при загрузке
    initializeChat();
    
    // Добавляем быстрые кнопки ответов (опционально)
    addQuickReplies();
    
    // Фокус на поле ввода при открытии чата
    document.getElementById('chatInput').addEventListener('focus', function() {
        this.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    
    // Обработчик для закрытия чата по клику вне окна
    document.addEventListener('click', function(event) {
        const chatWindow = document.getElementById('chatWindow');
        const chatBtn = document.querySelector('.chat-bot-btn');
        
        if (chatWindow.classList.contains('active') && 
            !chatWindow.contains(event.target) && 
            !chatBtn.contains(event.target)) {
            toggleChat();
        }
    });
    
    // Закрытие чата по Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const chatWindow = document.getElementById('chatWindow');
            if (chatWindow.classList.contains('active')) {
                toggleChat();
            }
        }
    });
});

/**
 * Инициализация чата при загрузке
 */
function initializeChat() {
    // Очищаем сообщения, оставляя только приветствие
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <p>Здравствуйте! Можете задать любой интересующий Вас вопрос по анализу и я постараюсь Вам помочь!</p>
        </div>
    `;
}

/**
 * Добавление быстрых ответов (опциональная функция)
 */
function addQuickReplies() {
    const quickReplies = [
        "Что такое ABC анализ?",
        "Как проводить XYZ анализ?",
        "Рекомендации по логистике",
        "Какой формат файла нужен?",
        "Спасибо, понятно"
    ];
    
    // Эта функция может быть использована для добавления кнопок быстрых ответов
    // в интерфейс, если потребуется
}

// =============================================
// ЭКСПОРТ ФУНКЦИЙ ДЛЯ ГЛОБАЛЬНОГО ДОСТУПА
// =============================================
window.toggleChat = toggleChat;
window.sendMessage = sendMessage;
window.handleKeyPress = handleKeyPress;
window.clearChatHistory = clearChatHistory;
window.addQuickReply = addQuickReply;