from datetime import datetime, timezone
"""
def calculation_actual_confidence(llm_confidence: float, rec_tool: str, context: dict, tool_calls_log: list) -> float:
    '''Setup trong so co so'''
    W_llm = 0.4
    W_evidence = 0.3
    W_consensus = 0.3

    # 2. Tinh diem bang chung (Evidence Score)
    c_evidence = 0.0
    if tool_calls_log and len(tool_calls_log) > 0:
        c_evidence = 1.0

    # 3. Dong thuan cam bien (Consensus Score)
    c_consensus = 0.5
    telemetry = context.get("TelemetrySummary", {})
    occupancy = context.get("Occupancy", {}).get("current_count", {})

    if rec_tool in ["set_fan", "send_alert"]:
        temp_latest = telemetry.get("temperature", {}).get("latest", 25.0)
        co2_latest = telemetry.get("co2", {}).get("latest", 400)

        if temp_latest > 29.0 and occupancy > 10:
            c_consensus = 1.0
        elif temp_latest > 35.0 and occupancy == 0 and co2_latest < 500:
            c_consensus = 0.1

    final_confidence = (W_llm*llm_confidence)+(W_evidence*c_evidence)+(W_consensus*c_consensus)

    # 5. Phat du lieu cu
    window_end_str = telemetry.get("window_end")
    if window_end_str:
        try:
            window_end_str = formisowindow_end = datetime.fromisoformat(window_end_str)
            # Nếu bản ghi telemetry cuối cùng đã cũ hơn 5 phút -> Trừ 0.2 điểm
            if (datetime.now(timezone.utc) - window_end).total_seconds() > 300:
                final_confidence -= 0.2
        except ValueError:
            pass
            
    # Đảm bảo điểm nằm trong khoảng 0.0 - 1.0
    return max(0.0, min(1.0, round(final_confidence, 2)))

"""