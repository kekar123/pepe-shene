// Основные функции для работы с файлами
const API_BASE_URL = (() => {
    const origin = window.location.origin;
    if (origin && origin !== 'null') return origin;
    return 'http://localhost:5000';
})();

// DOM элементы
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInput');
const notification = document.getElementById('notification');
const notificationText = document.getElementById('notification-text');
const progressFill = document.getElementById('progress-fill');
const tableBody = document.getElementById('tableBody');
const combinedFileInput = document.getElementById('combinedFileInput');
const combinedMasterInput = document.getElementById('combinedMasterInput');
const combinedMovementsInput = document.getElementById('combinedMovementsInput');
const combinedLinesInput = document.getElementById('combinedLinesInput');
const combinedAbcInput = document.getElementById('combinedAbcInput');
const combinedOrderPickedInput = document.getElementById('combinedOrderPickedInput');
const combinedStockInput = document.getElementById('combinedStockInput');
const combinedGenerateBtn = document.getElementById('combinedGenerateBtn');
const combinedMasterName = document.getElementById('combinedMasterName');
const combinedMovementsName = document.getElementById('combinedMovementsName');
const combinedLinesName = document.getElementById('combinedLinesName');
const combinedAbcName = document.getElementById('combinedAbcName');
const combinedOrderPickedName = document.getElementById('combinedOrderPickedName');
const combinedStockName = document.getElementById('combinedStockName');
const combinedTableBody = document.getElementById('combinedTableBody');
const combinedReportDownload = document.getElementById('combinedReportDownload');
const DISABLE_DB_NOTIFICATIONS = window.DISABLE_DB_NOTIFICATIONS === true;
const dynamicAnalysisInfo = document.getElementById('dynamicAnalysisInfo');
const analysisStats = document.getElementById('analysisStats');
const statsDetails = document.getElementById('statsDetails');
let notificationHideTimeout = null;

// =============== ПЕРЕМЕННЫЕ ДЛЯ ГРАФИКОВ ===============
let currentCharts = {};
let currentAnalysisData = null;
let chartRefreshInterval = null;
let lastUpdateTime = null;
// Временный переключатель: чтобы оставить только ABC график на странице,
// поставьте true. Верните false, чтобы снова включить все графики.
const SHOW_ONLY_ABC_CHART = true;
// Показываем всплывающие уведомления при авто-загрузке только на перезагрузке страницы.
const INITIAL_LOAD_SHOW_NOTIFICATIONS = (() => {
    try {
        const entries = performance.getEntriesByType && performance.getEntriesByType('navigation');
        if (entries && entries.length > 0) {
            return entries[0].type === 'reload';
        }
    } catch (e) {
        // ignore
    }
    return !!(performance && performance.navigation && performance.navigation.type === 1);
})();

// =============== ОБЩИЕ ФУНКЦИИ ===============
function showNotification(message, type = 'info', options = {}) {
    const autoHide = options.autoHide !== undefined ? options.autoHide : true;
    if (notificationHideTimeout) {
        clearTimeout(notificationHideTimeout);
        notificationHideTimeout = null;
    }
    notification.classList.remove('hiding');
    notificationText.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    if (type !== 'error' && autoHide) {
        notificationHideTimeout = setTimeout(() => {
            notification.style.display = 'none';
            notificationHideTimeout = null;
        }, 5000);
    }
}

function hideNotification() {
    if (notificationHideTimeout) {
        clearTimeout(notificationHideTimeout);
        notificationHideTimeout = null;
    }
    notification.classList.add('hiding');
    setTimeout(() => {
        notification.style.display = 'none';
        notification.classList.remove('hiding');
    }, 250);
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
    if (!dropArea) return;
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
    if (!fileInput) return;
    fileInput.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            processFile(this.files[0]);
        }
    });
}

function setupCombinedFileInput() {
    // Backward compatibility: old single multi-file input.
    if (combinedFileInput) {
        combinedFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                processCombinedFiles(Array.from(this.files));
            }
        });
    }

    // New flow: one input per required file + explicit generate button.
    const bindName = (inputEl, nameEl) => {
        if (!inputEl || !nameEl) return;
        const card = inputEl.closest('.combined-upload-card');
        const refreshState = () => {
            const hasFile = !!(inputEl.files && inputEl.files[0]);
            nameEl.textContent = hasFile ? inputEl.files[0].name : 'Файл не выбран';
            if (card) {
                card.classList.toggle('file-selected', hasFile);
            }
        };
        inputEl.addEventListener('change', () => {
            refreshState();
        });
        refreshState();
    };

    bindName(combinedMasterInput, combinedMasterName);
    bindName(combinedMovementsInput, combinedMovementsName);
    bindName(combinedLinesInput, combinedLinesName);
    bindName(combinedAbcInput, combinedAbcName);
    bindName(combinedOrderPickedInput, combinedOrderPickedName);
    bindName(combinedStockInput, combinedStockName);

    if (combinedGenerateBtn) {
        combinedGenerateBtn.addEventListener('click', processCombinedNamedFiles);
    }
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
    
    showNotification(`Загрузка файла: ${file.name}`, 'info', { autoHide: false });
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
            
            // Рендерим таблицу сразу из ответа /upload (без дополнительного запроса)
            const inlineData = Array.isArray(result.analysis_data) ? result.analysis_data : [];
            if (inlineData.length > 0) {
                displayAnalysisTable(inlineData);
                updateAnalysisInfo(inlineData);
                // Фоновая синхронизация из БД, чтобы данные на странице совпадали с persisted-состоянием.
                reloadAnalysisDataWithRetry({ attempts: 2, delayMs: 120, showLoadingIndicator: false }).catch(() => {});
            } else {
                // Фолбэк: если сервер не передал данные, берем из БД.
                showNotification('Загружаем таблицу...', 'info', { autoHide: false });
                updateProgress(70);
                await reloadAnalysisDataWithRetry({ attempts: 5, delayMs: 150, showLoadingIndicator: false });
            }
            updateProgress(90);
            hideNotification();

            // Графики загружаем отдельно, чтобы не блокировать таблицу
            if (result.charts_info && result.charts_info.generated && result.charts_info.charts) {
                displayCharts(result.charts_info.charts);
            } else {
                // Если графиков нет в ответе, генерируем/подгружаем их отдельным запросом
                autoLoadCharts();
            }
            
            // Начинаем автоматическое обновление
            // startAutoRefresh();
            
            showNotification('Данные успешно добавлены в БД', 'success');
            
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

function processCombinedFiles(files) {
    const validExtensions = ['.xls', '.xlsx'];
    const maxSize = 10 * 1024 * 1024;
    const invalid = [];

    const formData = new FormData();
    files.forEach(file => {
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExtensions.includes(fileExtension)) {
            invalid.push(file.name);
            return;
        }
        if (file.size > maxSize) {
            invalid.push(file.name);
            return;
        }
        formData.append('files', file);
    });

    if (invalid.length > 0) {
        showNotification(`Ошибка: неподходящие файлы: ${invalid.join(', ')}`, 'error');
        return;
    }

    showNotification(`Загрузка файлов для общего отчета: ${files.length}`, 'info', { autoHide: false });
    updateProgress(30);
    uploadCombinedFiles(formData);
}

function processCombinedNamedFiles() {
    const required = [
        { key: 'master_file', input: combinedMasterInput, label: 'Основные данные (Article Master Data)' },
        { key: 'movements_file', input: combinedMovementsInput, label: 'Движения стока' },
        { key: 'lines_file', input: combinedLinesInput, label: 'Линии пикинга' },
        { key: 'abc_file', input: combinedAbcInput, label: 'ABC анализ' },
        { key: 'order_picked_file', input: combinedOrderPickedInput, label: 'Проверка заказано-собрано' },
        { key: 'stock_file', input: combinedStockInput, label: 'PUD отчет по стоку' },
    ];

    const validExtensions = ['.xls', '.xlsx'];
    const maxSize = 10 * 1024 * 1024;
    const formData = new FormData();

    for (const item of required) {
        const file = item.input && item.input.files ? item.input.files[0] : null;
        if (!file) {
            showNotification(`Ошибка: не выбран файл "${item.label}"`, 'error');
            return;
        }

        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExtensions.includes(fileExtension)) {
            showNotification(`Ошибка: "${item.label}" должен быть Excel (.xls, .xlsx)`, 'error');
            return;
        }
        if (file.size > maxSize) {
            showNotification(`Ошибка: "${item.label}" превышает 10 МБ`, 'error');
            return;
        }
        formData.append(item.key, file);
    }

    showNotification('Формирование общего отчета...', 'info', { autoHide: false });
    updateProgress(30);
    uploadCombinedFiles(formData);
}

async function uploadCombinedFiles(formData) {
    try {
        updateProgress(50);
        const response = await fetch(`${API_BASE_URL}/upload-combined`, {
            method: 'POST',
            body: formData
        });
        updateProgress(80);
        const result = await response.json();

        if (response.ok && result.success) {
            updateProgress(100);
            hideNotification();
            showNotification('Общий отчет сформирован', 'success');
            displayCombinedReport(result.rows || []);
            if (combinedReportDownload && result.report_file) {
                combinedReportDownload.href = `${API_BASE_URL}/download-report/${encodeURIComponent(result.report_file)}`;
                combinedReportDownload.style.display = 'inline-block';
            }
        } else {
            const message = result.error || 'Ошибка при формировании отчета';
            showNotification(message, 'error');
            updateProgress(0);
        }
    } catch (error) {
        console.error('Ошибка загрузки файлов:', error);
        showNotification('Ошибка соединения с сервером', 'error');
        updateProgress(0);
    }
}

function displayCombinedReport(rows) {
    if (!combinedTableBody) return;
    combinedTableBody.innerHTML = '';

    if (!rows || rows.length === 0) {
        renderCombinedCharts([]);
        combinedTableBody.innerHTML = `
            <tr>
                <td colspan="22" style="text-align: center; padding: 40px;">
                    Нет данных для общего отчета
                </td>
            </tr>
        `;
        return;
    }

    rows.forEach(row => {
        const tr = document.createElement('tr');
        const status = (row['Мертвый сток'] || '').toString().toLowerCase();
        if (status === 'красный') tr.classList.add('dead-stock-red');
        if (status === 'желтый') tr.classList.add('dead-stock-yellow');
        if (status === 'зеленый') tr.classList.add('dead-stock-green');

        tr.innerHTML = `
            <td>${row['АРТИКУЛ'] ?? ''}</td>
            <td>${row['НАЗВАНИЕ'] ?? ''}</td>
            <td>${row['Аллея пикинг'] ?? ''}</td>
            <td>${row['Место пикинг'] ?? ''}</td>
            <td>${row['MAX PICK'] ?? 0}</td>
            <td>${row['Кол-во палет реапро'] ?? 0}</td>
            <td>${row['Кол-во коробов реапро'] ?? 0}</td>
            <td>${row['Кол-во штук Реапро'] ?? 0}</td>
            <td>${row['Кол-во заказов'] ?? 0}</td>
            <td>${row['Дата последнего выхода'] ?? ''}</td>
            <td>${row['Выход в коробах из пикинга'] ?? 0}</td>
            <td>${row['Выход в штуках'] ?? 0}</td>
            <td>${row['Палетизация'] ?? ''}</td>
            <td>${row['PCB'] ?? ''}</td>
            <td>${row['ABC класс'] ?? ''}</td>
            <td>${row['Стокаж'] ?? ''}</td>
            <td>${row['Кол-во линий'] ?? 0}</td>
            <td>${(row['Процент (реаппро)'] ?? 0).toFixed ? row['Процент (реаппро)'].toFixed(2) : (row['Процент (реаппро)'] ?? 0)}</td>
            <td>${(row['Популярность (реаппро)'] ?? 0).toFixed ? row['Популярность (реаппро)'].toFixed(2) : (row['Популярность (реаппро)'] ?? 0)}</td>
            <td>${(row['Процент (линии)'] ?? 0).toFixed ? row['Процент (линии)'].toFixed(2) : (row['Процент (линии)'] ?? 0)}</td>
            <td>${(row['Популярность (линии)'] ?? 0).toFixed ? row['Популярность (линии)'].toFixed(2) : (row['Популярность (линии)'] ?? 0)}</td>
            <td>${row['Мертвый сток'] ?? ''}</td>
        `;
        combinedTableBody.appendChild(tr);
    });

    renderCombinedCharts(rows);
}

function renderCombinedCharts(rows) {
    const abcChartImg = document.getElementById('combinedAbcChartImage');
    const chartsContainer = document.getElementById('combinedChartsContainer');
    const noChartsMessage = document.getElementById('combinedNoChartsMessage');
    if (!abcChartImg || !chartsContainer || !noChartsMessage) return;

    const counts = { A: 0, B: 0, C: 0 };
    const total = Array.isArray(rows) ? rows.length : 0;

    rows.forEach(row => {
        const raw = (row['ABC класс'] ?? '').toString().trim().toUpperCase();
        if (raw === 'A' || raw === 'B' || raw === 'C') {
            counts[raw] += 1;
        }
    });

    if (!total) {
        chartsContainer.style.display = 'none';
        noChartsMessage.style.display = 'block';
        abcChartImg.removeAttribute('src');
        abcChartImg.onclick = null;
        return;
    }

    chartsContainer.style.display = 'block';
    noChartsMessage.style.display = 'none';

    const size = 520;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Explicit white background so exported image is not transparent.
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, size, size);

    const values = [counts.A, counts.B, counts.C];
    const labels = ['A', 'B', 'C'];
    const colors = ['#2ecc71', '#f39c12', '#e74c3c'];

    let startAngle = -Math.PI / 2;
    const cx = size / 2;
    const cy = size / 2;
    const radius = 170;

    values.forEach((value, index) => {
        const slice = total > 0 ? (value / total) * Math.PI * 2 : 0;
        const endAngle = startAngle + slice;

        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, radius, startAngle, endAngle);
        ctx.closePath();
        ctx.fillStyle = colors[index];
        ctx.fill();

        // подпись сектора
        if (value > 0) {
            const mid = startAngle + slice / 2;
            const tx = cx + Math.cos(mid) * (radius * 0.65);
            const ty = cy + Math.sin(mid) * (radius * 0.65);
            const pct = ((value / total) * 100).toFixed(1);
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 22px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${labels[index]} ${pct}%`, tx, ty);
        }

        startAngle = endAngle;
    });

    // центральный круг и общее число
    ctx.beginPath();
    ctx.arc(cx, cy, 78, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.fillStyle = '#1f2f46';
    ctx.font = 'bold 34px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(String(total), cx, cy - 8);
    ctx.font = '16px Arial';
    ctx.fillStyle = '#5a6d88';
    ctx.fillText('товаров', cx, cy + 20);

    // легенда
    const legendY = size - 90;
    labels.forEach((label, i) => {
        const x = 85 + i * 145;
        const value = values[i];
        const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
        ctx.fillStyle = colors[i];
        ctx.fillRect(x, legendY, 18, 18);
        ctx.fillStyle = '#1f2f46';
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(`${label}: ${value} (${pct}%)`, x + 26, legendY + 14);
    });

    abcChartImg.src = canvas.toDataURL('image/png');
    abcChartImg.alt = 'ABC анализ';
    abcChartImg.onclick = () => openFullscreenChart(
        'combinedAbcChartImage',
        'ABC Анализ',
        'Распределение товаров по классам A, B, C в общем отчете.'
    );
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
            
            if (!window.DISABLE_CHART_NOTIFICATIONS) {
                showNotification(`Графики успешно сгенерированы!`, 'success');
            }
        } else {
            if (!window.DISABLE_CHART_NOTIFICATIONS) {
                showNotification('Не удалось загрузить графики', 'error');
            }
            showChartsLoading(false);
        }
        
    } catch (error) {
        console.error('Ошибка загрузки графиков:', error);
        if (!window.DISABLE_CHART_NOTIFICATIONS) {
            showNotification('Ошибка построения графиков', 'error');
        }
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
        console.log('ABC график: длина base64:', charts['abc_pie'] ? charts['abc_pie'].length : 0);
        abcChartImg.src = `data:image/png;base64,${charts['abc_pie']}`;
        abcChartImg.alt = 'ABC анализ';
        abcChartImg.style.opacity = '0';
        abcChartImg.onclick = () => openFullscreenChart('abcChart', 'ABC Анализ');
        abcChartImg.onerror = function() {
            console.error('Ошибка загрузки ABC графика');
            this.src = '';
            this.parentElement.innerHTML = '<div style="color: #e74c3c; text-align: center; padding: 20px;">Ошибка загрузки ABC графика. Проверьте данные.</div>';
        };
        setTimeout(() => {
            abcChartImg.style.opacity = '1';
            abcChartImg.style.transition = 'opacity 0.5s ease';
        }, 100);
    }

    // Временная блокировка остальных графиков (кроме ABC)
    if (SHOW_ONLY_ABC_CHART) {
        const xyzChartImg = document.getElementById('xyzChart');
        const matrixChartImg = document.getElementById('matrixChart');
        const topProductsChartImg = document.getElementById('topProductsChart');
        const xyzCard = xyzChartImg ? xyzChartImg.closest('.chart-card') : null;
        const matrixCard = matrixChartImg ? matrixChartImg.closest('.chart-card') : null;
        const topProductsCard = topProductsChartImg ? topProductsChartImg.closest('.chart-card') : null;
        if (xyzCard) xyzCard.style.display = 'none';
        if (matrixCard) matrixCard.style.display = 'none';
        if (topProductsCard) topProductsCard.style.display = 'none';
        return;
    }
    
    // XYZ анализ
    const xyzChartImg = document.getElementById('xyzChart');
    if (xyzChartImg && charts['xyz_bar']) {
        xyzChartImg.src = `data:image/png;base64,${charts['xyz_bar']}`;
        xyzChartImg.alt = 'XYZ анализ';
        xyzChartImg.style.opacity = '0';
        xyzChartImg.onclick = () => openFullscreenChart('xyzChart', 'XYZ Анализ');
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
        matrixChartImg.onclick = () => openFullscreenChart('matrixChart', 'Матрица ABC-XYZ');
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
        topProductsChartImg.onclick = () => openFullscreenChart('topProductsChart');
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
// Автообновление отключено по запросу:
// данные должны обновляться только при загрузке файлов.
// function startAutoRefresh() {
//     // Останавливаем предыдущий интервал, если он есть
//     if (chartRefreshInterval) {
//         clearInterval(chartRefreshInterval);
//     }
//     
//     // Обновляем каждые 30 секунд
//     chartRefreshInterval = setInterval(async () => {
//         await refreshCharts();
//     }, 30000);
//     
//     // Показываем индикатор автообновления
//     showAutoRefreshIndicator(true);
// }
//
// function stopAutoRefresh() {
//     if (chartRefreshInterval) {
//         clearInterval(chartRefreshInterval);
//         chartRefreshInterval = null;
//     }
//     
//     showAutoRefreshIndicator(false);
//     showNotification('Автообновление остановлено', 'info');
// }
//
// async function refreshCharts() {
//     try {
//         // Проверяем наличие новых данных
//         const response = await fetch(`${API_BASE_URL}/api/stats`);
//         const data = await response.json();
//         
//         if (data.success) {
//             const lastUpdate = new Date(data.stats.last_update);
//             
//             // Если данные обновились после последней проверки
//             if (!lastUpdateTime || lastUpdate > lastUpdateTime) {
//                 console.log('Обнаружены новые данные, обновляю графики...');
//                 
//                 // Показываем индикатор обновления
//                 showUpdateIndicator();
//                 
//                 // Обновляем графики
//                 await autoLoadCharts();
//                 
//                 // Обновляем таблицу
//                 await refreshTableData();
//                 
//                 showNotification('Данные успешно обновлены', 'info');
//             }
//         }
//     } catch (error) {
//         console.error('Ошибка обновления данных:', error);
//     }
// }
//
// function showUpdateIndicator() {
//     const updateIndicator = document.createElement('div');
//     updateIndicator.id = 'updateIndicator';
//     updateIndicator.className = 'update-indicator';
//     updateIndicator.innerHTML = `
//         <div class="update-spinner"></div>
//         <span>Обновление данных...</span>
//     `;
//     
//     const chartsSection = document.querySelector('.charts-section');
//     if (chartsSection && !document.getElementById('updateIndicator')) {
//         chartsSection.insertBefore(updateIndicator, chartsSection.firstChild);
//         
//         // Убираем через 3 секунды
//         setTimeout(() => {
//             if (updateIndicator.parentNode) {
//                 updateIndicator.remove();
//             }
//         }, 3000);
//     }
// }
//
// function showAutoRefreshIndicator(show) {
//     let indicator = document.getElementById('autoRefreshIndicator');
//     
//     if (show && !indicator) {
//         indicator = document.createElement('div');
//         indicator.id = 'autoRefreshIndicator';
//         indicator.className = 'auto-refresh-indicator';
//         indicator.innerHTML = `
//             <span class="indicator-dot"></span>
//             <span>Автообновление включено (30 сек)</span>
//             <button class="stop-refresh-btn" onclick="stopAutoRefresh()">Остановить</button>
//         `;
//         
//         const chartsSection = document.querySelector('.charts-section');
//         if (chartsSection) {
//             chartsSection.insertBefore(indicator, chartsSection.firstChild);
//         }
//     } else if (!show && indicator) {
//         indicator.remove();
//     }
// }

function updateLastUpdateTime() {
    const updateTimeElement = document.getElementById('lastUpdateTime');
    if (updateTimeElement && lastUpdateTime) {
        updateTimeElement.textContent = lastUpdateTime.toLocaleTimeString();
    }
}

// =============== ТАБЛИЦА ДАННЫХ ===============
async function loadAnalysisDataFromAPI(options = {}) {
    const showNotifications = options.showNotifications !== undefined ? options.showNotifications : true;
    try {
        if (showNotifications && !DISABLE_DB_NOTIFICATIONS) {
            showNotification('Загрузка данных анализа из базы данных...', 'info');
        }
        
        const response = await fetch(`${API_BASE_URL}/api/analysis-data?limit=1000`);
        const result = await response.json();
        
        if (result.success) {
            displayAnalysisTable(result.data);
            updateAnalysisInfo(result.data);
            
            if (showNotifications) {
                if (!DISABLE_DB_NOTIFICATIONS) {
                    showNotification('Данные анализа успешно загружены!', 'success');
                }
            }
            return Array.isArray(result.data) ? result.data.length : 0;
        } else {
            displayAnalysisTable([]);
            return 0;
        }
    } catch (error) {
        console.error('Ошибка загрузки анализа из API:', error);
        displayAnalysisTable([]);
        return 0;
    }
}

async function reloadAnalysisDataWithRetry(options = {}) {
    const attempts = options.attempts || 3;
    const delayMs = options.delayMs || 500;
    const showLoadingIndicator = options.showLoadingIndicator || false;
    let lastCount = 0;

    for (let i = 0; i < attempts; i += 1) {
        if (showLoadingIndicator) {
            const stepPercent = Math.min(80, 50 + Math.round(((i + 1) / attempts) * 30));
            updateProgress(stepPercent);
        }
        lastCount = await loadAnalysisDataFromAPI({ showNotifications: false });
        if (lastCount > 0) {
            return lastCount;
        }
        if (i < attempts - 1) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
        }
    }

    return lastCount;
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
            
            if (!DISABLE_DB_NOTIFICATIONS) {
                showNotification('Данные анализа успешно загружены из файла!', 'success');
            }
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
                <td colspan="5" style="text-align: center; padding: 40px;">
                    База данных пока пуста
                </td>
            </tr>
        `;
        return;
    }
    
    const shouldAnimateRows = data.length <= 120;
    const fragment = document.createDocumentFragment();

    data.forEach((item, index) => {
        const row = document.createElement('tr');
        
        if (shouldAnimateRows) {
            // Не даем задержке расти линейно до десятков секунд.
            row.classList.add('row-fade-in');
            row.style.animationDelay = `${Math.min(index * 0.015, 0.6)}s`;
        }
        
        const productName = item.name || item.product_name || item.productName || '';
        const revenue = item.revenue ?? item.total_revenue ?? 0;
        const abcCategory = item.ABC || item.abc_category || item.abcCategory || '';
        const xyzCategory = item.XYZ || item.xyz_category || item.xyzCategory || '';
        const abcXyzCategory = item.ABC_XYZ || item.abc_xyz_category || item.abcXyzCategory || '';

        // Определяем класс категории для цвета
        const abcClass = abcCategory ? `category-${abcCategory.toLowerCase()}` : '';
        
        row.innerHTML = `
            <td>${item.rank ?? (index + 1)}</td>
            <td>${productName}</td>
            <td><span class="${abcClass}">${abcCategory}</span></td>
            <td>${xyzCategory}</td>
            <td>${abcXyzCategory}</td>
        `;
        fragment.appendChild(row);
    });

    tableBody.appendChild(fragment);
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
async function checkExistingData(options = {}) {
    const showNotifications = options.showNotifications !== undefined ? options.showNotifications : true;
    try {
        const response = await fetch(`${API_BASE_URL}/api/check-data`);
        const data = await response.json();
        
        if (data.has_data && data.count > 0) {
            console.log(`Найдено ${data.count} записей, загружаем данные...`);
            
            // Показываем сообщение о загрузке существующих данных
            if (showNotifications) {
                if (!DISABLE_DB_NOTIFICATIONS) {
                    showNotification(`Загружаем существующие данные (${data.count} записей)...`, 'info');
                }
            }
            
            // Загружаем таблицу
            await loadAnalysisDataFromAPI({ showNotifications });

            // Графики загружаем отдельно, чтобы таблица появилась быстрее
            autoLoadCharts();
            
            // Запускаем автообновление
            // startAutoRefresh();
            
            if (showNotifications) {
                if (!DISABLE_DB_NOTIFICATIONS) {
                    showNotification(`Загружено ${data.count} записей из базы данных`, 'success');
                }
            }
        } else {
            console.log('В базе данных нет записей');
            // Показываем сообщение в таблице, чтобы не оставлять пустой блок
            displayAnalysisTable([]);
        }
    } catch (error) {
        console.error('Ошибка проверки данных:', error);
        // В случае ошибки показываем пустую таблицу с сообщением
        displayAnalysisTable([]);
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
    setupCombinedFileInput();
    
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
        checkExistingData({ showNotifications: INITIAL_LOAD_SHOW_NOTIFICATIONS });
    }, 1000);
    
});

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
window.autoLoadCharts = autoLoadCharts;
window.stopAutoRefresh = stopAutoRefresh;
// window.startAutoRefresh = startAutoRefresh;
// window.refreshCharts = refreshCharts;
window.toggleInfoPanel = toggleInfoPanel;
window.checkExistingData = checkExistingData;

// Обработчики событий для панели информации
document.addEventListener('click', function(event) {
    const infoPanel = document.getElementById('infoPanel');
    const infoToggleBtn = document.querySelector('.info-toggle-btn');
    const closeBtn = document.querySelector('.close-btn');
    
    if (infoPanel && infoPanel.classList.contains('active')) {
        if (event.target === closeBtn || 
            (!infoPanel.contains(event.target) && 
             !infoToggleBtn.contains(event.target))) {
            toggleInfoPanel();
        }
    }
});

// Закрытие по Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
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
    
    #analysisTable tbody tr.row-fade-in {
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

// script.js - добавьте новые функции

async function loadVisualizationData(sessionId = null, options = {}) {
    const showNotifications = options.showNotifications !== undefined ? options.showNotifications : true;
    try {
        if (showNotifications) {
            showNotification('Загрузка данных для визуализации...', 'info');
        }
        
        let url = `${API_BASE_URL}/api/visualization/data`;
        if (sessionId) {
            url += `?session_id=${sessionId}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            // Отображаем данные в таблице
            displayProductsTable(data.products.data);
            
            // Отображаем статистику
            displayCategoryStats(data.category_stats);
            
            // Отображаем матрицу
            displayMatrixData(data.matrix_data);
            
            // Отображаем графики если они есть
            if (data.has_charts && data.charts) {
                displayCharts(data.charts);
            } else {
                // Если графиков нет, генерируем их
                await generateAndDisplayCharts(data);
            }
            
            // Сохраняем ID сессии
            currentSessionId = data.session_info?.id;
            
            if (showNotifications) {
                showNotification('Данные визуализации загружены', 'success');
            }
            return true;
        } else {
            if (showNotifications) {
                showNotification('Ошибка загрузки данных: ' + (data.error || 'Неизвестная ошибка'), 'error');
            }
            return false;
        }
        
    } catch (error) {
        console.error('Ошибка загрузки данных визуализации:', error);
        if (showNotifications) {
            showNotification('Ошибка загрузки данных визуализации', 'error');
        }
        return false;
    }
}

function displayProductsTable(products) {
    if (!tableBody) return;
    
    tableBody.innerHTML = '';

    if (!products || products.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 40px;">
                    База данных пока пуста
                </td>
            </tr>
        `;
        return;
    }
    
    products.forEach((product, index) => {
        const row = document.createElement('tr');
        
        const abcClass = `category-${product.abc_category?.toLowerCase() || 'c'}`;
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${product.product_name || 'Без названия'}</td>
            <td>${product.product_code || ''}</td>
            <td>${product.quantity ? parseFloat(product.quantity).toLocaleString() : 0}</td>
            <td>${product.revenue ? parseFloat(product.revenue).toLocaleString(undefined, {minimumFractionDigits: 2}) : '0.00'}</td>
            <td><span class="${abcClass}">${product.abc_category || 'C'}</span></td>
            <td>${product.xyz_category || 'Z'}</td>
            <td>${product.abc_xyz_category || 'CZ'}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

function displayCategoryStats(stats) {
    if (!analysisStats || !statsDetails) return;
    
    analysisStats.style.display = 'block';
    
    let statsHTML = `
        <div class="stats-grid">
    `;
    
    // ABC статистика
    if (stats.abc) {
        for (const [category, data] of Object.entries(stats.abc)) {
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${data.products_count || 0}</div>
                    <div class="stat-label">ABC ${category}</div>
                    <div class="stat-sub">${data.revenue_percentage ? data.revenue_percentage.toFixed(1) : 0}% выручки</div>
                </div>
            `;
        }
    }
    
    // XYZ статистика
    if (stats.xyz) {
        for (const [category, data] of Object.entries(stats.xyz)) {
            statsHTML += `
                <div class="stat-item">
                    <div class="stat-value">${data.products_count || 0}</div>
                    <div class="stat-label">XYZ ${category}</div>
                    <div class="stat-sub">${data.revenue_percentage ? data.revenue_percentage.toFixed(1) : 0}% выручки</div>
                </div>
            `;
        }
    }
    
    statsHTML += '</div>';
    statsDetails.innerHTML = statsHTML;
}

function displayMatrixData(matrixData) {
    // Обновляем информационную панель с данными матрицы
    const matrixInfo = document.getElementById('matrixInfo');
    if (matrixInfo) {
        let matrixHTML = '<h4>Матрица ABC-XYZ:</h4><div class="matrix-grid">';
        
        // Группируем по ABC категориям
        const grouped = {};
        matrixData.forEach(cell => {
            if (!grouped[cell.abc_category]) {
                grouped[cell.abc_category] = [];
            }
            grouped[cell.abc_category].push(cell);
        });
        
        // Создаем таблицу матрицы
        matrixHTML += '<table class="matrix-table"><thead><tr><th>ABC\\XYZ</th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody>';
        
        ['A', 'B', 'C'].forEach(abcCat => {
            matrixHTML += `<tr><td class="matrix-header">${abcCat}</td>`;
            
            ['X', 'Y', 'Z'].forEach(xyzCat => {
                const cell = matrixData.find(c => c.abc_category === abcCat && c.xyz_category === xyzCat);
                if (cell) {
                    matrixHTML += `
                        <td class="matrix-cell ${abcCat.toLowerCase()}">
                            <strong>${cell.products_count}</strong> шт.<br>
                            <small>${cell.total_revenue ? parseFloat(cell.total_revenue).toLocaleString() : 0}</small>
                        </td>
                    `;
                } else {
                    matrixHTML += `<td class="matrix-cell empty">-</td>`;
                }
            });
            
            matrixHTML += '</tr>';
        });
        
        matrixHTML += '</tbody></table>';
        matrixInfo.innerHTML = matrixHTML;
    }
}

// В инициализации добавьте:
document.addEventListener('DOMContentLoaded', function() {
    // ... существующий код ...
    
    // При загрузке страницы пробуем загрузить последние данные из БД
    setTimeout(async () => {
        const hasData = await loadVisualizationData(null, { showNotifications: INITIAL_LOAD_SHOW_NOTIFICATIONS });
        if (!hasData) {
            console.log('В базе данных нет сохраненных анализов');
            // Показываем сообщение о необходимости загрузить файл
            if (INITIAL_LOAD_SHOW_NOTIFICATIONS) {
                showNotification('Загрузите Excel файл для начала анализа', 'info');
            }
        }
    }, 1000);
});



// Добавьте после других функций в script.js

async function loadAnalysisDataFromDB(options = {}) {
    const showNotifications = options.showNotifications !== undefined ? options.showNotifications : true;
    try {
        if (showNotifications) {
            showNotification('Загрузка данных анализа из базы данных...', 'info');
        }
        
        // Проверяем наличие данных
        const checkResponse = await fetch(`${API_BASE_URL}/api/check-analysis-data`);
        const checkData = await checkResponse.json();
        
        if (!checkData.has_data) {
            if (showNotifications && !DISABLE_DB_NOTIFICATIONS) {
                showNotification('В базе данных нет сохраненных анализов', 'warning');
            }
            displayAnalysisTableFromDB([]);
            return false;
        }
        
        // Загружаем данные анализа
        const analysisResponse = await fetch(`${API_BASE_URL}/api/analysis-data?limit=100`);
        const analysisData = await analysisResponse.json();
        
        if (analysisData.success && analysisData.data) {
            // Отображаем данные в таблице
            displayAnalysisTableFromDB(analysisData.data);
            
            // Загружаем статистику
            const statsResponse = await fetch(`${API_BASE_URL}/api/analysis-stats`);
            const statsData = await statsResponse.json();
            
            if (statsData.success) {
                displayAnalysisStatsFromDB(statsData.stats);
            }
            
            // Загружаем данные матрицы
            const matrixResponse = await fetch(`${API_BASE_URL}/api/matrix-data`);
            const matrixData = await matrixResponse.json();
            
            if (matrixData.success) {
                updateMatrixInfoFromDB(matrixData.data);
            }
            
            // Загружаем графики
            const chartsResponse = await fetch(`${API_BASE_URL}/api/analysis-charts`);
            const chartsData = await chartsResponse.json();
            
            if (chartsData.success && chartsData.charts) {
                displayCharts(chartsData.charts);
            } else {
                // Если графиков нет в БД, генерируем новые
                await autoLoadCharts();
            }
            
            if (showNotifications && !DISABLE_DB_NOTIFICATIONS) {
                showNotification('Данные успешно загружены из базы данных', 'success');
            }
            return true;
        }
        
        return false;
        
    } catch (error) {
        console.error('Ошибка загрузки данных анализа из БД:', error);
        if (showNotifications && !DISABLE_DB_NOTIFICATIONS) {
            showNotification('Ошибка загрузки данных из базы данных', 'error');
        }
        return false;
    }
}

function displayAnalysisTableFromDB(data) {
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (!data || data.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 40px;">
                    База данных пока пуста
                </td>
            </tr>
        `;
        return;
    }
    
    data.forEach((item, index) => {
        const row = document.createElement('tr');
        
        // Анимация
        row.style.animationDelay = `${index * 0.05}s`;
        row.style.opacity = '0';
        row.style.animation = 'fadeIn 0.5s ease forwards';
        
        // Определяем класс для категории ABC
        const abcClass = `category-${item.abc_category?.toLowerCase() || 'c'}`;
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${item.product_name || 'Без названия'}</td>
            <td>${item.product_code || ''}</td>
            <td>${item.quantity ? item.quantity.toLocaleString() : 0}</td>
            <td>${item.revenue ? item.revenue.toLocaleString(undefined, {minimumFractionDigits: 2}) : '0.00'}</td>
            <td><span class="${abcClass}">${item.abc_category || 'C'}</span></td>
            <td>${item.xyz_category || 'Z'}</td>
            <td>${item.abc_xyz_category || 'CZ'}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

function displayAnalysisStatsFromDB(stats) {
    if (!analysisStats || !statsDetails) return;
    
    analysisStats.style.display = 'block';
    
    let statsHTML = `
        <p><strong>Всего товаров:</strong> ${stats.total_products || 0}</p>
        <p><strong>Общая выручка:</strong> ${(stats.total_revenue || 0).toLocaleString()} у.е.</p>
        <p><strong>Средняя выручка:</strong> ${(stats.avg_revenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2})} у.е.</p>
        <div class="stats-grid">
    `;
    
    // Добавляем статистику ABC
    if (stats.a_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.a_count}</div>
                <div class="stat-label">Категория A</div>
            </div>
        `;
    }
    
    if (stats.b_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.b_count}</div>
                <div class="stat-label">Категория B</div>
            </div>
        `;
    }
    
    if (stats.c_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.c_count}</div>
                <div class="stat-label">Категория C</div>
            </div>
        `;
    }
    
    // Добавляем статистику XYZ
    if (stats.x_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.x_count}</div>
                <div class="stat-label">Категория X</div>
            </div>
        `;
    }
    
    if (stats.y_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.y_count}</div>
                <div class="stat-label">Категория Y</div>
            </div>
        `;
    }
    
    if (stats.z_count !== undefined) {
        statsHTML += `
            <div class="stat-item">
                <div class="stat-value">${stats.z_count}</div>
                <div class="stat-label">Категория Z</div>
            </div>
        `;
    }
    
    statsHTML += '</div>';
    
    if (stats.top_product_name) {
        statsHTML += `
            <p><strong>Топ товар:</strong> ${stats.top_product_name}</p>
            <p><strong>Выручка топ товара:</strong> ${(stats.top_product_revenue || 0).toLocaleString()} у.е.</p>
        `;
    }
    
    statsDetails.innerHTML = statsHTML;
}

function updateMatrixInfoFromDB(matrixData) {
    if (!dynamicAnalysisInfo) return;
    
    let matrixHTML = '<h4>Матрица ABC-XYZ:</h4><div class="matrix-grid">';
    
    matrixData.forEach(item => {
        const category = item.abc_xyz_category || '';
        const count = item.products_count || 0;
        const revenue = item.total_revenue || 0;
        const recommendation = item.recommendation || '';
        
        matrixHTML += `
            <div class="matrix-item">
                <div class="matrix-category">${category}</div>
                <div class="matrix-count">${count} товаров</div>
                <div class="matrix-revenue">${revenue.toLocaleString()} у.е.</div>
                <div class="matrix-recommendation">${recommendation}</div>
            </div>
        `;
    });
    
    matrixHTML += '</div>';
    
    // Добавляем к существующему содержимому
    const currentContent = dynamicAnalysisInfo.innerHTML;
    dynamicAnalysisInfo.innerHTML = matrixHTML + currentContent;
}

// Обновите инициализацию в конце script.js
document.addEventListener('DOMContentLoaded', function() {
    // ... существующий код ...
    
    // Пробуем загрузить данные из БД анализа при загрузке страницы
    setTimeout(async () => {
        const hasData = await loadAnalysisDataFromDB({ showNotifications: INITIAL_LOAD_SHOW_NOTIFICATIONS });
        if (!hasData) {
            console.log('В базе данных анализа нет сохраненных данных');
        }
    }, 1000);
});
