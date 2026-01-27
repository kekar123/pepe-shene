// Основные функции для работы с файлами
    const API_BASE_URL = 'http://localhost:5000';
    
    // DOM элементы
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const notification = document.getElementById('notification');
    const notificationText = document.getElementById('notification-text');
    const progressFill = document.getElementById('progress-fill');
    const tableBody = document.getElementById('tableBody');
    const dynamicAnalysisInfo = document.getElementById('dynamicAnalysisInfo');
    const abcChart = document.getElementById('abcChart');
    const xyzChart = document.getElementById('xyzChart');
    const analysisStats = document.getElementById('analysisStats');
    const statsDetails = document.getElementById('statsDetails');
    
    // Переменные состояния
    let currentAnalysisData = null;
    
    // Инициализация
    document.addEventListener('DOMContentLoaded', function() {
        // Настройка drag and drop
        setupDragAndDrop();
        
        // Настройка обработчика файлового ввода
        setupFileInput();
    });
    
    // Настройка drag and drop
    function setupDragAndDrop() {
        // Предотвращаем стандартное поведение браузера
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Подсветка при перетаскивании
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            dropArea.classList.add('dragover');
        }
        
        function unhighlight() {
            dropArea.classList.remove('dragover');
        }
        
        // Обработка drop
        dropArea.addEventListener('drop', handleDrop, false);
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            processFile(files[0]);
        }
    }
    
    // Настройка файлового ввода
    function setupFileInput() {
        fileInput.addEventListener('change', function(e) {
            if (this.files.length > 0) {
                processFile(this.files[0]);
            }
        });
    }
    
    // Обработка файла
    function processFile(file) {
        // Проверка типа файла
        const validExtensions = ['.xls', '.xlsx'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!validExtensions.includes(fileExtension)) {
            showNotification('Ошибка: разрешены только файлы Excel (.xls, .xlsx)', 'error');
            return;
        }
        
        // Проверка размера файла (максимум 10 МБ)
        const maxSize = 10 * 1024 * 1024; // 10 МБ
        if (file.size > maxSize) {
            showNotification('Ошибка: размер файла превышает 10 МБ', 'error');
            return;
        }
        
        // Показываем прогресс
        showNotification(`Загрузка файла: ${file.name}`, 'info');
        updateProgress(30);
        
        // Создаем FormData
        const formData = new FormData();
        formData.append('file', file);
        
        // Отправляем файл на сервер
        uploadFile(formData);
    }
    
    // Загрузка файла на сервер
    async function uploadFile(formData) {
        try {
            updateProgress(50);
            
            const response = await fetch(`${API_BASE_URL}/upload`, {
                method: 'POST',
                body: formData
            });
            
            updateProgress(80);
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                // Успешная загрузка
                updateProgress(100);
                showNotification(result.message, 'success');
                
                // Сохраняем данные анализа
                currentAnalysisData = result;
                
                // Отображаем статистику
                displayAnalysisStats(result);
                
                // Загружаем и отображаем данные анализа
                await loadAnalysisData(result.download_links.analysis);
            } else {
                // Ошибка
                showNotification(result.error || 'Ошибка при обработке файла', 'error');
                updateProgress(0);
            }
        } catch (error) {
            console.error('Ошибка загрузки:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            updateProgress(0);
        }
    }
    
    // Отображение статистики анализа
    function displayAnalysisStats(data) {
        analysisStats.style.display = 'block';
        
        const abcStats = data.stats.abc_distribution;
        const xyzStats = data.stats.xyz_distribution;
        
        statsDetails.innerHTML = `
            <p><strong>Всего товаров:</strong> ${data.stats.total_items}</p>
            <div class="stats-grid">
                ${Object.entries(abcStats).map(([category, count]) => `
                    <div class="stat-item">
                        <div class="stat-value">${count}</div>
                        <div class="stat-label">Категория ${category}</div>
                    </div>
                `).join('')}
                
                ${Object.entries(xyzStats).map(([category, count]) => `
                    <div class="stat-item">
                        <div class="stat-value">${count}</div>
                        <div class="stat-label">XYZ ${category}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Загрузка данных анализа
    async function loadAnalysisData(analysisUrl) {
        try {
            showNotification('Загрузка данных анализа...', 'info');
            
            const response = await fetch(`${API_BASE_URL}${analysisUrl}`);
            const analysisData = await response.json();
            
            // Отображаем данные в таблице
            displayAnalysisTable(analysisData);
            
            // Обновляем информацию в панели
            updateAnalysisInfo(analysisData);
            
            // Создаем визуализации
            createCharts(analysisData);
            
            showNotification('Анализ успешно загружен!', 'success');
        } catch (error) {
            console.error('Ошибка загрузки анализа:', error);
            showNotification('Ошибка загрузки данных анализа', 'error');
        }
    }
    
    // Отображение таблицы анализа
    function displayAnalysisTable(data) {
        tableBody.innerHTML = '';
        
        if (data.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 40px;">
                        Нет данных для отображения
                    </td>
                </tr>
            `;
            return;
        }
        
        data.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.id || ''}</td>
                <td>${item.name || ''}</td>
                <td>${item.revenue || 0}</td>
                <td><span class="category-${item.ABC?.toLowerCase()}">${item.ABC || ''}</span></td>
                <td>${item.XYZ || ''}</td>
                <td>${item.ABC_XYZ || ''}</td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // Обновление информации в панели
    function updateAnalysisInfo(data) {
        // Подсчет статистики
        const abcCounts = { A: 0, B: 0, C: 0 };
        const xyzCounts = { X: 0, Y: 0, Z: 0 };
        
        data.forEach(item => {
            if (abcCounts.hasOwnProperty(item.ABC)) {
                abcCounts[item.ABC]++;
            }
            if (xyzCounts.hasOwnProperty(item.XYZ)) {
                xyzCounts[item.XYZ]++;
            }
        });
        
        // Определение самых высоко- и низкоходовых товаров
        const sortedByRevenue = [...data].sort((a, b) => b.revenue - a.revenue);
        const topProducts = sortedByRevenue.slice(0, 3).map(item => item.name);
        const bottomProducts = sortedByRevenue.slice(-3).map(item => item.name);
        
        // Обновление содержимого
        dynamicAnalysisInfo.innerHTML = `
            <h4>По категориям ABC:</h4>
            <ul>
                <li>A (высокооборотные): ${abcCounts.A} позиций (${((abcCounts.A / data.length) * 100).toFixed(1)}%)</li>
                <li>B (среднеоборотные): ${abcCounts.B} позиций (${((abcCounts.B / data.length) * 100).toFixed(1)}%)</li>
                <li>C (низкооборотные): ${abcCounts.C} позиций (${((abcCounts.C / data.length) * 100).toFixed(1)}%)</li>
            </ul>
            
            <h4>По категориям XYZ:</h4>
            <ul>
                <li>X (стабильные): ${xyzCounts.X} позиций (${((xyzCounts.X / data.length) * 100).toFixed(1)}%)</li>
                <li>Y (сезонные): ${xyzCounts.Y} позиций (${((xyzCounts.Y / data.length) * 100).toFixed(1)}%)</li>
                <li>Z (нерегулярные): ${xyzCounts.Z} позиций (${((xyzCounts.Z / data.length) * 100).toFixed(1)}%)</li>
            </ul>
            
            <h4>Самые высокоходные товары:</h4>
            <div class="product-list">
                ${topProducts.map(product => `<div class="product-item">${product}</div>`).join('')}
            </div>
            
            <h4>Самые низкоходовые товары:</h4>
            <div class="product-list">
                ${bottomProducts.map(product => `<div class="product-item">${product}</div>`).join('')}
            </div>
        `;
    }
    
    // Создание графиков
    function createCharts(data) {
        // Простые HTML/CSS графики
        createSimpleChart(abcChart, data, 'ABC', ['A', 'B', 'C']);
        createSimpleChart(xyzChart, data, 'XYZ', ['X', 'Y', 'Z']);
    }
    
    function createSimpleChart(container, data, category, categories) {
        const counts = {};
        categories.forEach(cat => counts[cat] = 0);
        
        data.forEach(item => {
            if (counts.hasOwnProperty(item[category])) {
                counts[item[category]]++;
            }
        });
        
        const total = Object.values(counts).reduce((a, b) => a + b, 0);
        
        let chartHTML = '<div class="simple-chart">';
        
        categories.forEach(cat => {
            const percentage = total > 0 ? (counts[cat] / total) * 100 : 0;
            chartHTML += `
                <div class="chart-row">
                    <div class="chart-label">${cat}</div>
                    <div class="chart-bar-container">
                        <div class="chart-bar" style="width: ${percentage}%; background-color: ${getCategoryColor(cat)}"></div>
                    </div>
                    <div class="chart-value">${counts[cat]} (${percentage.toFixed(1)}%)</div>
                </div>
            `;
        });
        
        chartHTML += '</div>';
        container.innerHTML = chartHTML;
    }
    
    function getCategoryColor(category) {
        const colors = {
            'A': '#42e73c',
            'B': '#f39c12',
            'C': '#f53b35',
            'X': '#3498db',
            'Y': '#9b59b6',
            'Z': '#e74c3c'
        };
        return colors[category] || '#95a5a6';
    }
    
    // Управление уведомлениями
    function showNotification(message, type = 'info') {
        notificationText.textContent = message;
        notification.className = `notification ${type}`;
        notification.style.display = 'block';
        
        // Автоматическое скрытие
        if (type !== 'error') {
            setTimeout(() => {
                hideNotification();
            }, 5000);
        }
    }
    
    function hideNotification() {
        notification.style.display = 'none';
    }
    
    function updateProgress(percentage) {
        progressFill.style.width = `${percentage}%`;
    }

    // Функции для панели информации
    function toggleInfoPanel() {
    const infoPanel = document.getElementById('infoPanel');
    const toggleBtn = document.querySelector('.info-toggle-btn');
    
    infoPanel.classList.toggle('active');
    toggleBtn.classList.toggle('hidden');
}
    
    // ОТДЕЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ПАНЕЛИ ИНФОРМАЦИИ
    document.addEventListener('click', function(event) {
        const infoPanel = document.getElementById('infoPanel');
        const infoToggleBtn = document.querySelector('.info-toggle-btn');
        const chatWindow = document.getElementById('chatWindow');
        const chatBtn = document.querySelector('.chat-bot-btn');
        const closeBtn = document.querySelector('.close-btn');
        
        // Закрываем панель информации если:
        // 1. Она открыта
        // 2. И клик по крестику
        // ИЛИ
        // 1. Она открыта
        // 2. Клик не по панели информации
        // 3. Клик не по кнопке информации (даже если она сдвинута)
        // 4. Игнорируем клики по чат-боту и его окну
        if (infoPanel.classList.contains('active')) {
            if (event.target === closeBtn || 
                (!infoPanel.contains(event.target) && 
                 !infoToggleBtn.contains(event.target) &&
                 !chatWindow.contains(event.target) &&
                 !chatBtn.contains(event.target))) {
                toggleInfoPanel();
            }
        }
    });

    // Табы
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            const tabId = tab.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    document.querySelectorAll('.table-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.table-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        });
    });


    // =============================================
    // ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И КОНФИГУРАЦИЯ ЧАТ-БОТА
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
    // ОСНОВНЫЕ ФУНКЦИИ ЧАТ-БОТА
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
    // ИНИЦИАЛИЗАЦИЯ И ОБРАБОТЧИКИ СОБЫТИЙ ЧАТ-БОТА
    // =============================================

    document.addEventListener('DOMContentLoaded', function() {
        // Инициализация чата при загрузке
        initializeChat();
        
        // ОТДЕЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ЧАТ-БОТА
        document.addEventListener('click', function(event) {
            const chatWindow = document.getElementById('chatWindow');
            const chatBtn = document.querySelector('.chat-bot-btn');
            const infoPanel = document.getElementById('infoPanel');
            const infoToggleBtn = document.querySelector('.info-toggle-btn');
            
            // Закрываем чат только если:
            // 1. Он открыт
            // 2. Клик не по окну чата
            // 3. Клик не по кнопке чата
            // 4. Игнорируем клики по панели информации и ее кнопке
            if (chatWindow.classList.contains('active') && 
                !chatWindow.contains(event.target) && 
                !chatBtn.contains(event.target) &&
                !infoPanel.contains(event.target) &&
                !infoToggleBtn.contains(event.target)) {
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

    // =============================================
    // ЭКСПОРТ ФУНКЦИЙ ДЛЯ ГЛОБАЛЬНОГО ДОСТУПА
    // =============================================
    window.toggleChat = toggleChat;
    window.sendMessage = sendMessage;
    window.handleKeyPress = handleKeyPress;
    window.clearChatHistory = clearChatHistory;
    window.addQuickReply = addQuickReply;