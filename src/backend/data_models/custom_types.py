# custom_types.py
from datetime import date, datetime
from typing import Annotated

from pydantic import BeforeValidator


def parse_car_date(v: str | date) -> date:
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return datetime.strptime(v, "%d-%m-%Y").date()
    return v


DataItaliana = Annotated[date, BeforeValidator(parse_car_date)]
