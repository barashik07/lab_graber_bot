import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

def current_semester() -> str:
    """Определение текущего семестра"""
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    y, m = now.year, now.month
    if 2 <= m <= 7:
        semester = f"Spring {y}"
    elif m == 1:
        semester = f"Fall {y-1}"
    else:
        semester = f"Fall {y}"
    
    logger.debug(f"Current semester determined: {semester}")
    return semester