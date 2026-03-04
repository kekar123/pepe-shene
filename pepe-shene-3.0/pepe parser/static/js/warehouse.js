const API_BASE_URL = (() => {
    const origin = window.location.origin;
    if (origin && origin !== 'null') return origin;
    return 'http://localhost:5000';
})();

const notification = document.getElementById('notification');
const notificationText = document.getElementById('notification-text');
const warehouseMapGrid = document.getElementById('warehouseMapGrid');
const warehouseMapMeta = document.getElementById('warehouseMapMeta');
const reportInput = document.getElementById('warehouseReportInput');
const chooseBtn = document.getElementById('warehouseReportChooseBtn');
const applyBtn = document.getElementById('warehouseReportApplyBtn');
const fileNameEl = document.getElementById('warehouseReportFileName');
let notificationHideTimeout = null;

let stockColorByCell = {};

const STATIC_AISLE_LAYOUT = [
    { aisle: 748, maxPlace: 63, activeMaxPlace: 53 },
    { aisle: 747, maxPlace: 63, activeMaxPlace: 63 },
    { aisle: 746, maxPlace: 63, activeMaxPlace: 63 },
    { aisle: 745, maxPlace: 63, activeMaxPlace: 63 },
    { aisle: 744, maxPlace: 63, activeMaxPlace: 63 },
    { aisle: 743, maxPlace: 63, activeMaxPlace: 63 },
    { aisle: 742, maxPlace: 63, activeMaxPlace: 63 },
];

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
        }, 3000);
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

function buildRackCell(aisle, place, isOffset = false) {
    const cell = document.createElement('div');
    cell.className = 'warehouse-place-cell';

    if (isOffset) {
        cell.classList.add('warehouse-place-cell-offset');
        cell.textContent = '';
        cell.title = '';
        return cell;
    }

    const isPassage = place >= 21 && place <= 24;
    if (isPassage) {
        cell.classList.add('warehouse-place-cell-passage');
        cell.title = `Аллея ${aisle}, проход (${place})`;
    } else {
        const color = stockColorByCell[`${aisle}-${place}`];
        if (color === 'red') cell.classList.add('warehouse-place-cell-stock-red');
        if (color === 'yellow') cell.classList.add('warehouse-place-cell-stock-yellow');
        if (color === 'green') cell.classList.add('warehouse-place-cell-stock-green');
        cell.title = `Аллея ${aisle}, ячейка ${place}`;
    }

    cell.textContent = String(place);
    return cell;
}

function buildAisleItems(globalMaxPlace, aisleMaxPlace) {
    const items = [];
    for (let place = globalMaxPlace; place >= 1; place -= 1) {
        if (place > aisleMaxPlace) {
            items.push({ isOffset: true, place });
        } else {
            items.push({ isOffset: false, place });
        }
    }
    return items;
}

function renderWarehouseMap() {
    if (!warehouseMapGrid) return;

    warehouseMapGrid.innerHTML = '';

    const floor = document.createElement('div');
    floor.className = 'warehouse-floor';

    const aislesWrap = document.createElement('div');
    aislesWrap.className = 'warehouse-aisles';

    STATIC_AISLE_LAYOUT.forEach(layout => {
        const lane = document.createElement('section');
        lane.className = 'warehouse-aisle-lane';

        const header = document.createElement('div');
        header.className = 'warehouse-aisle-title';
        header.textContent = `Аллея ${String(layout.aisle).padStart(3, '0')}`;
        lane.appendChild(header);

        const body = document.createElement('div');
        body.className = 'warehouse-lane-body';

        const line = document.createElement('div');
        line.className = 'warehouse-aisle-line';
        line.style.setProperty('--cell-count', String(Math.max(layout.maxPlace, 1)));

        const items = buildAisleItems(layout.maxPlace, layout.activeMaxPlace);
        items.forEach(item => line.appendChild(buildRackCell(layout.aisle, item.place, item.isOffset)));

        body.appendChild(line);
        lane.appendChild(body);
        aislesWrap.appendChild(lane);
    });

    floor.appendChild(aislesWrap);
    warehouseMapGrid.appendChild(floor);

    if (warehouseMapMeta) {
        const paintedCells = Object.keys(stockColorByCell).length;
        warehouseMapMeta.textContent = paintedCells
            ? `Окрашено по стоку: ${paintedCells} ячеек`
            : '';
    }
}

async function uploadReportAndBuild() {
    const file = reportInput && reportInput.files ? reportInput.files[0] : null;
    if (!file) {
        showNotification('Сначала выберите файл общего отчета', 'error');
        return;
    }

    const extension = '.' + file.name.split('.').pop().toLowerCase();
    if (!['.xls', '.xlsx'].includes(extension)) {
        showNotification('Разрешены только Excel файлы (.xls, .xlsx)', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('report_file', file);

    try {
        showNotification('Обработка отчета...', 'info', { autoHide: false });
        const response = await fetch(`${API_BASE_URL}/api/warehouse-layout-from-report`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            showNotification(result.error || 'Не удалось применить цвета из отчета', 'error');
            return;
        }

        stockColorByCell = result.colors || {};

        renderWarehouseMap();
        showNotification('Ячейки окрашены по загруженному отчету', 'success');
    } catch (error) {
        console.error('Ошибка загрузки отчета:', error);
        showNotification('Ошибка соединения с сервером', 'error');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (chooseBtn && reportInput) {
        chooseBtn.addEventListener('click', () => reportInput.click());
    }

    if (reportInput && fileNameEl) {
        reportInput.addEventListener('change', () => {
            const file = reportInput.files && reportInput.files[0];
            fileNameEl.textContent = file ? file.name : 'Файл не выбран';
        });
    }

    if (applyBtn) {
        applyBtn.addEventListener('click', uploadReportAndBuild);
    }

    renderWarehouseMap();
});

window.hideNotification = hideNotification;
