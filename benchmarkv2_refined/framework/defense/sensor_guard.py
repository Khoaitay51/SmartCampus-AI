"""
framework/defense/sensor_guard.py
---------------------------------
Shim: mã nguồn duy nhất của SensorGuard nằm ở app/safety/sensor_guard.py (dùng chung cho agent thật
và cho mô phỏng offline simulate_defense.py). File này chỉ re-export để mô phỏng và agent luôn khớp nhau.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # thư mục AI + Backend
from app.safety.sensor_guard import *          # noqa: E402,F401,F403
from app.safety.sensor_guard import ACTION_TOOLS, ALERT_OK, apply, hazards, read_sensors  # noqa: E402,F401
