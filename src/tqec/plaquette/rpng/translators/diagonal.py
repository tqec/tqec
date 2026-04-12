from tqec.plaquette.rpng.translators.scheduled import ScheduledRPNGTranslator


class DiagonalRPNGTranslator(ScheduledRPNGTranslator):
    """Translator for diagonal-schedule plaquettes."""

    MEASUREMENT_SCHEDULE = 7
