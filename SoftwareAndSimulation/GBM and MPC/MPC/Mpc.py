
"""
Quyết định đèn tại thời điểm mới nhất trong CSV (last row theo timestamp):
- 4 lanes cố định: N, S, E, W (mỗi lane = 1 file CSV riêng)
- CSV schema (không có lag; code sẽ tự tạo lag1/lag2/lag3):
  timestamp,date,time,dayofweek,day_of_week,year,hour,
  carcount,bikecount,buscount,truckcount,total_vehicles,
  car_PCU,bike_PCU,bus_PCU,truck_PCU,total_PCU
- Mỗi hướng có 1 folder model: models_meta.json, xgb_model.json, gbm_model.pkl
- Quyết định MPC cho duy nhất 1 thời điểm: timestamp mới nhất (union của 4 CSV)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBRegressor

#== CONFIG
#model predict:
DIR_MODEL_ROOTS: Dict[str, Path] = {
    'N': Path(r'D:\CODE\AI\Traffic\Simulation\XGBNewModel_1\zone1'),
    'S': Path(r'D:\CODE\AI\Traffic\Simulation\XGBNewModel_1\zone3'),
    'E': Path(r'D:\CODE\AI\Traffic\Simulation\XGBNewModel_1\zone2'),
    'W': Path(r'D:\CODE\AI\Traffic\Simulation\XGBNewModel_1\zone4'),
}

#input:
# CSV_PATHS: Dict[str, Path] = {
#     'N': Path(r'D:\CODE\AI\Traffic\Traffic_MPC\datasets_fast\testz1.csv'),
#     'S': Path(r'D:\CODE\AI\Traffic\Traffic_MPC\datasets_fast\testz3.csv'),
#     'E': Path(r'D:\CODE\AI\Traffic\Traffic_MPC\datasets_fast\testz2.csv'),
#     'W': Path(r'D:\CODE\AI\Traffic\Traffic_MPC\datasets_fast\testz4.csv'), D:\CODE\AI\Traffic\Simulation\INPUTDATA
# }
CSV_PATHS: Dict[str, Path] = {
    'N': Path(r'D:\CODE\AI\Traffic\Simulation\PINPUTDATA\zone4.csv'),
    'S': Path(r'D:\CODE\AI\Traffic\Simulation\PINPUTDATA\zone2.csv'),
    'E': Path(r'D:\CODE\AI\Traffic\Simulation\PINPUTDATA\zone1.csv'),
    'W': Path(r'D:\CODE\AI\Traffic\Simulation\PINPUTDATA\zone3.csv'),
}
#config mpc
CYCLE_LEN = 40 #chu ki
G_MIN = 10
G_MAX = 90
STEP = 5
HORIZON = 3
MU = 0.7 #toc do xa pcu (pcu/s)
EPS = 1e-6
BETA_SPLIT = 1.0
DIR_ORDER = ["N", "S", "E", "W"]

#== UTILS
NUMERIC_OPTIONAL = [
    "carcount","bikecount","buscount","truckcount","total_vehicles",
    "car_PCU","bike_PCU","bus_PCU","truck_PCU"
]
SAVE_DIR = Path(r"D:\CODE\AI\Traffic\Simulation\script")

def print_control_signals(ts_key: str, g_NS: float, g_EW: float, gsplit_first_cycle: dict,
                          cycle_len: int = CYCLE_LEN, save_dir: Path | None = None):
    g_NS_i = int(round(g_NS))
    g_EW_i = int(round(g_EW))

    print("=== SIGNAL PLAN ===")
    print(f"PHASE_1: NS_GREEN_EW_RED duration={g_NS_i}s")
    print(f"PHASE_2: EW_GREEN_NS_RED duration={g_EW_i}s")

    cmd = {
        "cmd": "SET_PLAN",
        "ts_key": ts_key,
        "cycle_len_s": int(cycle_len),
        "phases": [
            {"phase": "NS", "duration_s": g_NS_i, "signals": {"N": "G", "S": "G", "E": "R", "W": "R"}},
            {"phase": "EW", "duration_s": g_EW_i, "signals": {"N": "R", "S": "R", "E": "G", "W": "G"}}
        ],
        "effective_split_first_cycle_s": {
            "N": round(float(gsplit_first_cycle.get("N", 0.0)), 1),
            "S": round(float(gsplit_first_cycle.get("S", 0.0)), 1),
            "E": round(float(gsplit_first_cycle.get("E", 0.0)), 1),
            "W": round(float(gsplit_first_cycle.get("W", 0.0)), 1),
        }
    }

    # print("SIGNAL_CMD " + json.dumps(cmd, ensure_ascii=False))
    # print("=== END SIGNAL PLAN ===")
#save file json (websocket) (esp32) (hardware)
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        out_path = save_dir / f"signal.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(cmd, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Saved signal plan to: {out_path}")

def compute_green_split(green_suggested, cycle_time=120):
    """
    gộp ns, we
    output dạng {'N':..., 'S':..., 'E':..., 'W':...}  dict{'NS': ..., 'EW': ...}/ cycle
    """
    g_NS = max(green_suggested['N'], green_suggested['S'])
    g_EW = max(green_suggested['E'], green_suggested['W'])
    total = g_NS + g_EW
    if total == 0:  #xly /0
        g_NS = g_EW = cycle_time / 2
    else:
        scale =cycle_time / total
        g_NS *= scale
        g_EW *= scale
    return {"NS": round(g_NS, 2), "EW": round(g_EW, 2)}

def _ensure_cols(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = pd.DataFrame()
    for c in cols:
        out[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else 0.0
    return out.fillna(0.0)

def _parse_date(s: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            pass
    raise ValueError(f"Không parse được date: '{s}'")

def _parse_time(s: str):
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt).time()
        except Exception:
            pass
    raise ValueError(f"Không parse được time: '{s}'")

def _parse_timestamp(s: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            pass
    raise ValueError(f"Không parse được timestamp: '{s}'")

def _extract_key_fields(row: pd.Series):
    """
    chuẩn hoá ts.
    """
    if "timestamp" in row and pd.notna(row["timestamp"]):
        ts = _parse_timestamp(str(row["timestamp"]))
        d, t = ts.date(), ts.time()
        key = f"{d.strftime('%Y-%m-%d')} {t.strftime('%H:%M:%S')}"
        year = ts.year
        hour_sec = t.hour*3600 + t.minute*60 + t.second
        dow = ts.weekday()
        return key, year, hour_sec, int(dow)

    # fallback date + time
    date_raw, time_raw = row.get("date"), row.get("time")
    if pd.isna(date_raw) or pd.isna(time_raw):
        raise ValueError("Thiếu 'timestamp' hoặc ('date' & 'time').")
    d = _parse_date(str(date_raw))
    t = _parse_time(str(time_raw))
    key = f"{d.strftime('%Y-%m-%d')} {t.strftime('%H:%M:%S')}"
    if "year" in row and pd.notna(row["year"]):
        try:
            year = int(row["year"])
        except Exception:
            year = d.year
    else:
        year = d.year

    # hour (giây từ 0h)
    if "hour" in row and pd.notna(row["hour"]):
        try:
            v = int(float(row["hour"]))
            hour_sec = v if 0 <= v <= 86400 else (t.hour*3600 + t.minute*60 + t.second)
        except Exception:
            hour_sec = t.hour*3600 + t.minute*60 + t.second
    else:
        hour_sec = t.hour*3600 + t.minute*60 + t.second

    # dow
    if "day_of_week" in row and pd.notna(row["day_of_week"]):
        dow = int(row["day_of_week"])
    elif "dayofweek" in row and pd.notna(row["dayofweek"]):
        dow = int(row["dayofweek"])
    else:
        dow = d.weekday()

    return key, year, hour_sec, int(dow)

#== Load model
def _load_dir_model(dir_path: Path):
    meta_path = dir_path / "models_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Thiếu meta: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    xgb_json = dir_path / meta["models"]["xgb_model_json"]
    if not xgb_json.exists():
        raise FileNotFoundError(f"Thiếu XGB json: {xgb_json}")
    xgb_model = XGBRegressor()
    xgb_model.load_model(str(xgb_json))

    cls_pkl = dir_path / meta["models"]["cls_model_pkl"]
    if not cls_pkl.exists():
        raise FileNotFoundError(f"Thiếu classifier pkl: {cls_pkl}")
    gbm_model = joblib.load(str(cls_pkl))

    feats_reg = meta["feature_cols_reg"]
    feats_cls = meta["feature_cols_cls"]
    thresholds = meta.get("thresholds", [1200, 2400, 3400])

    return {
        "xgb": xgb_model,
        "gbm": gbm_model,
        "feats_reg": feats_reg,
        "feats_cls": feats_cls,
        "thr": thresholds
    }

def load_all_dir_models() -> Dict[str, dict]:
    return {d: _load_dir_model(p) for d, p in DIR_MODEL_ROOTS.items()}

#Đọc csv và chuẩn hoá
def load_lane_csv_make_lags(csv_path: Path) -> pd.DataFrame:
    """
    Đọc CSV 1 lane theo schema, chuẩn hóa key, bổ sung year/hour/dow nếu thiếu,
    sort theo key, và tạo lag1/lag2/lag3 cho total_PCU.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV không tồn tại: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"CSV rỗng: {csv_path}")

    keys, years, hours, dows = [], [], [], []
    for _, r in df.iterrows():
        key, year, hour_sec, dow = _extract_key_fields(r)
        keys.append(key); years.append(year); hours.append(hour_sec); dows.append(dow)
    df = df.copy()
    df["__key__"] = keys
    df["year"] = years
    df["hour"] = hours
    df["day_of_week"] = dows

    if "total_PCU" not in df.columns:
        df["total_PCU"] = 0.0
    df["total_PCU"] = pd.to_numeric(df["total_PCU"], errors="coerce").fillna(0.0)

    # đếm pcu theo loại
    for c in NUMERIC_OPTIONAL:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Sort và tạo lag
    df = df.sort_values("__key__").reset_index(drop=True)
    df["total_PCU_lag1"] = df["total_PCU"].shift(1).fillna(0.0)
    df["total_PCU_lag2"] = df["total_PCU"].shift(2).fillna(0.0)
    df["total_PCU_lag3"] = df["total_PCU"].shift(3).fillna(0.0)
    return df

def union_latest_key(frames: Dict[str, pd.DataFrame]) -> str:
    """
    Lấy mốc thời gian MỚI NHẤT (max __key__) trên UNION của 4 CSV.
    Đây chính là "thời điểm mong muốn" để ra quyết định.
    """
    all_keys = set()
    for df in frames.values():
        all_keys.update(df["__key__"].unique().tolist())
    if not all_keys:
        raise RuntimeError("Không tìm thấy timestamp nào trong các CSV.")
    return sorted(all_keys)[-1]

#== Predict
def predict_from_row(bundle: dict, row: pd.Series):
    """
    Dự đoán PCU t+1 + nhãn từ 1 hàng (đã có lag) của hướng.
    """
    xgb_model = bundle["xgb"]
    gbm_model = bundle["gbm"]
    FEATS_REG = bundle["feats_reg"]
    FEATS_CLS = bundle["feats_cls"]
    THRESHOLDS = bundle["thr"]

    base = {
        "year": int(row.get("year", 0)),
        "hour": float(row.get("hour", 0)),
        "day_of_week": int(row.get("day_of_week", 0)),
        "total_PCU": float(row.get("total_PCU", 0.0)),
        "total_PCU_lag1": float(row.get("total_PCU_lag1", 0.0)),
        "total_PCU_lag2": float(row.get("total_PCU_lag2", 0.0)),
        "total_PCU_lag3": float(row.get("total_PCU_lag3", 0.0)),
        # test
        "carcount": float(row.get("carcount", 0.0)),
        "bikecount": float(row.get("bikecount", 0.0)),
        "buscount": float(row.get("buscount", 0.0)),
        "truckcount": float(row.get("truckcount", 0.0)),
        "total_vehicles": float(row.get("total_vehicles", 0.0)),
        "car_PCU": float(row.get("car_PCU", 0.0)),
        "bike_PCU": float(row.get("bike_PCU", 0.0)),
        "bus_PCU": float(row.get("bus_PCU", 0.0)),
        "truck_PCU": float(row.get("truck_PCU", 0.0)),
    }
    df1 = pd.DataFrame([base])

    Xr = _ensure_cols(df1, FEATS_REG).astype(np.float32)
    next_pcu = float(xgb_model.predict(Xr)[0])

    feat_wo_pred = [c for c in FEATS_CLS if c != "predicted_PCU"]
    Xc = _ensure_cols(df1, feat_wo_pred).astype(np.float32).assign(predicted_PCU=next_pcu)
    try:
        situation = gbm_model.predict(Xc)[0]
    except Exception:
        if next_pcu < THRESHOLDS[0]: situation = "thấp"
        elif next_pcu < THRESHOLDS[1]: situation = "bình thường"
        elif next_pcu < THRESHOLDS[2]: situation = "cao"
        else: situation = "tắc nghẽn"

    return next_pcu, situation

#== Core
def simulate_one_cycle(x_state, arrivals, g_NS, g_EW):
    x = x_state.copy()
    # NS phase
    wN = x['N'] + BETA_SPLIT*arrivals['N'] + EPS
    wS = x['S'] + BETA_SPLIT*arrivals['S'] + EPS
    sum_w = max(wN + wS, EPS)
    gN = g_NS * (wN / sum_w)
    gS = g_NS * (wS / sum_w)
    x['N'] = max(x['N'] - MU * gN, 0.0)
    x['S'] = max(x['S'] - MU * gS, 0.0)
    # EW phase
    wE = x['E'] + BETA_SPLIT*arrivals['E'] + EPS
    wW = x['W'] + BETA_SPLIT*arrivals['W'] + EPS
    sum_w2 = max(wE + wW, EPS)
    gE = g_EW * (wE / sum_w2)
    gW = g_EW * (wW / sum_w2)
    x['E'] = max(x['E'] - MU * gE, 0.0)
    x['W'] = max(x['W'] - MU * gW, 0.0)
    # add arrivals
    out = {d: x[d] + max(arrivals[d], 0.0) for d in DIR_ORDER}
    g_split = {'N': gN, 'S': gS, 'E': gE, 'W': gW}
    return out, g_split

def cost_state(x):
    return x['N']**2 + x['S']**2 + x['E']**2 + x['W']**2

def rollout_cost(x0, arrivals_seq, g_NS):
    g_NS = float(g_NS)
    g_EW = float(CYCLE_LEN - g_NS)
    x = x0.copy()
    total_cost = 0.0
    g_splits = []
    for k in range(len(arrivals_seq)):
        x, gsplit = simulate_one_cycle(x, arrivals_seq[k], g_NS, g_EW)
        total_cost += cost_state(x)
        g_splits.append(gsplit)
    return total_cost, g_splits

def optimize_mpc(x0, arrivals_seq):
    gNS_min = max(G_MIN, CYCLE_LEN - G_MAX)
    gNS_max = min(G_MAX, CYCLE_LEN - G_MIN)
    best = None
    best_tuple = None
    g = gNS_min
    while g <= gNS_max + 1e-9:
        cost, g_splits = rollout_cost(x0, arrivals_seq, g_NS=g)
        if (best is None) or (cost < best):
            best = cost
            best_tuple = (g, CYCLE_LEN - g, g_splits)
        g += STEP
    return best_tuple[0], best_tuple[1], best_tuple[2], best

#== Main
def main_vscode():
    #load model
    dir_models = load_all_dir_models()

    #check csv, tạo lag
    dir_frames: Dict[str, pd.DataFrame] = {}
    for d in DIR_ORDER:
        dir_frames[d] = load_lane_csv_make_lags(CSV_PATHS[d])
        print(f"[INFO] {d}: {len(dir_frames[d])} dòng, {dir_frames[d]['__key__'].nunique()} timestamps")

    # Lấy mới nhất
    key = union_latest_key(dir_frames)
    date_str, time_str = key.split(" ")
    dow = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    print(f"[INFO] Quyết định tại mốc mới nhất: {key} (DOW={dow})")
    lane_rows: Dict[str, pd.Series] = {}
    for d in DIR_ORDER:
        df = dir_frames[d]
        rows = df[df["__key__"] == key]
        if not rows.empty:
            lane_rows[d] = rows.iloc[0]
        else:
            #set = 0 nếu lỗi đọc
            lane_rows[d] = pd.Series({
                "__key__": key,
                "year": int(date_str[:4]),
                "hour": _parse_time(time_str).hour*3600 + _parse_time(time_str).minute*60 + _parse_time(time_str).second,
                "day_of_week": dow,
                "total_PCU": 0.0,
                "total_PCU_lag1": 0.0,
                "total_PCU_lag2": 0.0,
                "total_PCU_lag3": 0.0,
            })

    #predict
    arrivals_seq = []
    state = {}
    for d in DIR_ORDER:
        r = lane_rows[d]
        state[d] = {
            "p_now": float(r.get("total_PCU", 0.0)),
            "l1": float(r.get("total_PCU_lag1", 0.0)),
            "l2": float(r.get("total_PCU_lag2", 0.0)),
            "l3": float(r.get("total_PCU_lag3", 0.0)),
            "row": r
        }

    for k in range(HORIZON):
        next_dir = {}
        for d in DIR_ORDER:
            bundle = dir_models[d]
            s = state[d]
            r = s["row"].copy()
            r["total_PCU"] = s["p_now"]
            r["total_PCU_lag1"] = s["l1"]
            r["total_PCU_lag2"] = s["l2"]
            r["total_PCU_lag3"] = s["l3"]
            nxt, _lbl = predict_from_row(bundle, r)
            next_dir[d] = max(float(nxt), 0.0)
            state[d]["l3"] = state[d]["l2"]
            state[d]["l2"] = state[d]["l1"]
            state[d]["l1"] = state[d]["p_now"]
            state[d]["p_now"] = next_dir[d]

        arrivals_seq.append(next_dir)
    x_now = {d: float(lane_rows[d].get("total_PCU", 0.0)) for d in DIR_ORDER}
    g_NS, g_EW, gsplit_horizon, J = optimize_mpc(x_now, arrivals_seq)

    # khai báo test
    green_suggested = {"N": 30.2, "S": 19.8, "E": 37.1, "W": 32.9}
    result = compute_green_split(green_suggested, cycle_time=CYCLE_LEN)

    # OUTPUT
    # print("=== DECISION @ latest timestamp ===")
    # print(f"Time={time_str}  Date={date_str}  DOW={dow}")
    # print("Current PCU:", {d: round(x_now[d], 2) for d in DIR_ORDER})
    # print(f"MPC Opt -> g_NS={g_NS:.0f}s, g_EW={g_EW:.0f}s (cycle={CYCLE_LEN}s), cost={J:.2f}")
    g0 = gsplit_horizon[0]
    # print(f"Green split (next cycle): N={g0.get('N',0):.1f}s, S={g0.get('S',0):.1f}s, E={g0.get('E',0):.1f}s, W={g0.get('W',0):.1f}s")
    # print(f"Predicted arrivals (next {HORIZON} cycles):")
    for i, arr in enumerate(arrivals_seq, 1):
        print(f"  t+{i}: {{'N': {round(arr['N'],2)}, 'S': {round(arr['S'],2)}, 'E': {round(arr['E'],2)}, 'W': {round(arr['W'],2)}}}")
    # Phần này là print test
  #  print(result)
  #  print("===================================\n")
    
    print_control_signals(ts_key=key, g_NS=g_NS, g_EW=g_EW, gsplit_first_cycle=g0,
                      cycle_len=CYCLE_LEN, save_dir=SAVE_DIR)
    #phần cứng
   # print_control_signals(ts_key=key, g_NS=g_NS, g_EW=g_EW, gsplit_first_cycle=g0, cycle_len=CYCLE_LEN)

if __name__ == "__main__":
    main_vscode()
