import logging
import re

# Query parameters that carry a secret, e.g. `api_key=...` (OpenAlex, Springer).
_SECRET_PARAM = re.compile(r"(\b(?:api_?key)=)[^&\s\"']+", re.IGNORECASE)


def redact(text: str) -> str:
    """Masks the values of API key query parameters in `text`."""
    return _SECRET_PARAM.sub(r"\1***", text)


class RedactSecretsFilter(logging.Filter):
    """Masks API keys in log records, e.g. the request URLs httpx logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def install() -> None:
    """Adds the filter to the loggers that log outgoing request URLs."""
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).addFilter(RedactSecretsFilter())
