const statusLabels = {
    overdue: "SCADUTA",
    due_soon: "IN ARRIVO",
    up_to_date: "REGOLARE",
};

const addVehicleOptionValue = "add-new-vehicle";
const accessTokenStorageKey = "car-maintenance-access-token";
const numberFormatter = new Intl.NumberFormat("it-IT", {
    useGrouping: "always",
});
const wholeNumberFormatter = new Intl.NumberFormat("it-IT", {
    maximumFractionDigits: 0,
    useGrouping: "always",
});
const currencyFormatter = new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
});
let activeCarId = null;
let currentMileage = 0;
let currentUser = null;

function isActiveCar(carId) {
    return String(carId) === String(activeCarId);
}

function createTableCell(label, content) {
    const cell = document.createElement("td");
    cell.dataset.label = label;

    if (content instanceof Node) {
        cell.appendChild(content);
    } else {
        cell.textContent = content;
    }

    return cell;
}

function renderEmptyState(tableBody, message, columnCount) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.className = "empty-state";
    cell.colSpan = columnCount;
    cell.textContent = message;
    row.appendChild(cell);
    tableBody.replaceChildren(row);
    syncListScrollLimit(tableBody);
}

function replaceTableRows(tableBody, rows) {
    const fragment = document.createDocumentFragment();
    rows.forEach((row) => fragment.appendChild(row));
    tableBody.replaceChildren(fragment);
    syncListScrollLimit(tableBody);
}

function syncListScrollLimit(tableBody) {
    const container = tableBody.closest(".scrollable-list");
    if (!container) return;

    container.style.maxHeight = "";
    const rows = Array.from(tableBody.rows).filter(
        (row) => !row.classList.contains("empty-row"),
    );
    const hasMoreRows = rows.length > 5;
    container.classList.toggle("has-more", hasMoreRows);
    if (!hasMoreRows) return;

    requestAnimationFrame(() => {
        const visibleRows = Array.from(tableBody.rows).filter(
            (row) => !row.classList.contains("empty-row"),
        );
        if (
            visibleRows.length <= 5
            || !container.isConnected
            || container.closest("[hidden]")
        ) {
            return;
        }

        const isMobile = window.matchMedia("(max-width: 700px)").matches;
        const table = tableBody.closest("table");
        const headerHeight = isMobile
            ? 0
            : table.querySelector("thead")?.getBoundingClientRect().height ?? 0;
        const rowsHeight = visibleRows.slice(0, 5).reduce((total, row) => {
            const styles = getComputedStyle(row);
            return total
                + row.getBoundingClientRect().height
                + Number.parseFloat(styles.marginTop)
                + Number.parseFloat(styles.marginBottom);
        }, 0);
        const containerStyles = getComputedStyle(container);
        const borders = Number.parseFloat(containerStyles.borderTopWidth)
            + Number.parseFloat(containerStyles.borderBottomWidth);
        const hintHeight = container.querySelector(".scroll-hint").getBoundingClientRect().height;
        const nextRowPeek = 12;
        container.style.maxHeight = `${Math.ceil(headerHeight + rowsHeight + borders + nextRowPeek + hintHeight)}px`;
    });
}

function createDeleteButton(label, onDelete, accessibleLabel = label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-danger btn-small btn-delete";
    button.textContent = label;
    button.setAttribute("aria-label", accessibleLabel);
    button.addEventListener("click", onDelete);
    return button;
}

function showAppError(message) {
    const errorElement = document.getElementById("app-error");
    if (!errorElement) return;

    errorElement.textContent = message;
    errorElement.hidden = false;
}

function clearAppError() {
    const errorElement = document.getElementById("app-error");
    if (!errorElement) return;

    errorElement.textContent = "";
    errorElement.hidden = true;
}

function showMaintenanceFormError(message) {
    const overlay = document.getElementById("maintenance-error-overlay");
    const messageElement = document.getElementById("maintenance-error-message");
    if (!overlay || !messageElement) return;

    messageElement.textContent = message;
    overlay.hidden = false;
}

function clearMaintenanceFormError() {
    const overlay = document.getElementById("maintenance-error-overlay");
    const messageElement = document.getElementById("maintenance-error-message");
    if (!overlay || !messageElement) return;

    messageElement.textContent = "";
    overlay.hidden = true;
}

function closeMaintenanceError() {
    clearMaintenanceFormError();
}

async function getApiErrorMessage(response) {
    const responseBody = await response.text();
    let payload;

    try {
        payload = JSON.parse(responseBody);
    } catch {
        return responseBody || `Richiesta API fallita: HTTP ${response.status}`;
    }

    if (typeof payload?.detail === "string") return payload.detail;
    if (Array.isArray(payload?.detail)) {
        return payload.detail
            .map(item => item.msg ?? JSON.stringify(item))
            .join("; ");
    }
    return responseBody || `Richiesta API fallita: HTTP ${response.status}`;
}

async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers);
    const accessToken = sessionStorage.getItem(accessTokenStorageKey);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) {
        sessionStorage.removeItem(accessTokenStorageKey);
        clearGarageData();
        document.getElementById("garage-app").hidden = true;
        document.getElementById("login-screen").hidden = false;
    }
    return response;
}

document.addEventListener("DOMContentLoaded", () => {
    initializeApplication();
});

async function initializeApplication() {
    const setupScreen = document.getElementById("superuser-setup");
    const loginScreen = document.getElementById("login-screen");
    const garageApp = document.getElementById("garage-app");

    try {
        const response = await fetch(API_ENDPOINTS.auth.checkSetup());
        if (!response.ok) throw new Error(await getApiErrorMessage(response));

        const setup = await response.json();
        if (setup.needs_setup) {
            setupScreen.hidden = false;
            return;
        }

        if (sessionStorage.getItem(accessTokenStorageKey)) {
            garageApp.hidden = false;
            await initializeAuthenticatedApp();
        } else {
            loginScreen.hidden = false;
        }
    } catch (error) {
        garageApp.hidden = false;
        showAppError(`Impossibile verificare la configurazione: ${error.message}`);
    }
}

let lastWidth = window.innerWidth;

window.addEventListener("resize", () => {
    if (window.innerWidth !== lastWidth) {
        lastWidth = window.innerWidth;
        document.querySelectorAll(".scrollable-list tbody").forEach(syncListScrollLimit);
    }
});

async function checkGarageStatus(preferredCarId = null) {
    try {
        const response = await apiFetch(API_ENDPOINTS.cars.collection());
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        const cars = await response.json();

        if (cars.length === 0) {
            clearGarageData();
            if (!currentUser?.is_superuser) openCarModal(true);
        } else {
            populateCarSelector(cars);

            const selectedCar = cars.find(car => car.id === preferredCarId)
                ?? cars.find(car => car.id === activeCarId)
                ?? cars[0];
            document.getElementById('car-selector').value = selectedCar.id;
            await selectCar(selectedCar.id);
        }
    } catch (error) {
        console.error("Errore nel controllo del garage:", error);
        showAppError(error.message);
    }
}

const superuserSetupForm = document.getElementById("superuser-setup-form");
superuserSetupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorElement = document.getElementById("setup-error");
    const submitButton = document.getElementById("setup-submit");
    errorElement.hidden = true;
    submitButton.disabled = true;

    const formData = new FormData(superuserSetupForm);
    const payload = {
        full_name: formData.get("full_name") || null,
        email: formData.get("email"),
        password: formData.get("password"),
    };

    try {
        const response = await fetch(API_ENDPOINTS.auth.setupSuperuser(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));

        document.getElementById("superuser-setup").hidden = true;
        const loginScreen = document.getElementById("login-screen");
        loginScreen.hidden = false;
        document.getElementById("login-email").value = payload.email;
        document.getElementById("login-password").focus();
    } catch (error) {
        errorElement.textContent = error.message;
        errorElement.hidden = false;
    } finally {
        submitButton.disabled = false;
    }
});

const loginForm = document.getElementById("login-form");
const registrationForm = document.getElementById("registration-form");

document.getElementById("show-registration").addEventListener("click", () => {
    loginForm.hidden = true;
    document.getElementById("show-registration").hidden = true;
    registrationForm.hidden = false;
    document.getElementById("registration-success").hidden = true;
});

document.getElementById("show-login").addEventListener("click", () => {
    registrationForm.hidden = true;
    loginForm.hidden = false;
    document.getElementById("show-registration").hidden = false;
});

registrationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorElement = document.getElementById("registration-error");
    const successElement = document.getElementById("registration-success");
    const submitButton = document.getElementById("registration-submit");
    errorElement.hidden = true;
    successElement.hidden = true;
    submitButton.disabled = true;

    const formData = new FormData(registrationForm);
    const payload = {
        full_name: formData.get("full_name") || null,
        email: formData.get("email"),
        password: formData.get("password"),
    };

    try {
        const response = await fetch(API_ENDPOINTS.auth.signup(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));

        registrationForm.reset();
        registrationForm.hidden = true;
        loginForm.hidden = false;
        document.getElementById("show-registration").hidden = false;
        document.getElementById("login-email").value = payload.email;
        successElement.textContent = "Account creato. Ora puoi accedere.";
        successElement.hidden = false;
    } catch (error) {
        errorElement.textContent = error.message;
        errorElement.hidden = false;
    } finally {
        submitButton.disabled = false;
    }
});

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorElement = document.getElementById("login-error");
    const submitButton = document.getElementById("login-submit");
    errorElement.hidden = true;
    submitButton.disabled = true;

    const formData = new FormData(loginForm);
    const body = new URLSearchParams({
        username: formData.get("email"),
        password: formData.get("password"),
    });

    try {
        const response = await fetch(API_ENDPOINTS.auth.login(), {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));

        const token = await response.json();
        sessionStorage.setItem(accessTokenStorageKey, token.access_token);
        clearGarageData();
        document.getElementById("login-screen").hidden = true;
        document.getElementById("garage-app").hidden = false;
        clearAppError();
        await initializeAuthenticatedApp();
    } catch (error) {
        errorElement.textContent = error.message;
        errorElement.hidden = false;
    } finally {
        submitButton.disabled = false;
    }
});

async function initializeAuthenticatedApp() {
    const response = await apiFetch(API_ENDPOINTS.users.me());
    if (!response.ok) throw new Error(await getApiErrorMessage(response));

    currentUser = await response.json();
    document.getElementById("profile-button").hidden = false;
    document.getElementById("admin-user-management").hidden = !currentUser.is_superuser;
    document.getElementById("profile-panel").hidden = true;
    await checkGarageStatus();
}

document.getElementById("logout-button").addEventListener("click", () => {
    sessionStorage.removeItem(accessTokenStorageKey);
    clearGarageData();
    currentUser = null;
    document.getElementById("profile-button").hidden = true;
    document.getElementById("profile-panel").hidden = true;
    document.getElementById("garage-app").hidden = true;
    document.getElementById("login-screen").hidden = false;
});

document.getElementById("profile-button").addEventListener("click", async () => {
    const panel = document.getElementById("profile-panel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
        document.getElementById("profile-full-name").value = currentUser.full_name ?? "";
        document.getElementById("profile-email").value = currentUser.email;
        clearProfileMessages();
        if (currentUser.is_superuser) await loadUserManagement();
    }
});

document.getElementById("close-profile").addEventListener("click", () => {
    document.getElementById("profile-panel").hidden = true;
});

document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = document.getElementById("profile-submit");
    submitButton.disabled = true;
    clearProfileMessages();

    const formData = new FormData(form);
    const payload = {
        full_name: formData.get("full_name") || null,
        email: formData.get("email"),
    };

    try {
        const response = await apiFetch(API_ENDPOINTS.users.updateMe(), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        currentUser = await response.json();
        document.getElementById("profile-success").textContent = "Dati account aggiornati.";
        document.getElementById("profile-success").hidden = false;
    } catch (error) {
        showProfileError(error.message);
    } finally {
        submitButton.disabled = false;
    }
});

document.getElementById("password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = document.getElementById("password-submit");
    submitButton.disabled = true;
    clearProfileMessages();

    const formData = new FormData(form);
    const payload = {
        current_password: formData.get("current_password"),
        new_password: formData.get("new_password"),
    };

    try {
        const response = await apiFetch(API_ENDPOINTS.users.updateMyPassword(), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        form.reset();
        document.getElementById("profile-success").textContent = "Password aggiornata.";
        document.getElementById("profile-success").hidden = false;
    } catch (error) {
        showProfileError(error.message);
    } finally {
        submitButton.disabled = false;
    }
});

document.getElementById("admin-create-user-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = document.getElementById("admin-create-user-submit");
    submitButton.disabled = true;
    clearUserManagementError();

    const formData = new FormData(form);
    const payload = {
        full_name: formData.get("full_name") || null,
        email: formData.get("email"),
        password: formData.get("password"),
    };

    try {
        const response = await apiFetch(API_ENDPOINTS.users.collection(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        form.reset();
        await loadUserManagement();
    } catch (error) {
        showUserManagementError(error.message);
    } finally {
        submitButton.disabled = false;
    }
});

async function loadUserManagement() {
    clearUserManagementError();
    try {
        const response = await apiFetch(API_ENDPOINTS.users.statistics());
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        const statistics = await response.json();
        document.getElementById("active-users-count").textContent = statistics.active_users;
        document.getElementById("total-cars-count").textContent = statistics.total_cars;

        const tableBody = document.getElementById("user-table-body");
        const rows = statistics.data.map((user) => {
            const row = document.createElement("tr");
            row.appendChild(createTableCell("Utente", `${user.full_name || user.email}\n${user.email}`));
            row.appendChild(createTableCell("Ruolo", user.is_superuser ? "Superuser" : "Utente"));
            row.appendChild(createTableCell("Stato", user.is_active ? "Attivo" : "Sospeso"));
            row.appendChild(createTableCell("Auto", String(user.cars_count)));

            const actions = document.createElement("td");
            actions.dataset.label = "Azioni";
            const isCurrentUser = user.id === currentUser.id;
            const toggleButton = document.createElement("button");
            toggleButton.type = "button";
            toggleButton.className = "btn btn-secondary btn-small";
            toggleButton.textContent = user.is_active ? "SOSPENDI" : "RIATTIVA";
            toggleButton.disabled = isCurrentUser;
            toggleButton.title = isCurrentUser ? "Non puoi sospendere il tuo account" : "";
            toggleButton.addEventListener("click", () => updateManagedUser(user, { is_active: !user.is_active }));
            actions.appendChild(toggleButton);

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "btn btn-danger btn-small";
            deleteButton.textContent = "RIMUOVI";
            deleteButton.disabled = isCurrentUser;
            deleteButton.title = isCurrentUser ? "Non puoi rimuovere il tuo account da qui" : "";
            deleteButton.addEventListener("click", () => deleteManagedUser(user));
            actions.appendChild(deleteButton);
            row.appendChild(actions);
            return row;
        });
        replaceTableRows(tableBody, rows);
    } catch (error) {
        showUserManagementError(error.message);
    }
}

async function updateManagedUser(user, updates) {
    clearUserManagementError();
    try {
        const response = await apiFetch(API_ENDPOINTS.users.byId(user.id), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updates),
        });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        await loadUserManagement();
    } catch (error) {
        showUserManagementError(error.message);
    }
}

async function deleteManagedUser(user) {
    if (!window.confirm(`Rimuovere l'utente ${user.email} e i suoi dati?`)) return;
    clearUserManagementError();
    try {
        const response = await apiFetch(API_ENDPOINTS.users.byId(user.id), { method: "DELETE" });
        if (!response.ok) throw new Error(await getApiErrorMessage(response));
        await loadUserManagement();
    } catch (error) {
        showUserManagementError(error.message);
    }
}

function showUserManagementError(message) {
    const errorElement = document.getElementById("user-management-error");
    errorElement.textContent = message;
    errorElement.hidden = false;
}

function clearUserManagementError() {
    const errorElement = document.getElementById("user-management-error");
    errorElement.textContent = "";
    errorElement.hidden = true;
}

function showProfileError(message) {
    const errorElement = document.getElementById("profile-error");
    errorElement.textContent = message;
    errorElement.hidden = false;
}

function clearProfileMessages() {
    const errorElement = document.getElementById("profile-error");
    errorElement.textContent = "";
    errorElement.hidden = true;
    const successElement = document.getElementById("profile-success");
    successElement.textContent = "";
    successElement.hidden = true;
}

function populateCarSelector(cars) {
    const selector = document.getElementById('car-selector');
    if (!selector) return;

    selector.replaceChildren();

    cars.forEach(car => {
        const option = document.createElement('option');
        option.value = car.id;
        option.textContent = `${car.producer} ${car.model}`.toUpperCase();
        selector.appendChild(option);
    });

    const addOption = document.createElement('option');
    addOption.value = addVehicleOptionValue;
    addOption.textContent = "+ AGGIUNGI NUOVO VEICOLO";
    selector.appendChild(addOption);
}

async function onCarChange(carId) {
    if (!carId) return;
    if (carId === addVehicleOptionValue) {
        document.getElementById('car-selector').value = activeCarId ?? "";
        openCarModal(false);
        return;
    }
    await selectCar(carId);
}

async function selectCar(carId) {
    activeCarId = carId;
    clearAppError();
    await Promise.all([
        loadMaintenanceCategories(carId),
        loadCarDetails(carId),
        loadDashboardData(carId),
        loadMaintenanceHistory(carId),
        loadMileageChart(carId),
    ]);
}

async function loadCarDetails(carId) {
    try {
        const response = await apiFetch(API_ENDPOINTS.cars.byId(carId));
        if (!response.ok) throw new Error(await getApiErrorMessage(response));

        const car = await response.json();
        if (!isActiveCar(carId)) return;
        currentMileage = car.current_mileage;

        const plateElem = document.getElementById('car-plate');
        if (plateElem) plateElem.textContent = car.plate_nr;

        const kmFormatted = numberFormatter.format(car.current_mileage);
        const kmElem = document.getElementById('car-current-km');
        if (kmElem) kmElem.textContent = `${kmFormatted} km`;

    } catch (error) {
        console.error("Errore nel caricamento dettagli veicolo:", error);
        if (isActiveCar(carId)) showAppError(error.message);
    }
}

async function loadDashboardData(carId) {
    try {
        const response = await apiFetch(API_ENDPOINTS.cars.maintenanceStatus(carId));
        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        const data = await response.json();
        if (!isActiveCar(carId)) return;
        renderTables(data);
    } catch (error) {
        console.error("Errore nel recupero dei dati di manutenzione:", error);
        if (isActiveCar(carId)) {
            document.getElementById("global-status-badge").textContent = "ERRORE DI CARICAMENTO";
            showAppError(error.message);
        }
    }
}

async function loadMaintenanceHistory(carId) {
    const tableBody = document.getElementById("history-table-body");
    if (!tableBody) return;

    try {
        const response = await apiFetch(API_ENDPOINTS.cars.maintenanceHistory(carId));
        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        const historyItems = await response.json();
        if (!isActiveCar(carId)) return;

        if (historyItems.length === 0) {
            renderEmptyState(
                tableBody,
                "Nessun intervento registrato nello storico.",
                6,
            );
            return;
        }

        const rows = historyItems.map((item) => {
            const row = document.createElement("tr");
            const costCell = createTableCell("Costo", currencyFormatter.format(item.cost));
            costCell.classList.add("maintenance-cost");
            row.append(
                createTableCell("Manutenzione", item.category.replaceAll("_", " ")),
                createTableCell("Data completamento", item.date),
                createTableCell(
                    "Km effettuati",
                    `${numberFormatter.format(item.mileage)} km`,
                ),
                costCell,
                createTableCell("Note", item.notes ?? "—"),
                createTableCell(
                    "Azione",
                    createDeleteButton(
                        "Elimina",
                        () => deleteMaintenance(item.id),
                        `Elimina l'intervento del ${item.date}`,
                    ),
                ),
            );
            return row;
        });
        replaceTableRows(tableBody, rows);
    } catch (error) {
        console.error("Errore nel recupero dello storico manutenzioni:", error);
        if (isActiveCar(carId)) {
            showAppError(error.message);
            renderEmptyState(tableBody, "Errore di caricamento dello storico.", 6);
        }
    }
}

function renderTables(data) {
    const tableBody = document.getElementById("incoming-table-body");
    const statusBadge = document.getElementById("global-status-badge");
    const statuses = ["overdue", "due_soon", "up_to_date"];

    const items = statuses.flatMap((status) =>
        (data[status] ?? []).map((item) => ({ ...item, status })),
    );

    if (items.length === 0) {
        renderEmptyState(tableBody, "Nessuna manutenzione programmata.", 4);
    } else {
        const rows = items.map((item) => {
            const row = document.createElement("tr");
            const statusTag = document.createElement("span");
            statusTag.classList.add(
                "tag",
                item.status === "overdue"
                    ? "tag-expired"
                    : item.status === "due_soon"
                        ? "tag-incoming"
                        : "tag-done",
            );
            statusTag.textContent = statusLabels[item.status];
            row.append(
                createTableCell("Manutenzione", item.category.replaceAll("_", " ")),
                createTableCell("Scadenza", formatRemainingTime(item)),
                createTableCell("Note", item.description ?? "—"),
                createTableCell("Stato", statusTag),
            );
            return row;
        });
        replaceTableRows(tableBody, rows);
    }

    statusBadge.textContent = data.overdue?.length
        ? "MANUTENZIONI SCADUTE"
        : data.due_soon?.length
            ? "MANUTENZIONI IN ARRIVO"
            : "TUTTO REGOLARE";
}

function formatRemainingTime(item) {
    const remaining = [];

    if (item.km_left !== null) {
        const kilometers = wholeNumberFormatter.format(item.km_left);
        remaining.push(`${kilometers} km`);
    }
    if (item.months_left !== null) {
        remaining.push(`${item.months_left} mesi`);
    }

    return remaining.length > 0 ? remaining.join(" / ") : "—";
}

function toggleDefaultRecInputs(checkbox) {
    const row = checkbox.closest('.default-rec-item');
    if (!row) return;
    const inputs = row.querySelectorAll('input:not([type="checkbox"])');
    inputs.forEach(input => {
        input.disabled = !checkbox.checked;
    });
}

function addCustomRecommendationRow() {
    const container = document.getElementById('custom-recs-container');

    const row = document.createElement("div");
    row.className = "custom-rec-row";

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.placeholder = "Nome (es. cinghia)";
    nameInput.className = "custom-rec-name";
    nameInput.required = true;

    const kilometersInput = document.createElement("input");
    kilometersInput.type = "number";
    kilometersInput.placeholder = "Km max";
    kilometersInput.className = "custom-rec-km";
    kilometersInput.min = "0";

    const monthsInput = document.createElement("input");
    monthsInput.type = "number";
    monthsInput.placeholder = "Mesi";
    monthsInput.className = "custom-rec-months";
    monthsInput.min = "0";

    const removeButton = createDeleteButton("X", () => row.remove(), "Rimuovi scadenza");
    row.append(nameInput, kilometersInput, monthsInput, removeButton);
    container.appendChild(row);
}

const carForm = document.getElementById('car-form');
if (carForm) {
    carForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const payload = {
            producer: document.getElementById('producer').value,
            model: document.getElementById('model').value,
            plate_nr: document.getElementById('plate_nr').value,
            vin: document.getElementById('vin').value,
            first_registration: document.getElementById('first_registration').value
        };

        const initialMileage = parseFloat(document.getElementById('initial_mileage').value);

        try {
            const response = await apiFetch(API_ENDPOINTS.cars.collection(initialMileage), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(await getApiErrorMessage(response));

            const createdCar = await response.json();
            const newCarId = createdCar.id;

            let recommendationsPayload = [];

            const defaultItems = document.querySelectorAll('.default-rec-item');
            defaultItems.forEach(item => {
                const checkbox = item.querySelector('input[name="default_rec_check"]');
                if (checkbox && checkbox.checked) {
                    const category = checkbox.value;
                    const desc = item.querySelector('.default-rec-desc').value.trim();
                    const kmVal = item.querySelector('.default-rec-km').value;
                    const monthsVal = item.querySelector('.default-rec-months').value;

                    recommendationsPayload.push({
                        category: category,
                        description: desc || `Manutenzione periodica: ${category.replaceAll("_", " ")}`,
                        target_mileage: kmVal ? parseFloat(kmVal) : null,
                        target_months: monthsVal ? parseInt(monthsVal) : null
                    });
                }
            });

            const customRows = document.querySelectorAll('.custom-rec-row');
            customRows.forEach(row => {
                const nameInput = row.querySelector('.custom-rec-name').value.trim();
                if (nameInput) {
                    const formattedCategory = nameInput.toLowerCase().replaceAll(" ", "_");
                    const kmVal = row.querySelector('.custom-rec-km').value;
                    const monthsVal = row.querySelector('.custom-rec-months').value;

                    recommendationsPayload.push({
                        category: formattedCategory,
                        description: `Personalizzata: ${nameInput}`,
                        target_mileage: kmVal ? parseFloat(kmVal) : null,
                        target_months: monthsVal ? parseInt(monthsVal) : null
                    });
                }
            });

            if (recommendationsPayload.length > 0) {
                const recommendationsResponse = await apiFetch(
                    API_ENDPOINTS.cars.recommendationsBatch(newCarId),
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(recommendationsPayload),
                    },
                );
                if (!recommendationsResponse.ok) {
                    throw new Error(
                        await getApiErrorMessage(recommendationsResponse),
                    );
                }
            }

            carForm.reset();
            document.getElementById('custom-recs-container').replaceChildren();
            closeCarModal();
            await checkGarageStatus(newCarId);

        } catch (error) {
            console.error("Errore durante la configurazione iniziale del veicolo:", error);
            showAppError(error.message);
        }
    });
}

async function deleteActiveCar() {
    if (!activeCarId) return;
    if (!confirm("Sei sicuro di voler eliminare questo veicolo e tutti i dati associati (interventi e chilometri)?")) {
        return;
    }

    try {
        const response = await apiFetch(API_ENDPOINTS.cars.byId(activeCarId), {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        await checkGarageStatus();
    } catch (error) {
        console.error("Errore durante l'eliminazione del veicolo:", error);
        showAppError(error.message);
    }
}

async function deleteMaintenance(maintenanceId) {
    if (!confirm("Sei sicuro di voler eliminare questo intervento dallo storico?")) {
        return;
    }

    try {
        const response = await apiFetch(API_ENDPOINTS.maintenance.byId(maintenanceId), {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        if (activeCarId) {
            await selectCar(activeCarId);
        }
    } catch (error) {
        console.error("Errore durante l'eliminazione dell'intervento:", error);
        showAppError(error.message);
    }
}

async function deleteMileage(mileageId) {
    if (!confirm("Sei sicuro di voler eliminare questa registrazione del chilometraggio?")) {
        return;
    }

    try {
        const response = await apiFetch(API_ENDPOINTS.mileage.byId(mileageId), {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        if (activeCarId) {
            await selectCar(activeCarId);
        }
    } catch (error) {
        console.error("Errore durante l'eliminazione del chilometraggio:", error);
        showAppError(error.message);
    }
}

function openCarModal(isFirstVehicle) {
    document.getElementById('car-modal-title').textContent = isFirstVehicle
        ? "Benvenuto! Registra il tuo primo veicolo"
        : "Aggiungi un nuovo veicolo";
    document.getElementById('cancel-car-button').hidden = isFirstVehicle;
    document.getElementById('car-modal').style.display = 'flex';
}

function closeCarModal() {
    document.getElementById('car-modal').style.display = 'none';
    carForm.reset();
    document.getElementById('custom-recs-container').replaceChildren();
}

function openModal() {
    clearMaintenanceFormError();
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
    clearMaintenanceFormError();
}

function openMileageModal() {
    const now = new Date();
    const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 10);
    document.getElementById('current-mileage-input').value = currentMileage;
    document.getElementById('current-mileage-date').value = localDate;
    document.getElementById('mileage-form-error').hidden = true;
    document.getElementById('mileage-modal').style.display = 'flex';
    document.getElementById('current-mileage-input').focus();
}

function closeMileageModal() {
    document.getElementById('mileage-modal').style.display = 'none';
    document.getElementById('mileage-form-error').hidden = true;
    document.getElementById('km-display').focus();
}

async function loadMaintenanceCategories(carId) {
    const selectElement = document.getElementById("maintenance-category-select");
    if (!selectElement) return;

    selectElement.disabled = true;
    selectElement.replaceChildren(new Option("-- Caricamento categorie... --", ""));

    try {
        const response = await apiFetch(API_ENDPOINTS.cars.maintenanceCategories(carId), {
            method: "POST",
        });
        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        const categories = await response.json();
        if (!isActiveCar(carId)) return;
        selectElement.replaceChildren(new Option("-- Seleziona intervento --", "", true, true));
        selectElement.options[0].disabled = true;

        for (const item of categories) {
            const option = new Option(
                item.category.replaceAll("_", " "),
                item.category,
            );
            option.dataset.custom = String(item.is_custom);
            selectElement.add(option);
        }

        const customOption = new Option(
            "Altro (Personalizzata)",
            "altro-personalizzata",
        );
        customOption.dataset.custom = "true";
        selectElement.add(customOption);
        selectElement.disabled = false;
    } catch (error) {
        console.error("Errore nel caricamento delle categorie manutenzione:", error);
        if (isActiveCar(carId)) {
            showAppError(error.message);
            selectElement.replaceChildren(
                new Option("-- Errore nel caricamento delle categorie --", ""),
            );
        }
    }
}

function handleCategoryChange(selectedValue) {
    const customGroup = document.getElementById('custom-category-group');
    const customInput = document.getElementById('custom_category');

    const isCustomCategory = selectedValue === 'altro-personalizzata';
    customGroup.hidden = !isCustomCategory;
    customInput.required = isCustomCategory;
    if (!isCustomCategory) {
        customInput.value = '';
    }
}

const maintenanceForm = document.getElementById('maintenance-form');
if (maintenanceForm) {
    for (const fieldId of ['mileage', 'date']) {
        document.getElementById(fieldId).addEventListener('input', clearMaintenanceFormError);
        document.getElementById(fieldId).addEventListener('change', clearMaintenanceFormError);
    }

    maintenanceForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        clearMaintenanceFormError();

        const carSelector = document.getElementById('car-selector');
        const activeCarId = carSelector ? carSelector.value : null;

        if (!activeCarId) {
            alert("Seleziona prima un veicolo.");
            return;
        }

        const selectElement = document.getElementById('maintenance-category-select');
        let categoryValue = selectElement.value;
        if (categoryValue === 'altro-personalizzata') {
            categoryValue = document.getElementById('custom_category').value.trim().toLowerCase().replaceAll(" ", "_");
        }

        const payload = {
            category: categoryValue,
            cost: parseFloat(document.getElementById('cost').value),
            mileage: parseFloat(document.getElementById('mileage').value),
            date: document.getElementById('date').value,
            notes: document.getElementById('notes').value || null
        };

        try {
            const response = await apiFetch(API_ENDPOINTS.cars.maintenance(activeCarId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                closeModal();
                maintenanceForm.reset();
                document.getElementById('custom-category-group').hidden = true;
                await selectCar(activeCarId);
            } else {
                showMaintenanceFormError(await getApiErrorMessage(response));
            }
        } catch (error) {
            console.error("Errore di rete:", error);
            showMaintenanceFormError(error.message);
        }
    });
}

const mileageForm = document.getElementById('mileage-form');
if (mileageForm) {
    mileageForm.addEventListener('submit', async function (event) {
        event.preventDefault();

        const saveButton = document.getElementById('save-mileage-button');
        const errorElement = document.getElementById('mileage-form-error');
        saveButton.disabled = true;
        errorElement.hidden = true;

        const payload = {
            mileage: Number(document.getElementById('current-mileage-input').value),
            date: document.getElementById('current-mileage-date').value,
        };

        try {
            const response = await apiFetch(API_ENDPOINTS.cars.mileage(activeCarId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(await getApiErrorMessage(response));
            }

            closeMileageModal();
            mileageForm.reset();
            await selectCar(activeCarId);
        } catch (error) {
            console.error("Errore nell'aggiornamento del chilometraggio:", error);
            errorElement.textContent = error.message;
            errorElement.hidden = false;
        } finally {
            saveButton.disabled = false;
        }
    });
}

let mileageChartInstance = null;

function clearGarageData() {
    activeCarId = null;
    currentMileage = 0;

    document.getElementById("car-selector").replaceChildren();
    document.getElementById("car-plate").textContent = "--";
    document.getElementById("car-current-km").textContent = "-- km";
    document.getElementById("global-status-badge").textContent = "IN ATTESA...";
    renderEmptyState(
        document.getElementById("incoming-table-body"),
        "Nessuna manutenzione programmata.",
        4,
    );
    renderEmptyState(
        document.getElementById("history-table-body"),
        "Nessun intervento registrato nello storico.",
        6,
    );
    renderEmptyState(
        document.getElementById("mileage-table-body"),
        "Nessun chilometraggio registrato.",
        3,
    );

    if (mileageChartInstance) {
        mileageChartInstance.destroy();
        mileageChartInstance = null;
    }
}
let isMileageTableVisible = false;

function toggleMileageView() {
    isMileageTableVisible = !isMileageTableVisible;
    document.getElementById("mileage-chart-view").hidden = isMileageTableVisible;
    document.getElementById("mileage-table-view").hidden = !isMileageTableVisible;

    const toggleButton = document.getElementById("mileage-view-toggle");
    toggleButton.textContent = isMileageTableVisible
        ? "VISIONE GRAFICO"
        : "VISIONE TABULARE";
    toggleButton.setAttribute("aria-pressed", String(isMileageTableVisible));

    if (isMileageTableVisible) {
        syncListScrollLimit(document.getElementById("mileage-table-body"));
    }

    if (!isMileageTableVisible && mileageChartInstance) {
        requestAnimationFrame(() => mileageChartInstance.resize());
    }
}

async function loadMileageChart(carId) {
    const canvasElement = document.getElementById("mileageChart");
    if (!canvasElement) return;

    try {
        const response = await apiFetch(API_ENDPOINTS.cars.mileageHistory(carId));
        if (!response.ok) {
            throw new Error(await getApiErrorMessage(response));
        }

        const mileageItems = await response.json();
        if (!isActiveCar(carId)) return;
        const sortedItems = [...mileageItems].sort((a, b) => new Date(a.date) - new Date(b.date));
        renderMileageTable([...sortedItems].reverse());

        const labels = sortedItems.map(item => item.date);
        const dataValues = sortedItems.map(item => item.mileage);
        const styles = getComputedStyle(document.documentElement);
        const accentGreen = styles.getPropertyValue("--accent-green").trim();
        const accentOrange = styles.getPropertyValue("--accent-orange").trim();
        const textColor = styles.getPropertyValue("--text-dark").trim();
        const chartGridColor = styles.getPropertyValue("--chart-grid").trim() || "rgba(41, 45, 43, 0.15)";
        const fontFamily = getComputedStyle(document.body).fontFamily;
        const chartFont = { family: fontFamily, size: 16 };

        if (mileageChartInstance) {
            mileageChartInstance.destroy();
        }

        mileageChartInstance = new Chart(canvasElement, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Chilometraggio',
                    data: dataValues,
                    borderColor: accentGreen,
                    borderWidth: 3,
                    pointBackgroundColor: accentGreen,
                    pointBorderColor: styles.getPropertyValue("--bg-ivory").trim(),
                    pointHoverBackgroundColor: accentOrange,
                    pointRadius: 5,
                    fill: false,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                font: chartFont,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: styles.getPropertyValue("--border-color").trim(),
                        titleColor: styles.getPropertyValue("--bg-ivory").trim(),
                        bodyColor: styles.getPropertyValue("--bg-ivory").trim(),
                        titleFont: chartFont,
                        bodyFont: chartFont,
                        callbacks: {
                            label: context => `${numberFormatter.format(context.parsed.y)} km`
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor, font: chartFont },
                        grid: { color: chartGridColor },
                        border: { color: textColor }
                    },
                    y: {
                        beginAtZero: false,
                        ticks: {
                            color: textColor,
                            font: chartFont,
                            callback: value => numberFormatter.format(value)
                        },
                        grid: { color: chartGridColor },
                        border: { color: textColor }
                    }
                }
            }
        });

    } catch (error) {
        console.error("Errore nel caricamento del grafico chilometri:", error);
        if (isActiveCar(carId)) showAppError(error.message);
    }
}

function renderMileageTable(mileageItems) {
    const tableBody = document.getElementById("mileage-table-body");
    if (!tableBody) return;

    if (mileageItems.length === 0) {
        renderEmptyState(
            tableBody,
            "Nessuna registrazione di chilometraggio.",
            3,
        );
        return;
    }

    const rows = mileageItems.map((item) => {
        const row = document.createElement("tr");
        row.append(
            createTableCell("Data rilevazione", item.date),
            createTableCell(
                "Chilometraggio",
                `${numberFormatter.format(item.mileage)} km`,
            ),
            createTableCell(
                "Azione",
                createDeleteButton(
                    "Elimina",
                    () => deleteMileage(item.id),
                    `Elimina la registrazione del ${item.date}`,
                ),
            ),
        );
        return row;
    });
    replaceTableRows(tableBody, rows);
}