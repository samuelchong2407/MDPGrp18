import os
from flask import Flask, request, jsonify, send_file
from ultralytics import YOLO
import cv2
import yaml
from ImageID import imageid
from StitchedImage import stitch_images  # Import the stitch_images function

app = Flask(__name__)

# Load the YOLO model
model_path = os.path.join(os.path.dirname(__file__),'Finalz.pt')
print()
model = YOLO(model_path)

# Import data.yaml
yaml_path = os.path.join(os.path.dirname(__file__), 'data.yaml')
with open(yaml_path, 'r') as f:
    data = yaml.safe_load(f)
    class_labels = data['names']

# Directory to hold uploads
uploads_path = os.path.join(os.path.dirname(__file__), 'uploads')
if not os.path.exists(uploads_path):
    os.makedirs(uploads_path)  # Create uploads directory if it doesn't exist

# Initialize previous image paths
previous_image_path = os.path.join(uploads_path, 'previous_image.jpg')
last_stitched_image_path = os.path.join(uploads_path, 'stitched_previous_image.jpg')

# Dictionary to hold the latest detections
global latest_detections ,stitchcount
latest_detections = {}
stitchcount = 0

@app.route('/upload_image', methods=['POST'])
def upload_image():
    global previous_image_path, last_stitched_image_path,stitchcount  # Declare as global
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not os.path.exists(uploads_path):
        os.makedirs(uploads_path)
    file_path = os.path.join(uploads_path, file.filename)
    file.save(file_path)

    # Load the image with OpenCV
    image = cv2.imread(file_path)

    # Run the model on the uploaded image
    results = model(image,save=True, conf=0.4)
    # Extract detections and draw bounding boxes
    detections = []
    for detection_box in results[0].boxes:
        x1, y1, x2, y2 = map(int, detection_box.xyxy.tolist()[0])
        cls = int(detection_box.cls)
        conf = float(detection_box.conf)
        label = class_labels[cls] if cls < len(class_labels) else 'Unknown'

        image_id = imageid.get(label, 'ID Not Found')

        detections.append({
            'class': cls,
            'label': label,
            'ImageID': image_id,
            'confidence': conf,
            'coordinates': [x1, y1, x2, y2]
        })
        latest_detections['data'] = detections
        # Draw bounding box and label on the image
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(image, f'ImageID: {image_id}, {label} {conf:.2f}', 
                    (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
    
    # Stitch images and save it
    if len(detections) > 0:
        stitchcount += 1  # Update the stitch count to track number of images added

        # Call the function to add the image to the 2x4 frame
        stitched_image_path = stitch_images(image, uploads_path)

        # If a stitched image was created (i.e., frame was full), update last_stitched_image_path
        if stitched_image_path:
            last_stitched_image_path = stitched_image_path

        # Save the current image as the "previous image" for continuity
        cv2.imwrite(previous_image_path, image)
    

    # Return the current image with detections
    current_image_path = os.path.join(uploads_path, f"detected_{file.filename}")
    cv2.imwrite(current_image_path, image)

    return jsonify({'detections': detections})

@app.route('/get_detections', methods=['GET'])
def get_detections():
    return jsonify(latest_detections.get('data', []))

if __name__ == '__main__':
    
    app.run(host='0.0.0.0', port=5000)
