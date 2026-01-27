import pandas as pd
import numpy as np

#== Config
INPUT_FILE  = r"D:\CODE\AI\Traffic\Simulation\INPUTDATA\zone1.csv"
OUTPUT_FILE = r"D:\CODE\AI\Traffic\Simulation\PINPUTDATA\zone1.csv"

# PCU
CAR_PCU   = 1.0
BIKE_PCU  = 0.5
BUS_PCU   = 2.5
TRUCK_PCU = 3.0

LAGS = [1, 2, 3]
HORIZON_STEPS = 1

#== đọc csv
df = pd.read_csv(INPUT_FILE)

required = ["time", "date", "dayofweek", "carcount", "bikecount", "buscount", "truckcount"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Thiếu cột bắt buộc: {missing}. Cần các cột: {required}")

# TS
df["timestamp"] = pd.to_datetime(
    df["date"].astype(str) + " " + df["time"].astype(str),
    dayfirst=True, errors="coerce"
)
df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

# CHỈ GIỮ 10 DÒNG MỚI NHẤT SAU KHI ĐÃ SORT
df = df.tail(10).reset_index(drop=True)

df["year"] = df["timestamp"].dt.year

# trans sang giây
df["hour"] = (df["timestamp"] - df["timestamp"].dt.normalize()).dt.total_seconds().astype(int)

# trans sang chu kỳ tuần
df["day_of_week"] = pd.to_numeric(df["dayofweek"], errors="coerce")
bad = df["day_of_week"].isna() | (~df["day_of_week"].between(0, 6))
if bad.any():
    df.loc[bad, "day_of_week"] = df.loc[bad, "timestamp"].dt.dayofweek
df["day_of_week"] = df["day_of_week"].astype(int)

# Process PCU
for c in ["carcount", "bikecount", "buscount", "truckcount"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

df["total_vehicles"] = df["carcount"] + df["bikecount"] + df["buscount"] + df["truckcount"]

df["car_PCU"]   = df["carcount"]   * CAR_PCU
df["bike_PCU"]  = df["bikecount"]  * BIKE_PCU
df["bus_PCU"]   = df["buscount"]   * BUS_PCU
df["truck_PCU"] = df["truckcount"] * TRUCK_PCU

df["total_PCU"] = df[["car_PCU", "bike_PCU", "bus_PCU", "truck_PCU"]].sum(axis=1)

for k in LAGS:
    df[f"total_PCU_lag{k}"] = df["total_PCU"].shift(k)

df["target_next_PCU"] = df["total_PCU"].shift(-HORIZON_STEPS)

# Lọc data lỗi
needed = ["timestamp", "year", "hour", "day_of_week", "total_PCU", "target_next_PCU"] \
         + [f"total_PCU_lag{k}" for k in LAGS]
df_out = df.dropna(subset=needed).reset_index(drop=True)

col_order = [
    "timestamp", "date", "time", "dayofweek", "day_of_week", "year", "hour",
    "carcount", "bikecount", "buscount", "truckcount", "total_vehicles",
    "car_PCU", "bike_PCU", "bus_PCU", "truck_PCU",
    "total_PCU"
] + [f"total_PCU_lag{k}" for k in LAGS] + ["target_next_PCU"]
col_order = [c for c in col_order if c in df_out.columns]

df_out[col_order].to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
print(f"✅ Chuẩn hoá xong: {len(df_out)} dòng -> {OUTPUT_FILE}")
print(df_out.head(5).to_string(index=False))
