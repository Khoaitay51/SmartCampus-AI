import asyncio
import asyncpg
import random
import uuid
from datetime import datetime, timedelta, timezone

ROOMS = [
    {"id": "0c5bc15f-d2ef-4450-b7f3-b0d0a2dc726d", "name": "Room A101", "type": "CLASSROOM"},
    {"id": "b669e4b5-a922-45fa-997c-546d539c1b4a", "name": "Room A102", "type": "CLASSROOM"}
]

async def seed_edge_database():
    conn = await asyncpg.connect('postgresql://smartcampus:change-this-local-password@localhost:5433/smartcampus')
    
    print("Ensuring rooms exist in Edge DB...")
    for room in ROOMS:
        try:
            await conn.execute("""
                INSERT INTO room (room_id, room_name, room_type) 
                VALUES ($1, $2, $3)
                ON CONFLICT (room_id) DO NOTHING;
            """, room["id"], room["name"], room["type"])
        except Exception as e:
            print(f"Error creating room {room['name']}: {e}")

    # Delete old records
    await conn.execute("DELETE FROM environment WHERE room_id = '0c5bc15f-d2ef-4450-b7f3-b0d0a2dc726d' OR room_id = 'b669e4b5-a922-45fa-997c-546d539c1b4a';")
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=1)
    
    print(f"Start seeding from {start_time.strftime('%H:%M:%S')} to {now.strftime('%H:%M:%S')}...")
    
    current_time = start_time
    count = 0
    while current_time <= now:
        for room in ROOMS:
            temp = round(random.uniform(24.5, 26.5), 1)
            humidity = round(random.uniform(55.0, 62.0), 1)
            co2 = int(random.uniform(400, 600))
            
            # Biến cố A101 ở 5 phút cuối
            if room["id"] == "0c5bc15f-d2ef-4450-b7f3-b0d0a2dc726d" and (now - current_time).total_seconds() <= 300:
                co2 = int(random.uniform(1500, 5000))
                temp = round(random.uniform(30.0, 45.0), 1) 
                
            await conn.execute("""
                INSERT INTO environment 
                (room_id, temperature, humidity, smoke_detected, smoke_value, smoke_threshold, smoke_state, co2, air_quality, room_mode, message_id, source_timestamp, gateway_received_timestamp, environment_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, 'NORMAL', $7, $8, 'LECTURE', $9, $10, $10, $10)
            """, 
            room["id"], temp, humidity, False, random.uniform(5, 15), 400.0, co2, int(random.uniform(80, 100)), 
            str(uuid.uuid4()), current_time)
            
            count += 1
            
        current_time += timedelta(minutes=1)
        
    print(f"Successfully inserted {count} records into Edge DB.")
    
    print("\n--- 5 NEWEST RECORDS FOR ROOM A101 (With CO2 hazard) ---")
    telemetry = await conn.fetch("SELECT environment_timestamp, temperature, humidity, co2 FROM environment WHERE room_id = '0c5bc15f-d2ef-4450-b7f3-b0d0a2dc726d' ORDER BY environment_timestamp DESC LIMIT 5;")
    for row in telemetry:
        ts = row['environment_timestamp'].strftime('%H:%M:%S')
        print(f"[{ts}] Temp: {row['temperature']}C | Hum: {row['humidity']}% | CO2: {row['co2']}ppm")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_edge_database())
