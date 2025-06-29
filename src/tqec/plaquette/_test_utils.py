from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis


def make_surface_code_plaquette(
    basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    translator: RPNGTranslator = DefaultRPNGTranslator(),
) -> Plaquette:
    b = basis.value.lower()
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    sched = [1, 2, 3, 5] if basis == Basis.X else [1, 4, 3, 5]
    return translator.translate(
        RPNGDescription.from_string(" ".join(f"{r}{b}{s}{m}" for s in sched))
    )
