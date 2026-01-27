# train_next5min.py
# -*- coding: utf-8 -*-
"""
Train XGB (dự báo PCU 5' tới) + GBM/LGBM (phân loại trạng thái) cho dataset đã chuẩn hoá.
CSV cần có: timestamp, year, hour(giây), day_of_week, total_PCU,
            total_PCU_lag1..3, target_next_PCU
Chạy:
  python Train_JOBLIB.py --csv traffic_prepared_next_measure.csv --outdir models_next5m --opt_thr
  python Train_JOBLIB.py --csv D:\CODE\AI\Traffic\Software\YOLOrun\Prepared_dataset\zone1.csv --outdir D:\CODE\AI\Traffic\Simulation\XGBNewModel_1\zone1 --opt_thr
"""

import argparse
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import GradientBoostingClassifier

import xgboost as xgb
from xgboost import XGBRegressor

# LightGBM (tùy chọn). Nếu không có, fallback sang GradientBoostingClassifier
try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except Exception:
    HAS_LGBM = False
    warnings.warn("LightGBM không khả dụng. Sẽ dùng GradientBoostingClassifier thay thế.", RuntimeWarning)


# ========= Helpers =========
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def to_float_df(df: pd.DataFrame, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def pick_feature_cols(df: pd.DataFrame):
    candidates = [
        "year", "hour", "day_of_week",
        "total_PCU", "total_PCU_lag1", "total_PCU_lag2", "total_PCU_lag3",
        "carcount", "bikecount", "buscount", "truckcount", "total_vehicles",
        "car_PCU", "bike_PCU", "bus_PCU", "truck_PCU",
    ]
    return [c for c in candidates if c in df.columns]

def label_by_thresholds(x: float, thr):
    t1, t2, t3 = thr
    if x < t1: return "thấp"
    elif x < t2: return "bình thường"
    elif x < t3: return "cao"
    else: return "tắc nghẽn"

def compute_thresholds_by_quantiles(y_train: pd.Series, quantiles):
    return [float(np.percentile(y_train, q * 100)) for q in quantiles]

def optimize_thresholds(y_true_num: pd.Series,
                        y_pred_num: np.ndarray,
                        y_train_full: pd.Series,
                        quantile_candidates):
    best_f1, best_thr = -1.0, None
    for q1 in quantile_candidates:
        for q2 in quantile_candidates:
            for q3 in quantile_candidates:
                if not (q1 < q2 < q3):
                    continue
                thr = compute_thresholds_by_quantiles(y_train_full, (q1, q2, q3))
                y_true_lbl = y_true_num.apply(lambda v: label_by_thresholds(v, thr))
                y_pred_lbl = pd.Series(y_pred_num).apply(lambda v: label_by_thresholds(v, thr))
                f1 = f1_score(y_true_lbl, y_pred_lbl, average="macro")
                if f1 > best_f1:
                    best_f1, best_thr = f1, thr
    return best_thr, best_f1

def xgb_is_ge_210():
    """True nếu xgboost >= 2.1.0 (bỏ eval_metric/early_stopping_rounds khỏi fit)."""
    try:
        major, minor, *_ = xgb.__version__.split(".")
        major, minor = int(major), int(minor)
        return (major > 2) or (major == 2 and minor >= 1)
    except Exception:
        return True  # mặc định theo nhánh mới

def make_xgb_params():
    base = dict(
        n_estimators=2000,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        tree_method="gpu_hist",
        predictor="gpu_predictor",
    )
    # Với >=2.1, đặt eval_metric + early_stopping_rounds NGAY TRONG CONSTRUCTOR
    if xgb_is_ge_210():
        base["eval_metric"] = "rmse"
        base["early_stopping_rounds"] = 100
    return base

def xgb_fit_compat(model: XGBRegressor, X, y, eval_set):
    """
    Tương thích:
    - xgboost >= 2.1.0: early_stopping_rounds & eval_metric nằm trong constructor; fit chỉ cần eval_set
    - xgboost <  2.1.0: truyền eval_metric & early_stopping_rounds trong fit(...)
    """
    if xgb_is_ge_210():
        model.fit(X, y, eval_set=eval_set)
    else:
        model.fit(
            X, y,
            eval_set=eval_set,
            eval_metric="rmse",
            early_stopping_rounds=100,
            verbose=False
        )


# ========= Main =========
def main():
    ap = argparse.ArgumentParser(description="Train XGB (next 5') + GBM/LGBM (status) theo dataset đã chuẩn hoá.")
    ap.add_argument("--csv", required=True, help="Đường dẫn CSV đã chuẩn hoá (có target_next_PCU).")
    ap.add_argument("--outdir", default="models_next5m", help="Thư mục xuất model & meta.")
    ap.add_argument("--holdout", type=float, default=0.2, help="Tỉ lệ holdout theo thời gian (mặc định 0.2).")
    ap.add_argument("--n_splits", type=int, default=5, help="Số splits cho TimeSeriesSplit (OOF).")
    ap.add_argument("--thr_default", type=float, nargs=3, default=[1200, 2400, 3400],
                    help="Ngưỡng mặc định nếu không tối ưu (t1 t2 t3).")
    ap.add_argument("--opt_thr", action="store_true", help="Bật tối ưu ngưỡng theo macro-F1 trên OOF.")
    args = ap.parse_args()

    print(f"[INFO] xgboost version: {xgb.__version__} | new_api={xgb_is_ge_210()}")

    csv_path = Path(args.csv)
    out_dir = Path(args.outdir)
    ensure_dir(out_dir)

    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    required = [
        "timestamp", "year", "hour", "day_of_week",
        "total_PCU", "total_PCU_lag1", "total_PCU_lag2", "total_PCU_lag3",
        "target_next_PCU",
    ]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise ValueError(f"Thiếu cột bắt buộc trong CSV: {miss}")

    # Sort theo thời gian
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    feats_xgb = pick_feature_cols(df)
    if not feats_xgb:
        raise ValueError("Không tìm thấy feature phù hợp trong CSV.")

    needed = list(set(feats_xgb + ["target_next_PCU"]))
    data = df.dropna(subset=needed).copy()

    X_all = to_float_df(data[feats_xgb].copy(), feats_xgb).astype(np.float32)
    y_all = pd.to_numeric(data["target_next_PCU"], errors="coerce").astype(np.float32)
    mask = y_all.notna()
    X_all, y_all = X_all[mask], y_all[mask]

    n = len(X_all)
    if n < 100:
        warnings.warn(f"Dữ liệu hợp lệ chỉ {n} dòng. Kết quả có thể không ổn.", RuntimeWarning)

    # Holdout theo thời gian
    split_idx = int(n * (1 - float(args.holdout)))
    if split_idx <= 0 or split_idx >= n:
        raise ValueError("holdout ratio không hợp lệ, sinh split_idx lỗi.")

    X_tr, X_te = X_all.iloc[:split_idx], X_all.iloc[split_idx:]
    y_tr, y_te = y_all.iloc[:split_idx], y_all.iloc[split_idx:]

    # ---------- XGBRegressor + OOF ----------
    xgb_params = make_xgb_params()

    # số folds an toàn theo kích thước (~>=50 mẫu/val)
    n_splits = max(2, min(int(args.n_splits), max(2, len(X_tr) // 50)))
    tscv = TimeSeriesSplit(n_splits=n_splits)

    oof_pred = np.zeros(len(X_tr), dtype=np.float32)

    for fold, (tr_idx, va_idx) in enumerate(tscv.split(X_tr), 1):
        model = XGBRegressor(**xgb_params)
        xgb_fit_compat(model, X_tr.iloc[tr_idx], y_tr.iloc[tr_idx], eval_set=[(X_tr.iloc[va_idx], y_tr.iloc[va_idx])])
        oof_pred[va_idx] = model.predict(X_tr.iloc[va_idx])

    # Final model: 10% cuối train làm validation cho ES (tránh leak test)
    val_n = max(1, int(len(X_tr) * 0.1))
    if val_n >= len(X_tr):
        val_n = max(1, len(X_tr) // 10)
    X_fit, y_fit = X_tr.iloc[:-val_n], y_tr.iloc[:-val_n]
    X_val, y_val = X_tr.iloc[-val_n:], y_tr.iloc[-val_n:]

    xgb_final = XGBRegressor(**xgb_params)
    xgb_fit_compat(xgb_final, X_fit, y_fit, eval_set=[(X_val, y_val)])

    pred_te_pcu = xgb_final.predict(X_te)

    # >>>>> RMSE: không dùng squared=False để tương thích sklearn cũ
    mse = mean_squared_error(y_te, pred_te_pcu)
    rmse = float(np.sqrt(mse))
    print(f"[XGB] RMSE (holdout): {rmse:.3f}")

    # ---------- Tối ưu ngưỡng (tuỳ chọn) ----------
    if args.opt_thr:
        qgrid = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        best_thr, best_f1 = optimize_thresholds(y_tr, oof_pred, y_tr, qgrid)
        thresholds = best_thr if best_thr is not None else args.thr_default
        if best_thr is None:
            print(f"[THR] Không tìm được ngưỡng tốt hơn. Dùng mặc định: {thresholds}")
        else:
            print(f"[THR] Macro-F1 (OOF)={best_f1:.3f}, thresholds={thresholds}")
    else:
        thresholds = args.thr_default
        print(f"[THR] Dùng ngưỡng mặc định: {thresholds}")

    # ---------- Classifier (stacking) ----------
    feats_cls = list(feats_xgb)
    X_tr_cls = X_tr.copy(); X_tr_cls["predicted_PCU"] = oof_pred
    X_te_cls = X_te.copy(); X_te_cls["predicted_PCU"] = pred_te_pcu.astype(np.float32)

    y_tr_cls = pd.Series(y_tr).apply(lambda v: label_by_thresholds(v, thresholds))
    y_te_cls = pd.Series(y_te).apply(lambda v: label_by_thresholds(v, thresholds))

    if HAS_LGBM:
        clf = LGBMClassifier(
            n_estimators=3000,
            learning_rate=0.03,
            num_leaves=63,
            min_child_samples=40,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=42,

            # ==========================
            # GPU SETTINGS
            # ==========================
            device_type="gpu",
            gpu_platform_id=0,
            gpu_device_id=0,
        )
        clf_name = "LGBMClassifier_GPU"
        clf.fit(X_tr_cls, y_tr_cls)
    else:
        clf = GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42)
        clf_name = "GradientBoostingClassifier"
        clf.fit(X_tr_cls, y_tr_cls)

    y_pred_cls = clf.predict(X_te_cls)
    acc = accuracy_score(y_te_cls, y_pred_cls)
    f1m = f1_score(y_te_cls, y_pred_cls, average="macro")
    print(f"[{clf_name}] ACC={acc:.3f} | Macro-F1={f1m:.3f}")
    print(classification_report(y_te_cls, y_pred_cls, digits=3))

    # ---------- Save ----------
    out_dir.mkdir(parents=True, exist_ok=True)
    xgb_path = out_dir / "xgb_model.json"
    xgb_final.save_model(str(xgb_path))

    cls_name = "gbm_model.pkl" if HAS_LGBM else "gbc_model.pkl"
    clf_path = out_dir / cls_name
    joblib.dump(clf, clf_path)

    meta = {
        "csv_path": str(csv_path),
        "feature_cols_reg": feats_xgb,
        "feature_cols_cls": feats_cls + ["predicted_PCU"],
        "thresholds": list(map(float, thresholds)),
        "holdout": {"type": "time_holdout", "train_size": int(split_idx), "test_size": int(n - split_idx)},
        "models": {"xgb_model_json": xgb_path.name, "cls_model_pkl": clf_path.name, "cls_type": clf_name},
        "metrics": {"xgb_rmse_holdout": float(rmse), "cls_accuracy_holdout": float(acc), "cls_macroF1_holdout": float(f1m)},
        "label_note": "Nhãn từ target_next_PCU với thresholds (t1,t2,t3) → ['thấp','bình thường','cao','tắc nghẽn']",
        "version": "next5min-1.0.4",
        "xgboost_version": xgb.__version__,
    }
    meta_path = out_dir / "models_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(out_dir / "metrics_summary.txt", "w", encoding="utf-8") as f:
        f.write(f"XGB RMSE: {rmse:.6f}\n")
        f.write(f"{clf_name} Accuracy: {acc:.6f}\n")
        f.write(f"{clf_name} Macro-F1: {f1m:.6f}\n")
        f.write(f"Thresholds: {list(map(float, thresholds))}\n")

    print("\nĐÃ LƯU:")
    print(" -", xgb_path)
    print(" -", clf_path)
    print(" -", meta_path)
    print(" -", out_dir / "metrics_summary.txt")
    print("Sẵn sàng suy luận.")

if __name__ == "__main__":
    main()
