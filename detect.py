from ultralytics import YOLO
import cv2
import os

def detect_crowd(source):
    """
    Detect crowd using YOLOv8 model
    Args:
        source: Image path, video path, or 0 for webcam
    Returns:
        int: Number of people detected
    """
    try:
        # Check if source file exists
        if isinstance(source, str) and not os.path.exists(source):
            print(f"Error: File {source} does not exist")
            return 0
        
        # Load YOLOv8 model
        model = YOLO('yolov8n.pt')
        
        # Run inference
        results = model(source, verbose=False)
        
        person_count = 0
        
        # Count persons in each frame
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                # Filter for 'person' class (class 0 in COCO dataset)
                person_detections = boxes[boxes.cls == 0]
                person_count += len(person_detections)
        
        return person_count
    
    except Exception as e:
        print(f"Error in crowd detection: {e}")
        return 0

def get_crowd_status(count):
    """
    Convert person count to crowd status
    Args:
        count: Number of people detected
    Returns:
        str: Crowd status (Low/Medium/High)
    """
    if count <= 10:
        return 'Low'
    elif count <= 30:
        return 'Medium'
    else:
        return 'High'