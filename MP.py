import threading
import socket
import json
import cv2
import mediapipe as mp
import Settings as s
import time


class MP(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        print("MP INITIALIZATION")


    def run(self):
        print("MP START")
        recorded_data = []
        show = True

        # Initialize MediaPipe Pose
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        mp_pose = mp.solutions.pose

        # Initialize camera
        cap = cv2.VideoCapture(0)  # 0 - webcam, change index if multiple cameras
        image_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        image_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Initialize UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = ('localhost', 7000)

        # Define landmarks mapping
        lm_dict = {
            'nose': "0",
            'L_eye_inner': "1", 'L_eye': "2", "L_eye_outer": "3",
            'R_eye_inner': "4", 'R_eye': "5", "R_eye_outer": "6",
            'L_ear': "7", 'R_ear': "8", "L_mouth": "9", "R_mouth": "10",
            'L_shoulder': "11", 'R_shoulder': "12", 'L_elbow': "13", 'R_elbow': "14",
            'L_wrist': "15", 'R_wrist': "16",
            'L_hand_pinky': "17", 'R_hand_pinky': "18", 'L_hand_index': "19", 'R_hand_index': "20",
            'L_hand_thumb': "21", 'R_hand_thumb': "22", 'L_hip': "23", 'R_hip': "24",
        }

        # MediaPipe Pose instance
        with mp_pose.Pose(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5) as pose:
            while cap.isOpened() and not s.finish_program:
                success, image = cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue

                # Prepare image for MediaPipe
                image.flags.writeable = False
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = pose.process(image)

                # Prepare message string in format: "joint_name,x,y,z/joint_name,x,y,z/..."
                message_parts = []
                if results.pose_landmarks:
                    for key, idx in lm_dict.items():
                        landmark = results.pose_landmarks.landmark[int(idx)]
                        if landmark.visibility >= 0.7:
                            # Normalized coordinates with depth
                            x = landmark.x * image_width
                            y = -landmark.y * image_height
                            z = -landmark.z
                            message_parts.append(f"{key},{x},{y},{z}")
                        else:
                            # Default values for invisible landmarks
                            message_parts.append(f"{key},0,0,0")
                else:
                    # No pose landmarks detected
                    for key in lm_dict.keys():
                        message_parts.append(f"{key},0,0,0")

                # Join all parts with '/' separator and add trailing '/'
                message_string = '/'.join(message_parts) + '/'
                
                # Send string message over UDP
                sock.sendto(message_string.encode(), server_address)
                
                # Keep dict version for recording
                message_dict = {}
                for part in message_parts:
                    parts = part.split(',')
                    if len(parts) == 4:
                        message_dict[parts[0]] = {
                            "x": float(parts[1]),
                            "y": float(parts[2]),
                            "z": float(parts[3])
                        }

                # Draw landmarks on the image
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )

                # Display image if enabled
                if show:
                    cv2.imshow('MediaPipe Pose', cv2.flip(image, 1))

                # Handle key events
                key = cv2.waitKey(1)
                if s.finish_program or key == ord('q'):
                    s.finish_program = True
                    break

                # Record data with timestamp
                recorded_data.append({
                    'timestamp': time.time(),
                    'pose_data': message_dict
                })

            # Release resources
            cap.release()
            cv2.destroyAllWindows()

            # Save recorded data to a JSON file
            with open('recorded_data2.json', 'w') as f:
                json.dump(recorded_data, f)

        print("MP FINISHED")


if __name__ == '__main__':
    s.stop = False
    s.finish_program = False
    mediap = MP()
    mediap.start()
