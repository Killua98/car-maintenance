# standard_maintenances.py
from .recommended_maintenance import ModelRecommendedMaintenanceBase

STANDARD_SCHEDULES = {
    "Fiat": {
        "500": [
            ModelRecommendedMaintenanceBase(
                category="lubrificazione_leverismi",
                target_mileage=30000,
                target_months=24,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="regolazione_corsa_leva_freno_stazionamento",
                target_mileage=30000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_pattini_freni_a_disco",
                target_mileage=15000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_cinghia_di_distribuzione",
                target_mileage=120000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_olio_motore_e_filtro_olio",
                target_mileage=15000,
                target_months=12,
                description="Raccomandato selenia ECO2",
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_candele",
                target_mileage=30000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_cartuccia_filtro_aria",
                target_mileage=30000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_filtro_abitacolo",
                target_mileage=30000,
                target_months=12,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="inversione_pneumatici",
                target_mileage=15000,
                target_months=None,
                description=None,
            ),
            ModelRecommendedMaintenanceBase(
                category="sostituzione_pneumatici",
                target_mileage=50000,
                target_months=60,
                description="195/45 R16",
            ),
        ]
    }
}
