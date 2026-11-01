const API_BASE_URL = "/api/v1";
const API_ENDPOINTS = Object.freeze({
    auth: Object.freeze({
        checkSetup: () => `${API_BASE_URL}/users/check-setup`,
        setupSuperuser: () => `${API_BASE_URL}/users/setup-superuser`,
        signup: () => `${API_BASE_URL}/users/signup`,
        login: () => `${API_BASE_URL}/login/access-token`,
    }),
    users: Object.freeze({
        me: () => `${API_BASE_URL}/users/me`,
        updateMe: () => `${API_BASE_URL}/users/me`,
        updateMyPassword: () => `${API_BASE_URL}/users/me/password`,
        collection: () => `${API_BASE_URL}/users/`,
        statistics: () => `${API_BASE_URL}/users/statistics`,
        byId: (userId) => `${API_BASE_URL}/users/${encodeURIComponent(userId)}`,
    }),
    cars: Object.freeze({
        collection: (initialMileage) => {
            const url = `${API_BASE_URL}/cars/`;
            if (initialMileage === undefined || initialMileage === null) return url;

            const params = new URLSearchParams({ initial_mileage: initialMileage });
            return `${url}?${params}`;
        },
        byId: (carId) => `${API_BASE_URL}/cars/${encodeURIComponent(carId)}`,
        maintenanceStatus: (carId) => {
            const params = new URLSearchParams({ car_id: String(carId) });
            return `${API_BASE_URL}/cars/maintenance-status?${params}`;
        },
        maintenanceHistory: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/maintenance-history`,
        maintenanceCategories: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/maintenance-categories`,
        maintenance: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/maintenance`,
        mileageHistory: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/mileage-history`,
        mileage: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/mileage`,
        recommendationsBatch: (carId) =>
            `${API_BASE_URL}/cars/${encodeURIComponent(carId)}/recommendations/batch`,
    }),
    maintenance: Object.freeze({
        byId: (maintenanceId) =>
            `${API_BASE_URL}/maintenance/${encodeURIComponent(maintenanceId)}`,
    }),
    mileage: Object.freeze({
        byId: (mileageId) =>
            `${API_BASE_URL}/mileage/${encodeURIComponent(mileageId)}`,
    }),
});
