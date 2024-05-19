import logging
from datetime import datetime, timezone
from pathlib import Path


DATETIME_FORMAT_PATTERN = '%Y-%m-%d;%H:%M:%S.%f'
LOG_MESSAGE_PATTERN = ('{request_datetime};{request_text};'
                       '{response_datetime};{response_text}')

BASE_DIR = Path().cwd()


def now() -> datetime:
    return datetime.now(timezone.utc)


def configure_logger(name: str) -> logging.Logger:
    """Возвращает логгер, записывающий события в файл `filename`"""

    logging_dir = BASE_DIR.joinpath('logs')
    logging_dir.mkdir(exist_ok=True)
    log_file = logging_dir.joinpath(f'{name}.log')

    handler = logging.FileHandler(log_file, 'w', encoding='utf-8')
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    return logger
