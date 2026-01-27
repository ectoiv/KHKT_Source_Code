import os
from ultralytics import YOLO

model = YOLO('yolo11m.pt')

if __name__ == '__main__':
    model.train(
    data=r'D:\CODE\AI\Traffic\DTS\22-01DTS\data.yaml',
    epochs=110,
    imgsz=640,
    batch=16,
    optimizer="AdamW",
    lr0=0.002,
    lrf=0.1,
    warmup_epochs=5,
    weight_decay=0.001,
    cos_lr=True,
    patience=20,
    mosaic=1.0,
    close_mosaic=15,
    mixup=0.20,
    copy_paste=0.20,
    degrees=5.0,
    translate=0.10,
    scale=0.40,
    shear=2.0,
    hsv_h=0.015,
    hsv_s=0.70,
    hsv_v=0.40,
    fliplr=0.5,
    flipud=0.0,
    label_smoothing=0.05,
    dropout=0.10,
    device=0,
    workers=8,
    verbose=True
)