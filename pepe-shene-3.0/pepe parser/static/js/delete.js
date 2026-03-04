const API_BASE_URL = (() => {
    const origin = window.location.origin;
    if (origin && origin !== 'null') return origin;
    return 'http://localhost:5000';
})();

const dropArea = document.getElementById('deleteDropArea');
const fileInput = document.getElementById('deleteFileInput');
const notification = document.getElementById('notification');
const notificationText = document.getElementById('notification-text');
const progressFill = document.getElementById('progress-fill');
const tableBody = document.getElementById('tableBody');
let notificationHideTimeout = null;

function showNotification(message, type = 'info', options = {}) {
    const autoHide = options.autoHide !== undefined ? options.autoHide : true;
    if (!notification || !notificationText) return;
    if (notificationHideTimeout) {
        clearTimeout(notificationHideTimeout);
        notificationHideTimeout = null;
    }
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
    if (notification) {
        notification.style.display = 'none';
    }
}

function updateProgress(percentage) {
    if (!progressFill) return;
    progressFill.style.width = `${percentage}%`;
    const progressBar = progressFill.parentElement;
    if (percentage > 0) {
        progressBar.style.display = 'block';
    } else {
        progressBar.style.display = 'none';
    }
}

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
        dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false);
    });

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
    fileInput.addEventListener('change', function() {
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

    showNotification(`Загрузка файла: ${file.name}`, 'info', { autoHide: false });
    updateProgress(30);

    const formData = new FormData();
    formData.append('file', file);

    deleteByFile(formData);
}

async function deleteByFile(formData) {
    try {
        updateProgress(60);
        const response = await fetch(`${API_BASE_URL}/api/delete-by-file`, {
            method: 'POST',
            body: formData
        });

        updateProgress(90);
        const result = await response.json();

        if (response.ok && result.success) {
            updateProgress(100);
            await loadAnalysisData();
            showNotification('Данные успешно удалены из БД', 'success');
        } else {
            showNotification(result.error || 'Ошибка при удалении данных', 'error');
            updateProgress(0);
        }
    } catch (error) {
        console.error('Ошибка удаления:', error);
        showNotification('Ошибка соединения с сервером', 'error');
        updateProgress(0);
    }
}

async function loadAnalysisData() {
    if (!tableBody) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/analysis-data?limit=1000`);
        const result = await response.json();

        if (result.success) {
            renderAnalysisTable(result.data || []);
        } else {
            renderAnalysisTable([]);
        }
    } catch (error) {
        console.error('Ошибка загрузки анализа:', error);
        renderAnalysisTable([]);
    }
}

function renderAnalysisTable(data) {
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

        const productName = item.name || item.product_name || item.productName || '';
        const abcCategory = item.ABC || item.abc_category || item.abcCategory || '';
        const xyzCategory = item.XYZ || item.xyz_category || item.xyzCategory || '';
        const abcXyzCategory = item.ABC_XYZ || item.abc_xyz_category || item.abcXyzCategory || '';
        const abcClass = abcCategory ? `category-${abcCategory.toLowerCase()}` : '';

        row.innerHTML = `
            <td>${item.rank ?? (index + 1)}</td>
            <td>${productName}</td>
            <td><span class="${abcClass}">${abcCategory}</span></td>
            <td>${xyzCategory}</td>
            <td>${abcXyzCategory}</td>
        `;

        tableBody.appendChild(row);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    setupDragAndDrop();
    setupFileInput();
    loadAnalysisData();
});

window.hideNotification = hideNotification;
