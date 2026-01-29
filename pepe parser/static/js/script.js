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
const analysisStats = document.getElementById('analysisStats');
const statsDetails = document.getElementById('statsDetails');

// =============== ПЕРЕМЕННЫЕ ДЛЯ ГРАФИКОВ ===============
let currentCharts = {};
let currentAnalysisData = null;
let chartRefreshInterval = null;
let lastUpdateTime = null;

// =============== ОБЩИЕ ФУНКЦИИ ===============
function showNotification(message, type = 'info') {
    notificationText.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    if (type !== 'error') {
        setTimeout(() => {
            notification.style.display = 'none';
        }, 5000);
    }
}

function hideNotification() {
    notification.style.display = 'none';
}

function updateProgress(percentage) {
    progressFill.style.width = `${percentage}%`;
    const progressBar = progressFill.parentElement;
    if (percentage > 0) {
        progressBar.style.display = 'block';
    } else {
        progressBar.style.display = 'none';
    }
}

// =============== DRAG & DROP И ЗАГРУЗКА ФАЙЛОВ ===============
function setupDragAndDrop() {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
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
    
    dropArea.addEventListener('drop', handleDrop, false);
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
        processFile(files[0]);
    }
}

function setupFileInput() {
    fileInput.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            processFile(this.files[0]);
        }
    });
}

function processFile(file) {
    const validExtensions = ['.xls', '.xlsx'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!validExtensions.includes(fileExtension)) {
        showNotification('Ошибка: разрешены только файлы Excel (.xls, .xlsx)', 'error');
        return;
    }
    
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        showNotification('Ошибка: размер файла превышает 10 МБ', 'error');
        return;
    }
    
    showNotification(`Загрузка файла: ${file.name}`, 'info');
    updateProgress(30);
    
    const formData = new FormData();
    formData.append('file', file);
    
    uploadFile(formData);
}

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
            updateProgress(100);
            
            currentAnalysisData = result;
            
            // Отображаем статистику
            displayAnalysisStats(result);
            
            // Автоматически загружаем и отображаем графики
            if (result.charts_info && result.charts_info.generated && result.charts_info.charts) {
                displayCharts(result.charts_info.charts);
                showNotification(`Файл успешно обработан! Сгенерировано ${result.charts_info.count} графиков`, 'success');
            } else {
                // Если графики не пришли с ответом, загружаем их отдельно
                await autoLoadCharts();
            }
            
            // Загружаем данные таблицы
            await loadAnalysisDataFromAPI();
            
            // Начинаем автоматическое обновление
            startAutoRefresh();
            
        } else {
            showNotification(result.error || 'Ошибка при обработке файла', 'error');
            updateProgress(0);
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showNotification('Ошибка соединения с сервером', 'error');
        updateProgress(0);
    }
}

function displayAnalysisStats(data) {
    if (!analysisStats || !statsDetails) return;
    
    analysisStats.style.display = 'block';
    
    const abcStats = data.stats.abc_distribution;
    const xyzStats = data.stats.xyz_distribution;
    
    let statsHTML = `
        <p><strong>Всего товаров:</strong> ${data.stats.total_items}</p>
        <div class="stats-grid">
    `;
    
    // Добавляем статистику ABC
    if (abcStats) {
        for (const [category, count] of Object.entries(abcStats)) {
            const percentage = ((count / data.stats.total_items) * 100).toFixed(1);
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${count}</div>
                    <div class="stat-label">ABC ${category} (${percentage}%)</div>
                </div>
            `;
        }
    }
    
    // Добавляем статистику XYZ
    if (xyzStats) {
        for (const [category, count] of Object.entries(xyzStats)) {
            const percentage = ((count / data.stats.total_items) * 100).toFixed(1);
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${count}</div>
                    <div class="stat-label">XYZ ${category} (${percentage}%)</div>
                </div>
            `;
        }
    }
    
    statsHTML += '</div>';
    statsDetails.innerHTML = statsHTML;
}

// =============== ГРАФИКИ ===============
async function autoLoadCharts() {
    try {
        showChartsLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/api/charts`);
        const data = await response.json();
        
        if (data.success && data.charts) {
            currentCharts = data.charts;
            displayCharts(currentCharts);
            await loadStatisticsForCharts();
            
            // Обновляем время последнего обновления
            lastUpdateTime = new Date();
            updateLastUpdateTime();
            
            showNotification(`Графики успешно сгенерированы!`, 'success');
        } else {
            showNotification('Не удалось загрузить графики', 'error');
            showChartsLoading(false);
        }
        
    } catch (error) {
        console.error('Ошибка загрузки графиков:', error);
        showNotification('Ошибка построения графиков', 'error');
        showChartsLoading(false);
    }
}

function displayCharts(charts) {
    // Скрываем сообщение "нет графиков"
    const noChartsMessage = document.getElementById('noChartsMessage');
    if (noChartsMessage) noChartsMessage.style.display = 'none';
    
    // Показываем контейнер графиков
    const chartsContainer = document.getElementById('chartsContainer');
    if (chartsContainer) chartsContainer.style.display = 'block';
    
    // Скрываем индикатор загрузки
    showChartsLoading(false);
    
    // Отображаем каждый график в своем контейнере
    displayIndividualCharts(charts);
}

function displayIndividualCharts(charts) {
    console.log('Отображение графиков:', Object.keys(charts));
    
     // Проверяем матрицу отдельно
    if (charts['abc_xyz_matrix']) {
        console.log('Матрица найдена, длина base64:', charts['abc_xyz_matrix'].length);
        const matrixChartImg = document.getElementById('matrixChart');
        if (matrixChartImg) {
            matrixChartImg.src = `data:image/png;base64,${charts['abc_xyz_matrix']}`;
            matrixChartImg.alt = 'Матрица ABC-XYZ';
            matrixChartImg.style.opacity = '0';
            
            // Проверяем загрузку изображения
            matrixChartImg.onload = function() {
                console.log('Матрица успешно загружена в изображение');
                this.style.opacity = '1';
                this.style.transition = 'opacity 0.5s ease';
            };
            
            matrixChartImg.onerror = function() {
                console.error('Ошибка загрузки матрицы');
                this.src = '';
                this.parentElement.innerHTML = '<div style="color: #e74c3c; text-align: center; padding: 20px;">Ошибка загрузки матрицы. Проверьте данные.</div>';
            };
            
            setTimeout(() => {
                if (matrixChartImg.style.opacity === '0') {
                    matrixChartImg.style.opacity = '1';
                    matrixChartImg.style.transition = 'opacity 0.5s ease';
                }
            }, 300);
        }
    }

    // ABC анализ
    const abcChartImg = document.getElementById('abcChart');
    if (abcChartImg && charts['abc_pie']) {
        abcChartImg.src = `data:image/png;base64,${charts['abc_pie']}`;
        abcChartImg.alt = 'ABC анализ';
        abcChartImg.style.opacity = '0';
        abcChartImg.onclick = () => openFullscreenChart('abcChart', 'ABC Анализ', 'Распределение выручки по ABC категориям. A - наиболее прибыльные товары (80% выручки), B - средние (15%), C - наименее прибыльные (5%).');
        setTimeout(() => {
            abcChartImg.style.opacity = '1';
            abcChartImg.style.transition = 'opacity 0.5s ease';
        }, 100);
    }
    
    // XYZ анализ
    const xyzChartImg = document.getElementById('xyzChart');
    if (xyzChartImg && charts['xyz_bar']) {
        xyzChartImg.src = `data:image/png;base64,${charts['xyz_bar']}`;
        xyzChartImg.alt = 'XYZ анализ';
        xyzChartImg.style.opacity = '0';
        xyzChartImg.onclick = () => openFullscreenChart('xyzChart', 'XYZ Анализ', 'Стабильность спроса по XYZ категориям. X - стабильный спрос, Y - сезонные колебания, Z - нерегулярный спрос.');
        setTimeout(() => {
            xyzChartImg.style.opacity = '1';
            xyzChartImg.style.transition = 'opacity 0.5s ease';
        }, 200);
    }
    
    // Матрица ABC-XYZ
    const matrixChartImg = document.getElementById('matrixChart');
    if (matrixChartImg && charts['abc_xyz_matrix']) {
        matrixChartImg.src = `data:image/png;base64,${charts['abc_xyz_matrix']}`;
        matrixChartImg.alt = 'Матрица ABC-XYZ';
        matrixChartImg.style.opacity = '0';
        matrixChartImg.onclick = () => openFullscreenChart('matrixChart', 'Матрица ABC-XYZ', 'Тепловая карта показывает комбинации ABC-XYZ. Позволяет определить стратегию управления для каждой группы товаров.');
        setTimeout(() => {
            matrixChartImg.style.opacity = '1';
            matrixChartImg.style.transition = 'opacity 0.5s ease';
        }, 300);
    }
    
    // Топ товаров
    const topProductsChartImg = document.getElementById('topProductsChart');
    if (topProductsChartImg && charts['top_products']) {
        topProductsChartImg.src = `data:image/png;base64,${charts['top_products']}`;
        topProductsChartImg.alt = 'Топ товаров по выручке';
        topProductsChartImg.style.opacity = '0';
        topProductsChartImg.onclick = () => openFullscreenChart('topProductsChart', 'Топ товаров по выручке', 'Самые прибыльные товары. Цветом обозначена категория ABC (зеленый - A, оранжевый - B, красный - C).');
        setTimeout(() => {
            topProductsChartImg.style.opacity = '1';
            topProductsChartImg.style.transition = 'opacity 0.5s ease';
        }, 400);
    }
}

function showChartsLoading(show) {
    const loadingElement = document.getElementById('chartsLoading');
    if (loadingElement) {
        loadingElement.style.display = show ? 'block' : 'none';
    }
}

async function loadStatisticsForCharts() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const data = await response.json();
        
        if (data.success) {
            const statsContainer = document.getElementById('statsDetails');
            if (statsContainer && analysisStats) {
                const stats = data.stats;
                
                statsContainer.innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value">${stats.total_items}</div>
                            <div class="stat-label">Всего товаров</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${stats.total_revenue.toLocaleString()}</div>
                            <div class="stat-label">Общая выручка</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${stats.average_revenue.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                            <div class="stat-label">Средняя выручка</div>
                        </div>
                    </div>
                `;
                
                analysisStats.style.display = 'block';
            }
            
            // Обновляем статистику в секции графиков
            updateChartsStats(data.stats);
            
            updateAnalysisInfoPanel(data.stats);
        }
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

function updateChartsStats(stats) {
    const statsGrid = document.getElementById('chartsStatsGrid');
    if (!statsGrid) return;
    
    let statsHTML = '';
    
    // Основная статистика
    statsHTML += `
        <div class="stat-item">
            <div class="stat-value">${stats.total_items}</div>
            <div class="stat-label">Всего товаров</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${stats.total_revenue.toLocaleString()}</div>
            <div class="stat-label">Общая выручка</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${stats.average_revenue.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
            <div class="stat-label">Средняя выручка</div>
        </div>
    `;
    
    // ABC статистика
    if (stats.abc_distribution) {
        Object.entries(stats.abc_distribution).forEach(([category, data]) => {
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${data.count}</div>
                    <div class="stat-label">ABC ${category} (${data.percentage?.toFixed(1) || 0}%)</div>
                </div>
            `;
        });
    }
    
    // XYZ статистика
    if (stats.xyz_distribution) {
        Object.entries(stats.xyz_distribution).forEach(([category, data]) => {
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${data.count}</div>
                    <div class="stat-label">XYZ ${category}</div>
                </div>
            `;
        });
    }
    
    statsGrid.innerHTML = statsHTML;
}

function updateAnalysisInfoPanel(stats) {
    if (!dynamicAnalysisInfo) return;
    
    let infoHTML = `
        <h4>Статистика анализа:</h4>
        <div class="analysis-stats">
            <p><strong>Всего товаров:</strong> ${stats.total_items}</p>
            <p><strong>Общая выручка:</strong> ${stats.total_revenue.toLocaleString()} у.е.</p>
            <p><strong>Средняя выручка:</strong> ${stats.average_revenue.toLocaleString(undefined, {maximumFractionDigits: 0})} у.е.</p>
            <p><strong>Последнее обновление:</strong> ${new Date(stats.last_update).toLocaleString()}</p>
        </div>
    `;
    
    if (stats.top_products && stats.top_products.length > 0) {
        infoHTML += `
            <h4>Топ 3 товара:</h4>
            <div class="product-list">
                ${stats.top_products.slice(0, 3).map(product => `
                    <div class="product-item">
                        ${product.name}<br>
                        <small>${product.revenue.toLocaleString()} у.е. (${product.category})</small>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    dynamicAnalysisInfo.innerHTML = infoHTML;
}

// =============== АВТООБНОВЛЕНИЕ ===============
function startAutoRefresh() {
    // Останавливаем предыдущий интервал, если он есть
    if (chartRefreshInterval) {
        clearInterval(chartRefreshInterval);
    }
    
    // Обновляем каждые 30 секунд
    chartRefreshInterval = setInterval(async () => {
        await refreshCharts();
    }, 30000);
    
    // Показываем индикатор автообновления
    showAutoRefreshIndicator(true);
}

function stopAutoRefresh() {
    if (chartRefreshInterval) {
        clearInterval(chartRefreshInterval);
        chartRefreshInterval = null;
    }
    
    showAutoRefreshIndicator(false);
    showNotification('Автообновление остановлено', 'info');
}

async function refreshCharts() {
    try {
        // Проверяем наличие новых данных
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const data = await response.json();
        
        if (data.success) {
            const lastUpdate = new Date(data.stats.last_update);
            
            // Если данные обновились после последней проверки
            if (!lastUpdateTime || lastUpdate > lastUpdateTime) {
                console.log('Обнаружены новые данные, обновляю графики...');
                
                // Показываем индикатор обновления
                showUpdateIndicator();
                
                // Обновляем графики
                await autoLoadCharts();
                
                // Обновляем таблицу
                await refreshTableData();
                
                showNotification('Данные успешно обновлены', 'info');
            }
        }
    } catch (error) {
        console.error('Ошибка обновления данных:', error);
    }
}

function showUpdateIndicator() {
    const updateIndicator = document.createElement('div');
    updateIndicator.id = 'updateIndicator';
    updateIndicator.className = 'update-indicator';
    updateIndicator.innerHTML = `
        <div class="update-spinner"></div>
        <span>Обновление данных...</span>
    `;
    
    const chartsSection = document.querySelector('.charts-section');
    if (chartsSection && !document.getElementById('updateIndicator')) {
        chartsSection.insertBefore(updateIndicator, chartsSection.firstChild);
        
        // Убираем через 3 секунды
        setTimeout(() => {
            if (updateIndicator.parentNode) {
                updateIndicator.remove();
            }
        }, 3000);
    }
}

function showAutoRefreshIndicator(show) {
    let indicator = document.getElementById('autoRefreshIndicator');
    
    if (show && !indicator) {
        indicator = document.createElement('div');
        indicator.id = 'autoRefreshIndicator';
        indicator.className = 'auto-refresh-indicator';
        indicator.innerHTML = `
            <span class="indicator-dot"></span>
            <span>Автообновление включено (30 сек)</span>
            <button class="stop-refresh-btn" onclick="stopAutoRefresh()">Остановить</button>
        `;
        
        const chartsSection = document.querySelector('.charts-section');
        if (chartsSection) {
            chartsSection.insertBefore(indicator, chartsSection.firstChild);
        }
    } else if (!show && indicator) {
        indicator.remove();
    }
}

function updateLastUpdateTime() {
    const updateTimeElement = document.getElementById('lastUpdateTime');
    if (updateTimeElement && lastUpdateTime) {
        updateTimeElement.textContent = lastUpdateTime.toLocaleTimeString();
    }
}

// =============== ТАБЛИЦА ДАННЫХ ===============
async function loadAnalysisDataFromAPI() {
    try {
        showNotification('Загрузка данных анализа из базы данных...', 'info');
        
        const response = await fetch(`${API_BASE_URL}/api/analysis-data`);
        const result = await response.json();
        
        if (result.success) {
            displayAnalysisTable(result.data);
            updateAnalysisInfo(result.data);
            
            showNotification('Данные анализа успешно загружены!', 'success');
        } else {
            // Пробуем загрузить из файла как резервный вариант
            await loadAnalysisDataFromFile();
        }
    } catch (error) {
        console.error('Ошибка загрузки анализа из API:', error);
        // Пробуем загрузить из файла как резервный вариант
        await loadAnalysisDataFromFile();
    }
}

async function loadAnalysisDataFromFile() {
    try {
        showNotification('Загрузка данных анализа из файла...', 'info');
        
        // Получаем последний файл анализа
        const response = await fetch(`${API_BASE_URL}/api/get-latest-analysis`);
        const result = await response.json();
        
        if (result.success) {
            displayAnalysisTable(result.data);
            updateAnalysisInfo(result.data);
            
            showNotification('Данные анализа успешно загружены из файла!', 'success');
        } else {
            showNotification('Нет данных для отображения', 'warning');
        }
    } catch (error) {
        console.error('Ошибка загрузки анализа из файла:', error);
        showNotification('Ошибка загрузки данных анализа', 'error');
    }
}

function displayAnalysisTable(data) {
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (!data || data.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px;">
                    Нет данных для отображения
                </td>
            </tr>
        `;
        return;
    }
    
    data.forEach((item, index) => {
        const row = document.createElement('tr');
        
        // Добавляем анимацию с задержкой для каждой строки
        row.style.animationDelay = `${index * 0.05}s`;
        row.style.opacity = '0';
        row.style.animation = 'fadeIn 0.5s ease forwards';
        
        // Определяем класс категории для цвета
        const abcClass = item.ABC ? `category-${item.ABC.toLowerCase()}` : '';
        
        row.innerHTML = `
            <td>${item.id || index + 1}</td>
            <td>${item.name || item.product_name || ''}</td>
            <td>${item.revenue ? item.revenue.toLocaleString() : 0}</td>
            <td><span class="${abcClass}">${item.ABC || ''}</span></td>
            <td>${item.XYZ || ''}</td>
            <td>${item.ABC_XYZ || ''}</td>
        `;
        tableBody.appendChild(row);
    });
}

function updateAnalysisInfo(data) {
    if (!dynamicAnalysisInfo) return;
    
    const abcCounts = { A: 0, B: 0, C: 0 };
    const xyzCounts = { X: 0, Y: 0, Z: 0 };
    
    data.forEach(item => {
        if (item.ABC && abcCounts.hasOwnProperty(item.ABC)) {
            abcCounts[item.ABC]++;
        }
        if (item.XYZ && xyzCounts.hasOwnProperty(item.XYZ)) {
            xyzCounts[item.XYZ]++;
        }
    });
    
    const sortedByRevenue = [...data].sort((a, b) => (b.revenue || 0) - (a.revenue || 0));
    const topProducts = sortedByRevenue.slice(0, 3).map(item => item.name || item.product_name || 'Без названия');
    const bottomProducts = sortedByRevenue.slice(-3).map(item => item.name || item.product_name || 'Без названия');
    
    dynamicAnalysisInfo.innerHTML = `
        <h4>По категориям ABC:</h4>
        <ul>
            <li>A (высокооборотные): ${abcCounts.A} позиций (${data.length > 0 ? ((abcCounts.A / data.length) * 100).toFixed(1) : 0}%)</li>
            <li>B (среднеоборотные): ${abcCounts.B} позиций (${data.length > 0 ? ((abcCounts.B / data.length) * 100).toFixed(1) : 0}%)</li>
            <li>C (низкооборотные): ${abcCounts.C} позиций (${data.length > 0 ? ((abcCounts.C / data.length) * 100).toFixed(1) : 0}%)</li>
        </ul>
        
        <h4>По категориям XYZ:</h4>
        <ul>
            <li>X (стабильные): ${xyzCounts.X} позиций (${data.length > 0 ? ((xyzCounts.X / data.length) * 100).toFixed(1) : 0}%)</li>
            <li>Y (сезонные): ${xyzCounts.Y} позиций (${data.length > 0 ? ((xyzCounts.Y / data.length) * 100).toFixed(1) : 0}%)</li>
            <li>Z (нерегулярные): ${xyzCounts.Z} позиций (${data.length > 0 ? ((xyzCounts.Z / data.length) * 100).toFixed(1) : 0}%)</li>
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

async function refreshTableData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/analysis-data`);
        const data = await response.json();
        
        if (data.success) {
            displayAnalysisTable(data.data);
        }
    } catch (error) {
        console.error('Ошибка обновления таблицы:', error);
    }
}

// =============== ПРОВЕРКА СУЩЕСТВУЮЩИХ ДАННЫХ ===============
async function checkExistingData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/check-data`);
        const data = await response.json();
        
        if (data.has_data && data.count > 0) {
            console.log(`Найдено ${data.count} записей, загружаем данные...`);
            
            // Показываем сообщение о загрузке существующих данных
            showNotification(`Загружаем существующие данные (${data.count} записей)...`, 'info');
            
            // Загружаем графики
            await autoLoadCharts();
            
            // Загружаем таблицу
            await loadAnalysisDataFromAPI();
            
            // Запускаем автообновление
            startAutoRefresh();
            
            showNotification(`Загружено ${data.count} записей из базы данных`, 'success');
        } else {
            console.log('В базе данных нет записей');
            // Проверяем наличие файлов анализа
            await checkAnalysisFiles();
        }
    } catch (error) {
        console.error('Ошибка проверки данных:', error);
        // Проверяем наличие файлов анализа
        await checkAnalysisFiles();
    }
}

async function checkAnalysisFiles() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/get-latest-analysis`);
        const result = await response.json();
        
        if (result.success) {
            console.log('Найден файл анализа, загружаем...');
            showNotification('Найден сохраненный файл анализа, загружаем...', 'info');
            
            displayAnalysisTable(result.data);
            updateAnalysisInfo(result.data);
            
            // Пробуем загрузить графики
            await autoLoadCharts();
            
            showNotification('Данные успешно загружены из файла!', 'success');
        }
    } catch (error) {
        console.error('Нет файлов анализа:', error);
    }
}

// =============== ИНИЦИАЛИЗАЦИЯ ===============
document.addEventListener('DOMContentLoaded', function() {
    setupDragAndDrop();
    setupFileInput();
    
    // Инициализация вкладок
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
    
    // Проверяем существующие данные при загрузке страницы
    setTimeout(() => {
        checkExistingData();
    }, 1000);
    
    // Инициализация чата
    setTimeout(initializeChat, 100);
});

// =============== ЧАТ-БОТ ===============
const botKnowledgeBase = {
    'abc анализ': {
        responses: [
            "ABC анализ — это метод классификации товаров по степени их важности. Категория A (55% товаров, 80% оборота), B (30% товаров, 15% оборота), C (15% товаров, 5% оборота).",
            "ABC анализ помогает выделить наиболее важные товары для оптимизации складских запасов и логистики.",
            "Для проведения ABC анализа нужны данные: наименование товара, выручка или количество продаж за период."
        ],
        keywords: ['abc', 'анализ abc', 'категории', 'классификация']
    },
    
    'xyz анализ': {
        responses: [
            "XYZ анализ оценивает стабильность спроса. X — стабильный спрос, Y — сезонные колебания, Z — нерегулярный спрос.",
            "Комбинированный ABC-XYZ анализ дает полную картину: важность товара + предсказуемость спроса.",
            "XYZ категория определяется по коэффициенту вариации продаж."
        ],
        keywords: ['xyz', 'анализ xyz', 'стабильность', 'спрос', 'вариация']
    },
    
    'матрица': {
        responses: [
            "Матрица ABC-XYZ показывает комбинации категорий. Например, AX - высокоприоритетные стабильные товары, CZ - низкоприоритетные нерегулярные товары.",
            "Матрица помогает определить стратегию управления: для AX товаров - максимальные запасы, для CZ - минимальные или работа под заказ.",
            "Тепловая карта матрицы визуализирует среднюю выручку по каждой комбинации ABC-XYZ."
        ],
        keywords: ['матрица', 'abc-xyz', 'комбинации', 'тепловая карта']
    },
    
    'логистика': {
        responses: [
            "Для категории A рекомендую размещение в золотой зоне (0.8-1.6 м от пола), страховой запас 30-40 дней, еженедельная инвентаризация.",
            "Категория B: средняя зона склада, запас 15-20 дней, инвентаризация раз в 2 недели.",
            "Категория C: удаленная зона, минимум запаса (7-10 дней) или работа под заказ, ежемесячная проверка."
        ],
        keywords: ['логистика', 'склад', 'размещение', 'запас', 'зона']
    },
    
    'привет': {
        responses: [
            "Здравствуйте! Я аналитический помощник. Задавайте вопросы по ABC/XYZ анализу, логистике и оптимизации.",
            "Привет! Готов помочь с анализом товарных категорий и рекомендациями по складскому хранению."
        ],
        keywords: ['привет', 'здравствуй', 'добрый день', 'здравствуйте', 'hello', 'hi']
    },
    
    'помощь': {
        responses: [
            "Я могу помочь с: 1) ABC анализом 2) XYZ анализом 3) Матрицей ABC-XYZ 4) Логистическими рекомендациями 5) Интерпретацией результатов",
            "Задавайте вопросы про: категории товаров, размещение на складе, страховые запасы, анализ эффективности, матрицу ABC-XYZ."
        ],
        keywords: ['помощь', 'help', 'что ты умееш', 'возможности', 'функции']
    },
    
    'файл': {
        responses: [
            "Для анализа загрузите Excel файл со столбцами: 'Наименование товара', 'Выручка (У.Е.)' и данные по кварталам.",
            "Формат файла: .xlsx или .csv. Обязательные поля: название товара и финансовые показатели."
        ],
        keywords: ['файл', 'excel', 'загрузить', 'формат', 'данные', 'выручка']
    },
    
    'график': {
        responses: [
            "Графики строятся автоматически после загрузки файла. Доступны: ABC анализ, XYZ анализ, матрица ABC-XYZ и топ товаров.",
            "Кликните на график для увеличения. Пробел - зум, +/- - масштаб, Esc - закрыть."
        ],
        keywords: ['график', 'диаграмма', 'визуализация', 'картинка', 'матрица']
    },
    
    'статистика': {
        responses: [
            "Статистика обновляется автоматически. Показывает: общее количество товаров, выручку, распределение по категориям.",
            "Под каждым графиком отображается соответствующая статистика для лучшего понимания данных."
        ],
        keywords: ['статистика', 'данные', 'числа', 'показатели']
    }
};

let chatHistory = [];

function toggleChat() {
    const chatWindow = document.getElementById('chatWindow');
    const isOpening = !chatWindow.classList.contains('active');
    
    chatWindow.classList.toggle('active');
    
    if (isOpening) {
        setTimeout(() => {
            document.getElementById('chatInput').focus();
        }, 300);
    }
}

function sendMessage() {
    const input = document.getElementById('chatInput');
    const userMessage = input.value.trim();
    
    if (!userMessage) return;
    
    addMessageToChat(userMessage, 'user');
    input.value = '';
    
    chatHistory.push({
        text: userMessage,
        sender: 'user',
        timestamp: new Date()
    });
    
    showTypingIndicator();
    
    setTimeout(() => {
        hideTypingIndicator();
        const botResponse = generateBotResponse(userMessage);
        addMessageToChat(botResponse, 'bot');
        
        chatHistory.push({
            text: botResponse,
            sender: 'bot',
            timestamp: new Date()
        });
        
        scrollToBottom();
    }, 1000 + Math.random() * 1000);
}

function generateBotResponse(userMessage) {
    const message = userMessage.toLowerCase();
    
    // Проверяем точные совпадения
    for (const [category, data] of Object.entries(botKnowledgeBase)) {
        for (const keyword of data.keywords) {
            if (message.includes(keyword)) {
                const responses = data.responses;
                return responses[Math.floor(Math.random() * responses.length)];
            }
        }
    }
    
    // Проверяем частичные совпадения
    const matchedCategories = [];
    for (const [category, data] of Object.entries(botKnowledgeBase)) {
        for (const keyword of data.keywords) {
            if (message.includes(keyword)) {
                matchedCategories.push(category);
                break;
            }
        }
    }
    
    if (matchedCategories.length > 0) {
        const randomCategory = matchedCategories[Math.floor(Math.random() * matchedCategories.length)];
        const responses = botKnowledgeBase[randomCategory].responses;
        return responses[Math.floor(Math.random() * responses.length)];
    }
    
    const defaultResponses = [
        "Понял ваш вопрос. Могу уточнить: интересует ли вас ABC анализ, XYZ анализ, матрица ABC-XYZ или логистические рекомендации?",
        "Для более точного ответа уточните, пожалуйста, ваш вопрос. Например: 'Как провести ABC анализ?' или 'Какие рекомендации для категории A?'",
        "Загрузите данные в формат Excel для проведения полного анализа. Нужны столбцы: наименование товара и выручка.",
        "Рекомендую посмотреть раздел с рекомендациями по логистике для разных категорий товаров."
    ];
    
    return defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
}

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

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function getCurrentTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function addQuickReply(text) {
    const input = document.getElementById('chatInput');
    input.value = text;
    input.focus();
}

function clearChatHistory() {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;
    
    const welcomeMessage = messagesContainer.querySelector('.welcome-message');
    messagesContainer.innerHTML = '';
    if (welcomeMessage) {
        messagesContainer.appendChild(welcomeMessage);
    }
    
    chatHistory = [];
    
    addMessageToChat('История диалога очищена. Чем еще могу помочь?', 'bot');
}

function initializeChat() {
    const messagesContainer = document.getElementById('chatMessages');
    if (messagesContainer) {
        // Очищаем контейнер перед добавлением приветственного сообщения
        messagesContainer.innerHTML = '';
        
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'welcome-message';
        welcomeDiv.innerHTML = `
            <p>Здравствуйте! Можете задать любой интересующий Вас вопрос по анализу и я постараюсь Вам помочь!</p>
        `;
        
        messagesContainer.appendChild(welcomeDiv);
    }
}

// =============== ПАНЕЛЬ ИНФОРМАЦИИ ===============
function toggleInfoPanel() {
    const infoPanel = document.getElementById('infoPanel');
    const toggleBtn = document.querySelector('.info-toggle-btn');
    
    if (!infoPanel || !toggleBtn) return;
    
    infoPanel.classList.toggle('active');
    toggleBtn.classList.toggle('hidden');
    
    // Если панель открывается, обновляем информацию
    if (infoPanel.classList.contains('active')) {
        updateInfoPanelContent();
    }
}

function updateInfoPanelContent() {
    // Эта функция может быть расширена для обновления содержимого панели
    console.log('Обновление содержимого информационной панели');
}

// =============== ЭКСПОРТ ФУНКЦИЙ ДЛЯ ГЛОБАЛЬНОГО ДОСТУПА ===============
window.toggleChat = toggleChat;
window.sendMessage = sendMessage;
window.handleKeyPress = handleKeyPress;
window.clearChatHistory = clearChatHistory;
window.addQuickReply = addQuickReply;
window.autoLoadCharts = autoLoadCharts;
window.stopAutoRefresh = stopAutoRefresh;
window.startAutoRefresh = startAutoRefresh;
window.refreshCharts = refreshCharts;
window.toggleInfoPanel = toggleInfoPanel;
window.checkExistingData = checkExistingData;

// Обработчики событий для панели информации и чат-бота
document.addEventListener('click', function(event) {
    const infoPanel = document.getElementById('infoPanel');
    const infoToggleBtn = document.querySelector('.info-toggle-btn');
    const chatWindow = document.getElementById('chatWindow');
    const chatBtn = document.querySelector('.chat-bot-btn');
    const closeBtn = document.querySelector('.close-btn');
    
    if (infoPanel && infoPanel.classList.contains('active')) {
        if (event.target === closeBtn || 
            (!infoPanel.contains(event.target) && 
             !infoToggleBtn.contains(event.target) &&
             !chatWindow.contains(event.target) &&
             !chatBtn.contains(event.target))) {
            toggleInfoPanel();
        }
    }
    
    // Закрытие чата
    if (chatWindow && chatWindow.classList.contains('active') && 
        !chatWindow.contains(event.target) && 
        !chatBtn.contains(event.target) &&
        !infoPanel.contains(event.target) &&
        !infoToggleBtn.contains(event.target)) {
        toggleChat();
    }
});

// Закрытие по Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const chatWindow = document.getElementById('chatWindow');
        if (chatWindow && chatWindow.classList.contains('active')) {
            toggleChat();
        }
        
        const infoPanel = document.getElementById('infoPanel');
        if (infoPanel && infoPanel.classList.contains('active')) {
            toggleInfoPanel();
        }
    }
});

// Добавляем CSS анимацию для строк таблицы
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    #analysisTable tbody tr {
        animation: fadeIn 0.5s ease forwards;
    }
    
    .category-a {
        color: #2ecc71;
        font-weight: bold;
    }
    
    .category-b {
        color: #f39c12;
        font-weight: bold;
    }
    
    .category-c {
        color: #e74c3c;
        font-weight: bold;
    }
    
    /* Стили для индикатора обновления */
    .update-indicator {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 12px;
        padding: 15px;
        margin: 20px auto;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        max-width: 300px;
        animation: slideIn 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border: 1px solid #eaeaea;
    }
    
    @keyframes slideIn {
        from {
            transform: translateY(-20px);
            opacity: 0;
        }
        to {
            transform: translateY(0);
            opacity: 1;
        }
    }
    
    .update-spinner {
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    .update-indicator span {
        color: #2c3e50;
        font-weight: 500;
    }
    
    /* Стили для автообновления */
    .auto-refresh-indicator {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 12px;
        padding: 15px 20px;
        margin: 25px auto;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        max-width: 450px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        border: 1px solid #eaeaea;
    }
    
    .indicator-dot {
        width: 12px;
        height: 12px;
        background-color: #2ecc71;
        border-radius: 50%;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { 
            opacity: 1;
            transform: scale(1);
        }
        50% { 
            opacity: 0.5;
            transform: scale(1.2);
        }
        100% { 
            opacity: 1;
            transform: scale(1);
        }
    }
    
    .stop-refresh-btn {
        background: #e74c3c;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 13px;
        cursor: pointer;
        margin-left: auto;
        transition: all 0.3s ease;
        font-weight: 500;
    }
    
    .stop-refresh-btn:hover {
        background: #c0392b;
    }
`;
document.head.appendChild(style);

// =============== ПОЛНОЭКРАННЫЙ ПРОСМОТР ГРАФИКОВ ===============
let currentZoomedImage = null;

// Функция для открытия графика в полноэкранном режиме
function openFullscreenChart(chartId, chartTitle, chartDescription) {
    const modal = document.getElementById('chartModal');
    const modalImage = document.getElementById('modalImage');
    const modalTitle = document.getElementById('modalTitle');
    const modalDescription = document.getElementById('modalDescription');
    
    // Получаем исходное изображение
    const originalImage = document.getElementById(chartId);
    if (!originalImage || !originalImage.src || originalImage.src === '') {
        showNotification('График не найден или не загружен', 'error');
        return;
    }
    
    // Устанавливаем данные в модальное окно
    modalImage.src = originalImage.src;
    modalImage.alt = chartTitle;
    modalTitle.textContent = chartTitle;
    modalDescription.textContent = chartDescription;
    
    // Показываем модальное окно
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Отключаем прокрутку страницы
    
    // Добавляем обработчик для зума по клику
    modalImage.onclick = function() {
        toggleZoom(this);
    };
    
    // Добавляем обработчики клавиш
    document.addEventListener('keydown', handleModalKeydown);
    
    // Показываем подсказку о зуме
    showZoomHint();
}

// Функция для закрытия модального окна
function closeModal() {
    const modal = document.getElementById('chartModal');
    modal.style.display = 'none';
    document.body.style.overflow = ''; // Восстанавливаем прокрутку
    
    // Сбрасываем зум
    if (currentZoomedImage) {
        currentZoomedImage.classList.remove('zoomed');
        currentZoomedImage = null;
    }
    
    // Убираем обработчики клавиш
    document.removeEventListener('keydown', handleModalKeydown);
}

// Функция для переключения зума
function toggleZoom(image) {
    if (image.classList.contains('zoomed')) {
        image.classList.remove('zoomed');
        currentZoomedImage = null;
    } else {
        image.classList.add('zoomed');
        currentZoomedImage = image;
    }
}

// Обработчик клавиш для модального окна
function handleModalKeydown(e) {
    const modal = document.getElementById('chartModal');
    if (modal.style.display !== 'block') return;
    
    switch(e.key) {
        case 'Escape':
            closeModal();
            break;
        case ' ':
            e.preventDefault();
            const modalImage = document.getElementById('modalImage');
            if (modalImage) toggleZoom(modalImage);
            break;
        case '+':
        case '=':
            e.preventDefault();
            zoomIn();
            break;
        case '-':
            e.preventDefault();
            zoomOut();
            break;
        case '0':
            e.preventDefault();
            resetZoom();
            break;
    }
}

// Функции для управления зумом
function zoomIn() {
    const modalImage = document.getElementById('modalImage');
    if (!modalImage) return;
    
    let currentScale = parseFloat(modalImage.style.transform?.replace('scale(', '')?.replace(')', '')) || 1;
    modalImage.style.transform = `scale(${currentScale * 1.2})`;
    modalImage.classList.add('zoomed');
    currentZoomedImage = modalImage;
}

function zoomOut() {
    const modalImage = document.getElementById('modalImage');
    if (!modalImage) return;
    
    let currentScale = parseFloat(modalImage.style.transform?.replace('scale(', '')?.replace(')', '')) || 1;
    const newScale = Math.max(0.5, currentScale * 0.8);
    modalImage.style.transform = `scale(${newScale})`;
    
    if (newScale <= 1) {
        modalImage.classList.remove('zoomed');
        currentZoomedImage = null;
    }
}

function resetZoom() {
    const modalImage = document.getElementById('modalImage');
    if (!modalImage) return;
    
    modalImage.style.transform = 'scale(1)';
    modalImage.classList.remove('zoomed');
    currentZoomedImage = null;
}

// Показать подсказку о зуме
function showZoomHint() {
    const hint = document.createElement('div');
    hint.className = 'zoom-hint';
    hint.innerHTML = `
        <div>🔍 Кликните по графику для увеличения</div>
        <div style="font-size: 12px; opacity: 0.8; margin-top: 5px;">
            Пробел - зум, +/- - масштаб, Esc - закрыть
        </div>
    `;
    
    document.body.appendChild(hint);
    hint.style.display = 'block';
    
    setTimeout(() => {
        if (hint.parentNode) {
            hint.remove();
        }
    }, 3000);
}

// Добавляем обработчик клика вне модального окна
document.addEventListener('click', function(event) {
    const modal = document.getElementById('chartModal');
    if (modal && modal.style.display === 'block' && event.target === modal) {
        closeModal();
    }
});

// Закрытие по Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('chartModal');
        if (modal && modal.style.display === 'block') {
            closeModal();
        }
    }
});

// Добавляем функции в глобальную область видимости
window.openFullscreenChart = openFullscreenChart;
window.closeModal = closeModal;
window.toggleZoom = toggleZoom;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;