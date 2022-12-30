import cv2

cap = cv2.VideoCapture("rtsp://172.27.23.235:8554/video_stream")
while True:
    
    ret, frame = cap.read()
    if ret:
        cv2.imshow("RTSP View", frame)
        cv2.waitKey(1)
    else:
        print("unable to open camera")
        break
cap.release()
cv2.destroyAllWindows()
