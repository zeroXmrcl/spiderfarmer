class SpiderFarmerError(Exception):
    """API, crypto, or transport failure. ``code`` is the envelope code or ``http`` / ``decrypt`` / ``write``."""

    def __init__(self, code: str, msg: str) -> None:
        self.code = code
        self.msg = msg
        super().__init__(f"{code} {msg}")
