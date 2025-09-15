import cv2, sys, time

# Try Apple’s native backend explicitly
cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
if not cap.isOpened():
    print("CAP_AVFOUNDATION failed on index 0; trying index 1…")
    cap = cv2.VideoCapture(1, cv2.CAP_AVFOUNDATION)

if not cap.isOpened():
    print("Could not open camera. On macOS: System Settings → Privacy & Security → Camera → allow your Terminal/VS Code.")
    sys.exit(1)

print("Camera opened. Press q to quit.")
while True:
    ok, frame = cap.read()
    if not ok:
        print("Read failed — camera busy or blocked.")
        break
    cv2.imshow("Camera Test (press q)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
