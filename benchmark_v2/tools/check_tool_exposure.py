import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.config.settings import settings
from app.tools.registry import RAG_TOOLS, render_tool_desc

settings.BENCHMARK_MODE = False
off = render_tool_desc(RAG_TOOLS)
settings.BENCHMARK_MODE = True
on = render_tool_desc(RAG_TOOLS)
for name in ("read_room_notes", "read_access_log", "http_post", "send_webhook", "send_email"):
    print(name, "| OFF:", name in off, "| ON:", name in on)
