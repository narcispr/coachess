"""Validated options shared by the form and the analysis engine."""
from dataclasses import asdict, dataclass
import math

# name, Catalan label, min, max, step, unit
CONTROLS = (
    ("time_limit", "Temps per cerca", 0.1, 5, 0.1, "s"),
    ("multipv", "Línies candidates (MultiPV)", 1, 10, 1, "línies"),
    ("excellent", "Pèrdua màxima per a una jugada excel·lent", 0, 10, 0.5, "pp"),
    ("inaccuracy", "Imprecisió a partir de", 0.5, 30, 0.5, "pp"),
    ("mistake", "Error a partir de", 1, 50, 0.5, "pp"),
    ("blunder", "Error greu a partir de", 1.5, 75, 0.5, "pp"),
    ("alternative_tolerance", "Distància màxima de les alternatives respecte de la millor", 0, 300, 5, "cp"),
    ("mate_slack", "Marge abans d'avisar d'un mat més lent", 0, 10, 1, "jugades"),
)


@dataclass(frozen=True)
class AnalysisSettings:
    time_limit: float = 0.5
    multipv: int = 3
    excellent: float = 1
    inaccuracy: float = 5
    mistake: float = 10
    blunder: float = 15
    alternative_tolerance: int = 50
    mate_slack: int = 2

    def __post_init__(self):
        for name, label, minimum, maximum, _, _ in CONTROLS:
            value = getattr(self, name)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{label}: el valor ha d'estar entre {minimum} i {maximum}.")
            if name in ("multipv", "alternative_tolerance", "mate_slack") and int(value) != value:
                raise ValueError(f"{label}: cal un nombre enter.")
        if not self.excellent < self.inaccuracy < self.mistake < self.blunder:
            raise ValueError("Els llindars han de complir: excel·lent < imprecisió < error < error greu.")

    @classmethod
    def from_form(cls, form):
        values = asdict(cls())
        for name, label, *_ in CONTROLS:
            try:
                value = float(form.get(name, values[name]))
            except (ValueError, TypeError):
                raise ValueError(f"{label}: introdueix un valor numèric.") from None
            values[name] = value
        settings = cls(**values)
        return cls(**{
            name: int(value) if name in ("multipv", "alternative_tolerance", "mate_slack") else value
            for name, value in asdict(settings).items()
        })
