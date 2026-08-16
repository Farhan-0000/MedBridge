import logging
import sys
import structlog
from structlog.contextvars import merge_contextvars, bind_contextvars, clear_contextvars

SENSITIVE_KEYS = {"api_key", "authorization", "password", "groq_api_key", "openai_api_key", "postgres_password"}

def mask_sensitive_data(logger, method_name, event_dict):
    """
    Processor to mask sensitive fields in the log event dictionary.
    """
    for key, value in event_dict.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "***MASKED***"
    return event_dict

def configure_logging(json_format: bool = True, log_level: int = logging.INFO):
    """
    Configure structlog and standard logging.
    If json_format is True, outputs structured JSON.
    Otherwise outputs colored console logging.
    """
    
    shared_processors = [
        merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        mask_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_format:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=shared_processors,
        )
        
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
