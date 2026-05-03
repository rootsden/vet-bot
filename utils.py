# utils.py
from datetime import datetime, timedelta

def get_available_dates():
    """Оставлено для совместимости, не используется в новой версии"""
    available = []
    now = datetime.now()
    for i in range(14):
        date = now + timedelta(days=i)
        if date.weekday() <= 6:
            available.append(date)
    return available