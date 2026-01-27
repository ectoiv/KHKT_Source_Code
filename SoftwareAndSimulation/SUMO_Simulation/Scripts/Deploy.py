#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import os
import sys
import csv
import json
import requests
import threading          # <--- [NEW] Để chạy đa luồng
import queue              # <--- [NEW] Để nhận kết quả từ luồng con
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

# =========================
# ======== CONFIG =========
# =========================

SERVER_URL = "http://localhost:5000"

# --- SUMO & mô phỏng ---
SUMO_BINARY       = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo-gui.exe"
SUMO_CONFIG       = r"D:\CODE\AI\Traffic\Traffic_MPC\SUMO\osm.sumocfg"
TLS_ID            = "6453053474"
SIM_STEP_LENGTH_S = 1.0
SIM_DURATION_S    = 720000

# --- Cấu hình Trigger AI ---
# Thời điểm kích hoạt AI sớm hơn thời điểm kết thúc chu kỳ (giây)
AI_PRE_CALC_OFFSET_S = 5.0 

AI_START_DELAY_S   = 20000

YELLOW_EW_S = 5.0
YELLOW_NS_S = 5.0

PHASE_INDEX = {
    "EW_G": 0, "EW_Y": 1,
    "NS_G": 2, "NS_Y": 3,
}

# --- I/O thư mục ---
IO_BASE_DIR_D = Path(r"D:\CODE\AI\Traffic\Simulation\INPUTDATA")
IO_BASE_DIR   = Path(r"D:\CODE\AI\Traffic\Simulation\script")

ZONE_CSV_PATHS = {
    "zone1": IO_BASE_DIR_D / "zone1.csv",
    "zone2": IO_BASE_DIR_D / "zone2.csv",
    "zone3": IO_BASE_DIR_D / "zone3.csv",
    "zone4": IO_BASE_DIR_D / "zone4.csv",
}

ZONE_LANES = {
    "zone1": ["1306985992#1_0"],
    "zone2": ["688234464#2_0"],
    "zone3": ["-261177827#0_0", "-261177827#1_0"],
    "zone4": ["-954599013#0_0"],
}

AI_WORK_DIR        = IO_BASE_DIR
SIGNAL_JSON_PATH   = IO_BASE_DIR / "signal.json"

# __now = datetime.now()
# START_DATETIME = __now.replace(hour=0, minute=0, second=0, microsecond=0)
START_DATETIME = datetime(2026, 1, 22, 0, 0, 0)
CLEAR_OLD_OUTPUT = True

# Biến toàn cục để giao tiếp giữa Thread và Main
ai_result_queue = queue.Queue()
is_ai_running = False  # Cờ đánh dấu AI đang chạy hay chưa

# =========================
# ====== IMPORT TRACI =====
# =========================
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)
try:
    import traci
except ImportError as e:
    raise ImportError("Không import được 'traci'.") from e

# =========================
# ====== HELPER FUNCTIONS =
# =========================

def report_status_to_server(is_red: bool):
    try:
        requests.post(f"{SERVER_URL}/api/sumo_status", json={"Red": is_red}, timeout=0.05)
    except: pass

def clear_old_outputs():
    if not CLEAR_OLD_OUTPUT: return
    for p in ZONE_CSV_PATHS.values():
        if p.exists(): p.unlink()
    if SIGNAL_JSON_PATH.exists(): SIGNAL_JSON_PATH.unlink()

def ensure_csv_header(csv_path: Path):
    if csv_path.exists(): return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "date", "dayofweek", "carcount", "bikecount", "buscount", "truckcount"])

def get_zone_counts(zone_lanes):
    vehicle_ids = set()
    for lane_id in zone_lanes:
        try: vehs = traci.lane.getLastStepVehicleIDs(lane_id)
        except: vehs = []
        for vid in vehs: vehicle_ids.add(vid)

    counts = {"car": 0, "moto": 0, "truck": 0, "bus": 0, "bicycle": 0}
    for vid in vehicle_ids:
        try: vtype = traci.vehicle.getTypeID(vid)
        except: continue
        if vtype in counts: counts[vtype] += 1
    return counts["car"], counts["moto"] + counts["bicycle"], counts["bus"], counts["truck"]

def append_zone_snapshot(sim_step: int):
    snap_dt = START_DATETIME + timedelta(seconds=sim_step)
    row = [
        snap_dt.strftime("%H:%M:%S"),
        snap_dt.strftime("%d/%m/%Y"),
        snap_dt.strftime("%A")
    ]
    for zone_name, csv_path in ZONE_CSV_PATHS.items():
        ensure_csv_header(csv_path)
        lanes = ZONE_LANES.get(zone_name, [])
        counts = get_zone_counts(lanes)
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row + list(counts))

# --- AI WORKER (CHẠY NGẦM) ---
def run_script(script_name: str):
    path = Path(script_name)
    # capture_output=True để ẩn log rác nếu muốn
    subprocess.run([sys.executable, str(path)], check=True)

def Data_measure():
    procs = [
        subprocess.Popen([sys.executable, str(Path(r"D:\CODE\AI\Traffic\Simulation\script\D1.py"))]),
        subprocess.Popen([sys.executable, str(Path(r"D:\CODE\AI\Traffic\Simulation\script\D2.py"))]),
        subprocess.Popen([sys.executable, str(Path(r"D:\CODE\AI\Traffic\Simulation\script\D3.py"))]),
        subprocess.Popen([sys.executable, str(Path(r"D:\CODE\AI\Traffic\Simulation\script\D4.py"))]),
    ]
    for p in procs: p.wait()

def background_ai_task():
    """Hàm này sẽ chạy trong Thread riêng để không block SUMO"""
    try:
        # 1. Chạy các script tính toán
        Data_measure()
        run_script(r"D:\CODE\AI\Traffic\Simulation\script\MPC.py")
        
        # 2. Đọc kết quả JSON
        if SIGNAL_JSON_PATH.exists():
            with SIGNAL_JSON_PATH.open("r", encoding="utf-8") as f:
                plan = json.load(f)
            # 3. Đẩy kết quả vào Queue để Main Thread nhận
            ai_result_queue.put(plan)
        else:
            print("[THREAD] Warning: signal.json not found after script run.")
            ai_result_queue.put(None)
            
    except Exception as e:
        print(f"[THREAD] Error running AI: {e}")
        ai_result_queue.put(None)

def build_tls_schedule_from_signal(signal_plan: dict):
    phases = signal_plan.get("phases", [])
    ns_green, ew_green = None, None
    for p in phases:
        if p.get("phase") == "NS": ns_green = float(p.get("duration_s", 0))
        elif p.get("phase") == "EW": ew_green = float(p.get("duration_s", 0))
    
    if ns_green is None or ew_green is None: return None # Tránh crash

    schedule = [
        (PHASE_INDEX["NS_G"], ns_green),
        (PHASE_INDEX["NS_Y"], YELLOW_NS_S),
        (PHASE_INDEX["EW_G"], ew_green),
        (PHASE_INDEX["EW_Y"], YELLOW_EW_S),
    ]
    return schedule

# =========================
# ====== SUMO CONTROL =====
# =========================

def start_sumo():
    sumo_cmd = [SUMO_BINARY, "-c", SUMO_CONFIG, "--start", "--step-length", str(SIM_STEP_LENGTH_S)]
    traci.start(sumo_cmd)

def run_controller():
    global is_ai_running
    clear_old_outputs() 
    start_sumo()

    sim_step = 0
    
    # State quản lý Schedule
    current_schedule = None # List các pha đang chạy
    schedule_pos = 0        # Đang ở pha thứ mấy trong schedule
    remaining = 0.0         # Thời gian còn lại của pha hiện tại
    
    pending_plan = None     # Plan mới từ AI (chờ áp dụng)

    # Tạo một plan mặc định ban đầu (để chạy những giây đầu tiên)
    # Ví dụ: NS=30s, EW=30s
    default_plan = {
        "phases": [{"phase": "NS", "duration_s": 15}, {"phase": "EW", "duration_s": 15}]
    }
    current_schedule = build_tls_schedule_from_signal(default_plan)
    
    # Set pha đầu tiên ngay lập tức
    p_idx, p_dur = current_schedule[0]
    traci.trafficlight.setPhase(TLS_ID, p_idx)
    traci.trafficlight.setPhaseDuration(TLS_ID, p_dur)
    remaining = p_dur
    print(f"[INIT] Start with default schedule.")

    try:
        while sim_step < SIM_DURATION_S and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            sim_step += 1

            # --- 1. Gửi trạng thái Server ---
            try:
                cur_phase = traci.trafficlight.getPhase(TLS_ID)
                # report_status_to_server(cur_phase != 0)
                is_red_status = (cur_phase == 1 or cur_phase == 2)
                report_status_to_server(is_red_status)
            except: pass

            # --- 2. Ghi dữ liệu ---
            append_zone_snapshot(sim_step)

            # --- 3. Kiểm tra kết quả từ Thread AI (nếu có) ---
            if not ai_result_queue.empty():
                new_data = ai_result_queue.get()
                is_ai_running = False # Đánh dấu AI đã xong
                if new_data:
                    pending_plan = new_data
                    print(f"[CTRL] AI finished. Plan stored for next cycle.")

            # --- 4. Logic Trigger AI (Lookahead 5s) ---
            # Kích hoạt nếu: 
            #   - Chưa chạy AI
            #   - Đã qua thời gian delay ban đầu
            #   - Đang ở pha cuối cùng của chu kỳ (thường là Vàng EW)
            #   - Thời gian còn lại của pha này <= 5s
            if (not is_ai_running 
                and sim_step >= AI_START_DELAY_S
                and current_schedule is not None
                and schedule_pos == len(current_schedule) - 1 # Đang ở pha cuối
                and remaining <= AI_PRE_CALC_OFFSET_S         # Còn <= 5s
            ):
                print(f"[CTRL] step={sim_step}: Triggering AI background task...")
                is_ai_running = True
                t = threading.Thread(target=background_ai_task)
                t.daemon = True # Để thread tự tắt khi chương trình chính tắt
                t.start()

            # --- 5. Điều khiển đèn (Traffic Light Logic) ---
            if current_schedule is not None:
                remaining -= SIM_STEP_LENGTH_S
                
                # Hết pha hiện tại
                if remaining <= 0:
                    schedule_pos += 1
                    
                    # Vẫn còn pha trong chu kỳ hiện tại
                    if schedule_pos < len(current_schedule):
                        phase_index, duration_s = current_schedule[schedule_pos]
                        traci.trafficlight.setPhase(TLS_ID, phase_index)
                        traci.trafficlight.setPhaseDuration(TLS_ID, duration_s)
                        remaining = duration_s
                        print(f"[TLS] -> Phase {phase_index} ({duration_s}s)")
                    
                    # Hết chu kỳ -> Chuyển sang chu kỳ mới
                    else:
                        print(f"[TLS] Cycle finished at step {sim_step}")
                        
                        # Kiểm tra xem có plan mới từ AI chưa
                        if pending_plan is not None:
                            # Có plan mới -> Áp dụng
                            current_schedule = build_tls_schedule_from_signal(pending_plan)
                            pending_plan = None # Reset
                            print(f"[TLS] Applying NEW AI PLAN.")
                        else:
                            # Chưa có (AI tính chậm hoặc chưa đến lúc) -> Lặp lại plan cũ
                            # Hoặc dùng default_plan nếu muốn
                            print(f"[TLS] No new AI plan ready. Repeating old cycle.")
                            # current_schedule giữ nguyên, chỉ reset pos
                        
                        # Bắt đầu pha đầu tiên của chu kỳ mới
                        schedule_pos = 0
                        phase_index, duration_s = current_schedule[0]
                        traci.trafficlight.setPhase(TLS_ID, phase_index)
                        traci.trafficlight.setPhaseDuration(TLS_ID, duration_s)
                        remaining = duration_s
                        print(f"[TLS] Start Cycle: Phase {phase_index} ({duration_s}s)")

    finally:
        traci.close()
        print("[SUMO] Closed.")

if __name__ == "__main__":
    run_controller()