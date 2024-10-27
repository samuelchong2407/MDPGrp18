import os
import cv2
import numpy as np

# Global variables to track the frame and position
frame = None
frame_position = 0

def stitch_images(current_image, uploads_path, frame_width=1, frame_height=2, img_count=2):
    global frame, frame_position  # Use global to persist frame between calls
    
    # Initialize the frame as None for the first time
    if frame is None:
        # Get the dimensions of the first image to construct the frame
        img_height, img_width = current_image.shape[:2]
        # Create an empty frame (2 rows x 4 columns) with blank (black) placeholders
        frame = np.zeros((img_height * frame_height, img_width * frame_width, 3), dtype=current_image.dtype)

    # Calculate the row and column for the next image position
    row = frame_position // frame_width  # 0 for first row, 1 for second row
    col = frame_position % frame_width  # 0 to 3 for columns

    # Determine where to place the current image on the frame
    start_y = row * current_image.shape[0]
    start_x = col * current_image.shape[1]

    # Insert the current image into the frame
    frame[start_y:start_y + current_image.shape[0], start_x:start_x + current_image.shape[1]] = current_image

    # Move to the next position
    frame_position += 1

    # Save the frame even if it's not yet full
    stitched_image_path = os.path.join(uploads_path, "stitched_frame.jpg")
    cv2.imwrite(stitched_image_path, frame)

    # If the frame is full or if there are no more images to add
    if frame_position == img_count:
        # Reset frame and position for the next batch
        frame = None
        frame_position = 0

    return stitched_image_path
