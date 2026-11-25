import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Единая настройка логов для точек входа (воркер и бот)."""
    logging.basicConfig(level=level, format=LOG_FORMAT)
    # httpx пишет INFO на каждый запрос — для воркера это шум
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)
