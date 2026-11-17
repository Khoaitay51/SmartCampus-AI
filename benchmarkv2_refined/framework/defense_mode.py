"""
framework/defense_mode.py
-------------------------
Quy ước tách kết quả giữa agent gốc và agent có phòng thủ (app/safety/defense.py).

  --defense none   (mặc định)  ->  models/<model>/<suite>/<run_id>                      (như cũ)
  --defense full                ->  models/<model>/<suite>_def_full/<run_id>_def_full

Hậu tố được gắn cả vào thư mục suite lẫn run_id, nên:
- không bao giờ ghi đè kết quả của agent gốc;
- file chấm trong reports/scored/ (đặt tên theo run_id) cũng không trùng nhau.
"""
from __future__ import annotations

from pathlib import Path

MODES = ("none", "prompt", "guard", "full")


def suffix(mode: str) -> str:
    return "" if mode in (None, "", "none") else f"_def_{mode}"


def run_id(rid: str, mode: str) -> str:
    s = suffix(mode)
    return rid if (not s or rid.endswith(s)) else rid + s


def leaf(path: Path, mode: str) -> Path:
    """Gắn hậu tố vào tên thư mục cuối nếu chưa có (dùng khi người dùng tự truyền --output)."""
    s = suffix(mode)
    path = Path(path)
    return path if (not s or "_def_" in path.name) else path.with_name(path.name + s)


def suite(name: str, mode: str) -> str:
    return name + suffix(mode)


def activate(mode: str) -> None:
    """Bật chế độ phòng thủ cho agent trong tiến trình hiện tại."""
    import os
    from app.config.settings import settings
    if mode not in MODES:
        raise ValueError(f"--defense phải là một trong {MODES}")
    os.environ["AGENT_DEFENSE"] = mode
    settings.AGENT_DEFENSE = mode
