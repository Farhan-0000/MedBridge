from medbridge.api.schemas.enums import ActionEnum

class EmergencyClassifier:
    """
    Deterministic fast-path triage for detecting emergency patterns.
    """
    def __init__(self):
        pass
        
    def classify(self, message: str) -> ActionEnum | None:
        """
        Evaluates message against emergency patterns. Returns ESCALATE or None.
        """
        pass
