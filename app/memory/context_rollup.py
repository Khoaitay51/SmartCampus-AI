"""
app/memory/context_rollup.py
----------------------------
Background service định kỳ tóm tắt và sinh embedding cho Contextual Memory:
- Gom các log 'hourly' (từ Edge) ➔ Tóm tắt 'daily' (mỗi 1 ngày)
- Gom các log 'daily' ➔ Tóm tắt 'weekly' (mỗi 1 tuần)

Sử dụng `asyncio.to_thread` để đẩy tác vụ tính toán / tóm tắt văn bản ra worker thread,
tránh làm nghẽn Event Loop chính của FastAPI.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ContextualMemoryLog
from app.database.session import async_session
from app.gateway.embeddings import get_embedding

logger = logging.getLogger("agent.memory.rollup")


def sync_summarize_telemetry_records(
    room_id: str,
    period: str,
    start_time: datetime,
    end_time: datetime,
    records: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """
    Hàm tính toán / tóm tắt văn bản chạy đồng bộ (CPU-bound).
    Được gọi qua `asyncio.to_thread` để giải phóng Event Loop.
    """
    if not records:
        text = f"Phòng {room_id} trong kỳ {period} ({start_time.strftime('%Y-%m-%d')} đến {end_time.strftime('%Y-%m-%d')}): Không có dữ liệu ghi nhận."
        return text, {}

    temps = [r.get("metrics_data", {}).get("temperature") for r in records if r.get("metrics_data", {}).get("temperature") is not None]
    co2s = [r.get("metrics_data", {}).get("co2") for r in records if r.get("metrics_data", {}).get("co2") is not None]
    smokes = [r.get("metrics_data", {}).get("smoke_value") for r in records if r.get("metrics_data", {}).get("smoke_value") is not None]
    humidities = [r.get("metrics_data", {}).get("humidity") for r in records if r.get("metrics_data", {}).get("humidity") is not None]

    avg_temp = round(sum(temps) / len(temps), 1) if temps else 0.0
    min_temp = round(min(temps), 1) if temps else 0.0
    max_temp = round(max(temps), 1) if temps else 0.0

    avg_co2 = round(sum(co2s) / len(co2s), 0) if co2s else 0.0
    max_co2 = round(max(co2s), 0) if co2s else 0.0

    avg_humidity = round(sum(humidities) / len(humidities), 0) if humidities else 0.0
    max_smoke = round(max(smokes), 1) if smokes else 0.0

    period_str = "HÀNG NGÀY (24H)" if period == "daily" else "HÀNG TUẦN (7D)"
    date_range = f"{start_time.strftime('%Y-%m-%d %H:%M')} đến {end_time.strftime('%Y-%m-%d %H:%M')}"

    summary_text = (
        f"Tóm tắt ngữ cảnh {period_str} phòng {room_id} từ {date_range} (tổng hợp từ {len(records)} bản ghi): "
        f"Nhiệt độ dao động {min_temp}°C - {max_temp}°C (trung bình {avg_temp}°C), "
        f"Độ ẩm trung bình {avg_humidity}%, "
        f"Nồng độ CO2 trung bình {avg_co2:.0f}ppm (đỉnh {max_co2:.0f}ppm), "
        f"Chỉ số khói tối đa ghi nhận {max_smoke}."
    )

    notes: list[str] = []
    if max_temp >= 32.0:
        notes.append("Ghi nhận thời điểm quá nhiệt cần lưu ý điều hòa.")
    if avg_co2 >= 1000.0:
        notes.append("Không khí trong phòng có xu hướng bí khí kéo dài.")
    if max_smoke >= 50.0:
        notes.append("Có sự kiện khói bất thường chạm ngưỡng cảnh báo.")

    if notes:
        summary_text += " Đánh giá bất thường: " + " ".join(notes)
    else:
        summary_text += " Môi trường phòng vận hành ổn định trong kỳ."

    metrics_data = {
        "samples_count": len(records),
        "temperature": {"avg": avg_temp, "min": min_temp, "max": max_temp},
        "co2": {"avg": avg_co2, "max": max_co2},
        "humidity": {"avg": avg_humidity},
        "smoke": {"max": max_smoke},
        "anomalies_detected": len(notes) > 0,
    }

    return summary_text, metrics_data


async def process_daily_rollup(reference_time: datetime | None = None) -> int:
    """Gom nhóm các bản ghi hourly trong 24 giờ qua của từng phòng ➔ Tạo bản ghi daily."""
    now = reference_time or datetime.now(timezone.utc)
    start_time = now - timedelta(days=1)
    end_time = now

    async with async_session() as session:
        # Lấy danh sách room_id có hourly log trong 24h qua
        stmt_rooms = (
            select(ContextualMemoryLog.room_id)
            .where(
                and_(
                    ContextualMemoryLog.period == "hourly",
                    ContextualMemoryLog.start_time >= start_time,
                    ContextualMemoryLog.end_time <= end_time,
                )
            )
            .distinct()
        )
        res_rooms = await session.execute(stmt_rooms)
        room_ids = [r[0] for r in res_rooms.fetchall()]

        if not room_ids:
            return 0

        inserted_count = 0
        for room_id in room_ids:
            # Lấy toàn bộ bản ghi hourly của phòng
            stmt_logs = (
                select(ContextualMemoryLog)
                .where(
                    and_(
                        ContextualMemoryLog.room_id == room_id,
                        ContextualMemoryLog.period == "hourly",
                        ContextualMemoryLog.start_time >= start_time,
                        ContextualMemoryLog.end_time <= end_time,
                    )
                )
                .order_by(ContextualMemoryLog.start_time.asc())
            )
            logs_res = await session.execute(stmt_logs)
            records = [
                {
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "summary_text": r.summary_text,
                    "metrics_data": r.metrics_data or {},
                }
                for r in logs_res.scalars().all()
            ]

            if not records:
                continue

            # Đẩy tác vụ tóm tắt ra ngoài thread pool để không block asyncio loop
            summary_text, metrics_data = await asyncio.to_thread(
                sync_summarize_telemetry_records,
                room_id,
                "daily",
                start_time,
                end_time,
                records,
            )

            # Sinh vector embedding
            embedding = await get_embedding(summary_text)

            daily_log = ContextualMemoryLog(
                id=str(uuid.uuid4()),
                room_id=room_id,
                period="daily",
                start_time=start_time,
                end_time=end_time,
                summary_text=summary_text,
                metrics_data=metrics_data,
                embedding=embedding,
            )
            session.add(daily_log)
            inserted_count += 1

        await session.commit()
        logger.info("Đã hoàn tất Daily Rollup: tạo %d bản ghi tóm tắt ngày.", inserted_count)
        return inserted_count


async def process_weekly_rollup(reference_time: datetime | None = None) -> int:
    """Gom nhóm các bản ghi daily trong 7 ngày qua của từng phòng ➔ Tạo bản ghi weekly."""
    now = reference_time or datetime.now(timezone.utc)
    start_time = now - timedelta(days=7)
    end_time = now

    async with async_session() as session:
        stmt_rooms = (
            select(ContextualMemoryLog.room_id)
            .where(
                and_(
                    ContextualMemoryLog.period == "daily",
                    ContextualMemoryLog.start_time >= start_time,
                    ContextualMemoryLog.end_time <= end_time,
                )
            )
            .distinct()
        )
        res_rooms = await session.execute(stmt_rooms)
        room_ids = [r[0] for r in res_rooms.fetchall()]

        if not room_ids:
            return 0

        inserted_count = 0
        for room_id in room_ids:
            stmt_logs = (
                select(ContextualMemoryLog)
                .where(
                    and_(
                        ContextualMemoryLog.room_id == room_id,
                        ContextualMemoryLog.period == "daily",
                        ContextualMemoryLog.start_time >= start_time,
                        ContextualMemoryLog.end_time <= end_time,
                    )
                )
                .order_by(ContextualMemoryLog.start_time.asc())
            )
            logs_res = await session.execute(stmt_logs)
            records = [
                {
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "summary_text": r.summary_text,
                    "metrics_data": r.metrics_data or {},
                }
                for r in logs_res.scalars().all()
            ]

            if not records:
                continue

            summary_text, metrics_data = await asyncio.to_thread(
                sync_summarize_telemetry_records,
                room_id,
                "weekly",
                start_time,
                end_time,
                records,
            )

            embedding = await get_embedding(summary_text)

            weekly_log = ContextualMemoryLog(
                id=str(uuid.uuid4()),
                room_id=room_id,
                period="weekly",
                start_time=start_time,
                end_time=end_time,
                summary_text=summary_text,
                metrics_data=metrics_data,
                embedding=embedding,
            )
            session.add(weekly_log)
            inserted_count += 1

        await session.commit()
        logger.info("Đã hoàn tất Weekly Rollup: tạo %d bản ghi tóm tắt tuần.", inserted_count)
        return inserted_count


async def fetch_and_store_hourly_from_edge(client: Any | None = None) -> int:
    """Kéo các bản ghi RawSummarizer 1-giờ từ Edge Gateway (/tool/reasoning/summaries) về lưu vào DB."""
    try:
        from app.gateway.client import GatewayClient
        from app.gateway.rooms import RoomsClient
        import json

        gw_client = client or GatewayClient()
        rooms = RoomsClient(gw_client)
        summaries = await rooms.get_raw_summaries(limit=50)
    except Exception as exc:
        logger.debug("Chưa kết nối được Edge để lấy summaries: %s", exc)
        return 0

    if not summaries or not isinstance(summaries, list):
        return 0

    inserted_count = 0
    async with async_session() as session:
        for item in summaries:
            raw_id = str(item.get("raw_summarizer_id") or "")
            summary_text = item.get("summary") or ""
            raw_data_str = item.get("raw_data") or "{}"
            raw_data = json.loads(raw_data_str) if isinstance(raw_data_str, str) else (raw_data_str or {})
            room_id = str(raw_data.get("room_id") or item.get("room_id") or "unknown_room")

            ts_str = item.get("raw_summarizer_timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.now(timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            # Tránh lưu trùng lặp
            stmt_check = select(ContextualMemoryLog.id).where(
                and_(
                    ContextualMemoryLog.room_id == room_id,
                    ContextualMemoryLog.period == "hourly",
                    ContextualMemoryLog.start_time == ts - timedelta(hours=1),
                )
            )
            exists = (await session.execute(stmt_check)).scalar_one_or_none()
            if exists:
                continue

            embedding = await get_embedding(summary_text)

            log_entry = ContextualMemoryLog(
                id=raw_id or str(uuid.uuid4()),
                room_id=room_id,
                period="hourly",
                start_time=ts - timedelta(hours=1),
                end_time=ts,
                summary_text=summary_text,
                metrics_data=raw_data,
                embedding=embedding,
            )
            session.add(log_entry)
            inserted_count += 1

        if inserted_count > 0:
            await session.commit()
            logger.info("Đã đồng bộ %d bản ghi hourly summary từ Edge Gateway vào contextual memory.", inserted_count)

    return inserted_count


async def memory_rollup_worker(check_interval_seconds: int = 3600) -> None:
    """Background task chạy định kỳ theo check_interval_seconds (mặc định 1h)."""
    logger.info("Contextual Memory Rollup Worker đã khởi động (interval=%ds)", check_interval_seconds)
    while True:
        try:
            # 1. Kéo các summary 1h mới nhất từ Edge
            await fetch_and_store_hourly_from_edge()
            # 2. Tóm tắt rollup ngày & tuần
            await process_daily_rollup()
            await process_weekly_rollup()
        except asyncio.CancelledError:
            logger.info("Contextual Memory Rollup Worker đang dừng...")
            break
        except Exception as e:
            logger.error("Lỗi trong vòng lặp Contextual Memory Rollup: %s", e)

        try:
            await asyncio.sleep(check_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Contextual Memory Rollup Worker nhận tín hiệu dừng.")
            break

