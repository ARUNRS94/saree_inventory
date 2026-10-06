from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Pydantic renders Decimal as a JSON string, which silently turns UI arithmetic
# (totals, sums) into string concatenation. Responses emit plain numbers instead.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
