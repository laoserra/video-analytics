import numpy as np
import cv2
import backbone
import time
import sys
import os

import config_file as config
import manage_video_db as db
import detections_grpc_video as dgv


#Uncomment the next line if you want CPU execution
#os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

#grab the video file
cap = cv2.VideoCapture(sys.argv[1])
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
fps = int(cap.get(cv2.CAP_PROP_FPS))
fourcc = cv2.VideoWriter_fourcc(*'XVID')
#save the output video with bounding boxes
video_name = os.path.basename(sys.argv[1])
video_base = os.path.splitext(video_name)[0]
video_ext= os.path.splitext(video_name)[1]
output_video_name = video_base + '_bbox' + video_ext
out = cv2.VideoWriter(config.OUTPUT_FOLDER + output_video_name, fourcc, fps, (width, height))

if not os.path.exists(sys.argv[1]):
    sys.exit('video file does not exist')

# insert initial data to the video table
db.insert_video_data(video_name, fps, height, width)

# set trigger to flush detections to db
FLUSH_TRIGGER = config.FLUSH_TRIGGER

# start list of detections
detections = []

# flush partial detections to database
def flush_detections(counter, partial_detections):
    global detections
    condition = counter % FLUSH_TRIGGER
    if not condition:
        db.insert_multiple_detections(video_name, partial_detections)
        #partial_detections = []
        detections = []
        print('(flushed detections to db)')

#initialize the frame counting variable
frame_number = 0
#initialize the time
init_time = time.time()
while(True):     
    #extract frame from the video       
    ret, img = cap.read()    
    if ret:
        np.asarray(img)
        #count the frames
        frame_number += 1
        start_time = time.time()
        #process the image
        processed_img_raw = backbone.processor(img, height, width)
        processed_img = processed_img_raw[0] 
        output_dict = processed_img_raw[1] 
        category_index = config.CATEGORY_INDEX
        threshold = config.THRESHOLD
        detections.extend(dgv.get_detections(
            frame_number,
            width,
            height,
            output_dict['detection_boxes'],
            output_dict['detection_classes'],
            output_dict['detection_scores'],
            category_index,
            threshold))
        # write detections to the video db
        flush_detections(frame_number, detections)
        print ("per-frame time: " + str(time.time() - start_time) + " seconds")
        print ("overall time: " + str(time.time() - init_time) + " seconds")     
        out.write(processed_img)
        print("writing frame " + str(frame_number))
    #break the while loop if there are no frames to process    
    else:
        break 
print("end of the video!")

# update video table
db.update_video(frame_number, round((time.time() - init_time), 3), 
                backbone.totalUp, backbone.totalDown, video_name)

# flush last detections to database
db.insert_multiple_detections(video_name, detections)
print('(flushed remainder detections to db)')

# insert tracks to the tracks table
db.insert_multiple_tracks(backbone.tracker_dict, video_name)
