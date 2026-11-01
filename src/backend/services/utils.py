from datetime import date


def get_months_difference(start_date: date, end_date: date) -> int:
    """Calcola la differenza in mesi interi tra due date."""
    # Gestiamo l'ordine delle date (assicurando che end_date sia successiva)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    years_diff = end_date.year - start_date.year
    months_diff = end_date.month - start_date.month

    total_months = years_diff * 12 + months_diff

    # Se il giorno del mese non è ancora arrivato, non è completo il mese
    if end_date.day < start_date.day:
        total_months -= 1

    return total_months
