from ultralytics import YOLO
import cv2
import numpy as np

#config
model = YOLO('D:/CODE/AI/Traffic/runs/detect/train16/weights/best.pt')
allowed_classes = list(range(12))
cap = cv2.VideoCapture(r'D:\CODE\AI\Traffic\video_source\src.mp4')
zones = {
    'Zone 1': np.array([(760, 893), (1019, 984), (1335, 652), (1189, 605)]),
    'Zone 2': np.array([(1049, 992), (1607, 1061), (1706, 704), (1359, 661)]),
    'Zone 3': np.array([(1240, 584), (1343, 633), (1547, 389), (1496, 363)]),
    'Zone 4': np.array([(1588, 386), (1379, 632), (1707, 671), (1736, 406)])
}

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, imgsz=640, conf=0.35, iou=0.5)
    annotated_frame = frame.copy()
    zone_counts = {zone_name: 0 for zone_name in zones}

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        if cls_id in allowed_classes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            label = f"{model.names[cls_id]} {conf:.2f}"

            # Tính tâm bounding box
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            center = np.array([cx, cy])

            # Kiểm tra xem tâm có nằm trong vùng nào không
            for zone_name, polygon in zones.items():
                if cv2.pointPolygonTest(polygon, (cx, cy), False) >= 0:
                    zone_counts[zone_name] += 1
                    break 

            # Vẽ bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated_frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.circle(annotated_frame, (cx, cy), 3, (255, 0, 0), -1)

    # Vẽ các vùng
    # for zone_name, polygon in zones.items():
    #     cv2.polylines(annotated_frame, [polygon], isClosed=True, color=(0, 0, 255), thickness=2)
    #     cv2.putText(annotated_frame, f"{zone_name}: {zone_counts[zone_name]}", 
    #                 (polygon[0][0], polygon[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 
    #                 0.7, (0, 0, 255), 2)
    cv2.imshow("Zone Detection", annotated_frame)
    if cv2.waitKey(1) == 27:
        break
cap.release()
cv2.destroyAllWindows()
