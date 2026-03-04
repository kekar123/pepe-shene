const notification = document.getElementById('notification');
const notificationText = document.getElementById('notification-text');
const warehouseMapGrid = document.getElementById('warehouseMapGrid');
const warehouseMapMeta = document.getElementById('warehouseMapMeta');
const warehouseMapRefreshBtn = document.getElementById('warehouseMapRefreshBtn');
let notificationHideTimeout = null;

const STATIC_AISLE_LAYOUT = [
    { aisle: 748, maxPlace: 63, activeMaxPlace: 52 },
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

function buildRackCell(aisle, place) {
    const cell = document.createElement('div');
    cell.className = 'warehouse-place-cell';

    if (place && place.isOffset) {
        cell.classList.add('warehouse-place-cell-offset');
        cell.textContent = '';
        cell.title = '';
        return cell;
    }

    const placeValue = Number(place);

    if (placeValue >= 21 && placeValue <= 24) {
        cell.classList.add('warehouse-place-cell-passage');
        cell.title = `Аллея ${aisle}, проход (${placeValue})`;
    } else {
        cell.title = `Аллея ${aisle}, ячейка ${placeValue}`;
    }

    cell.textContent = String(placeValue);
    return cell;
}

function buildAisleItems(maxPlace, activeMaxPlace) {
    const items = [];
    for (let place = maxPlace; place >= 1; place -= 1) {
        if (place > activeMaxPlace) {
            items.push({ isOffset: true });
        } else {
            items.push(place);
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
        const aisleItems = buildAisleItems(layout.maxPlace, layout.activeMaxPlace);

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
        line.style.setProperty('--cell-count', String(Math.max(aisleItems.length, 1)));

        aisleItems.forEach(place => line.appendChild(buildRackCell(layout.aisle, place)));
        body.appendChild(line);

        lane.appendChild(body);
        aislesWrap.appendChild(lane);
    });

    floor.appendChild(aislesWrap);
    warehouseMapGrid.appendChild(floor);

    if (warehouseMapMeta) {
        const totalCells = STATIC_AISLE_LAYOUT.reduce((acc, row) => acc + row.maxPlace, 0);
        warehouseMapMeta.textContent = `Статическая схема | Аллей: ${STATIC_AISLE_LAYOUT.length} | Ячеек: ${totalCells}`;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (warehouseMapRefreshBtn) {
        warehouseMapRefreshBtn.addEventListener('click', () => {
            renderWarehouseMap();
            showNotification('Схема обновлена', 'success');
        });
    }
    renderWarehouseMap();
});

window.hideNotification = hideNotification;
