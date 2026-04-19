"""
CellRoute L4 Autonomy - Video Segmentation Processor
Template for generating segmented_hud_feed.mp4 from raw_road.mp4

Requirements:
    pip install opencv-python ultralytics
"""

import cv2
from ultralytics import YOLO
import sys

def process_road_video(input_path, output_path, model_path='yolov8n-seg.pt'):
    # Load segmentation model (Pre-trained or Custom Fine-tuned)
    print(f"Loading Perception Model: {model_path}...")
    model = YOLO(model_path)
    
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {input_path}")
        return

    # Video properties
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print(f"Processing frames ({width}x{height} @ {fps}fps)...")
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.get()
        if not ret:
            break

        # Run segmentation on frame (inference)
        results = model(frame, verbose=False)
        
        # Draw results onto frame
        # We use a custom cyan overlay for the 'road' class (index 0 usually in custom models)
        annotated_frame = results[0].plot(
            conf=False, 
            labels=False, 
            line_width=2, 
            font_size=1
        )
        
        # Add 'L4 HUD' overlay text
        cv2.putText(annotated_frame, f"INF: {results[0].speed['inference']:.1f}ms", 
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2)
        cv2.putText(annotated_frame, "PERCEPTION: V24_ACTIVE", 
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2)

        out.write(annotated_frame)
        
        frame_count += 1
        if frame_count % 30 == 0:
            sys.stdout.write(f"\rProcessed {frame_count} frames...")
            sys.stdout.flush()

    cap.release()
    out.release()
    print(f"\nCompleted! Segmentation HUD saved to: {output_path}")

if __name__ == "__main__":
    # To be defined by user at execution time:
    INPUT_VIDEO  = 'road_raw.mp4'
    OUTPUT_VIDEO = 'segmented_hud_feed.mp4'
    MODEL_WEIGHTS = 'yolov8n-seg.pt' # Replace with custom fine-tuned weights
    
    process_road_video(INPUT_VIDEO, OUTPUT_VIDEO, MODEL_WEIGHTS)
