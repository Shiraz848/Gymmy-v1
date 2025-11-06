"""
RealsenseNew.py - RealSense Camera Integration with Advanced Angle Calculation
This version matches Camera.py's calculation logic for consistency across both camera types.
"""

import threading
import socket
import time
import numpy as np
from Audio import say, get_wav_duration
from Joint import Joint
from MP import MP
import Settings as s
import Excel


class RealsenseNew(threading.Thread):
    """
    RealSense camera handler with MediaPipe skeleton tracking
    Uses same angle calculation logic as ZED Camera for consistency
    """

    def __init__(self):
        threading.Thread.__init__(self)
        # Initialize UDP socket for receiving skeleton data from MediaPipe
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = ('localhost', 7000)
        self.sock.bind(self.server_address)
        print("REALSENSE CAMERA INITIALIZATION")
        
        # Angle tracking for smoothing
        self.previous_angles = {}
        self.max_angle_jump = 10  # Maximum degrees an angle can jump per frame
        
        # Frame tracking
        self.frame_count = 0
        self.start_time = None

    def calc_angle_3d(self, joint1, joint2, joint3, joint_name="default"):
        """
        Calculate 3D angle between three joints with smoothing and error prevention
        Matches Camera.py logic exactly
        
        Args:
            joint1: First joint (end point)
            joint2: Middle joint (vertex of angle)
            joint3: Third joint (other end point)
            joint_name: Identifier for angle tracking
            
        Returns:
            Angle in degrees (rounded to 2 decimal places) or None if calculation fails
        """
        a = np.array([joint1.x, joint1.y, joint1.z], dtype=np.float32)
        b = np.array([joint2.x, joint2.y, joint2.z], dtype=np.float32)
        c = np.array([joint3.x, joint3.y, joint3.z], dtype=np.float32)

        ba = a - b  # Vector from joint2 to joint1
        bc = c - b  # Vector from joint2 to joint3

        try:
            # Compute cosine of the angle
            cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))

            # ✅ Clamp cosine value between -1 and 1 to prevent NaN errors
            cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

            # Convert to degrees
            angle = np.degrees(np.arccos(cosine_angle))

            # ✅ Handle cases where the angle might get stuck at 180° due to straight alignment
            if np.isclose(cosine_angle, -1.0, atol=1e-3):
                angle -= 0.1  # Small shift to prevent it from sticking

            # ✅ Ensure angle smoothing to avoid sudden jumps
            if joint_name in self.previous_angles:
                angle = self.limit_angle_jump(angle, joint_name)

            self.previous_angles[joint_name] = angle

            return round(angle, 2)

        except Exception as e:
            print(f"⚠️ Could not calculate the angle for {joint_name}: {e}")
            return None

    def limit_angle_jump(self, angle, joint_name):
        """
        Limit angle changes to prevent jittery movements
        
        Args:
            angle: New calculated angle
            joint_name: Identifier for which angle
            
        Returns:
            Smoothed angle value
        """
        previous_angle = self.previous_angles[joint_name]
        if abs(angle - previous_angle) > self.max_angle_jump:
            direction = 1 if angle > previous_angle else -1
            angle = previous_angle + direction * self.max_angle_jump
        return angle

    def get_skeleton_data(self):
        """
        Receive skeleton joint data from MediaPipe via UDP socket
        
        Returns:
            Dictionary of joints {joint_name: Joint object} or None on timeout
        """
        self.sock.settimeout(1)
        try:
            data, address = self.sock.recvfrom(4096)
            data = data.decode()  # Decode bytes to string
            data = data.split('/')  # Split by '/' separator
            joints_str = []
            for i in data:
                if i:  # Skip empty strings
                    joint_data = i.split(',')
                    joints_str.append(joint_data)
            
            # Parse joints
            joints = {}
            for j in joints_str:
                if len(j) == 4:  # Ensure we have name, x, y, z
                    joints[j[0]] = Joint(j[0], float(j[1]), float(j[2]), float(j[3]) * 100)
            return joints
        except socket.timeout:
            print("Didn't receive data! [Timeout]")
            return None
        except Exception as e:
            print(f"Error parsing skeleton data: {e}")
            return None

    def run(self):
        """Main thread loop - handles exercise requests"""
        print("CAMERA START (RealSense)")
        # Initialize MediaPipe camera backend
        mediaPipe = MP()
        s.camera_backend = mediaPipe
        mediaPipe.start()
        
        while not s.finish_program:
            time.sleep(0.0001)
            if s.req_exercise != "":
                ex = s.req_exercise
                print(f"CAMERA: Exercise {ex} start")
                if s.req_exercise != "hello_waving":
                    audio = s.req_exercise
                    time.sleep(get_wav_duration(audio) + get_wav_duration("start_ex"))
                    s.max_repetitions_in_training += s.rep
                getattr(self, ex)()  # Call exercise method dynamically
                print(f"CAMERA: Exercise {ex} done")
                s.req_exercise = ""
                s.camera_done = True
            else:
                time.sleep(1)
        print("Camera Done")

    # ==================== EXERCISE TRACKING METHODS ====================

    def exercise_two_angles_3d(self, exercise_name, joint1, joint2, joint3, up_lb, up_ub, down_lb, down_ub,
                                   joint4, joint5, joint6, up_lb2, up_ub2, down_lb2, down_ub2, 
                                   use_alternate_angles=False, left_right_differ=False):
        """Track exercise with two angles (4 joints total)"""
        flag = True
        counter = 0
        list_joints = []
        s.time_of_change_position = time.time()
        
        while s.req_exercise == exercise_name:
            while s.did_training_paused and not s.stop_requested:
                time.sleep(0.01)
                if self.previous_angles != {}:
                    self.previous_angles = {}
        
            joints = self.get_skeleton_data()
            if joints is not None:
                right_angle = self.calc_angle_3d(joints[str("R_" + joint1)], joints[str("R_" + joint2)],
                                                 joints[str("R_" + joint3)], "R_1")
                left_angle = self.calc_angle_3d(joints[str("L_" + joint1)], joints[str("L_" + joint2)],
                                                joints[str("L_" + joint3)], "L_1")
                
                if use_alternate_angles:
                    right_angle2 = self.calc_angle_3d(joints[str("R_" + joint4)], joints[str("R_" + joint5)],
                                                     joints[str("L_" + joint6)], "R_2")
                    left_angle2 = self.calc_angle_3d(joints[str("L_" + joint4)], joints[str("L_" + joint5)],
                                                     joints[str("R_" + joint6)], "L_2")
                else:
                    right_angle2 = self.calc_angle_3d(joints[str("R_" + joint4)], joints[str("R_" + joint5)],
                                                   joints[str("R_" + joint6)], "R_2")
                    left_angle2 = self.calc_angle_3d(joints[str("L_" + joint4)], joints[str("L_" + joint5)],
                                                  joints[str("L_" + joint6)], "L_2")

                # Update UI information
                if flag == False:
                    s.information = [[str("R_" + joint1), str("R_" + joint2), str("R_" + joint3), up_lb, up_ub],
                                     [str("L_" + joint1), str("L_" + joint2), str("L_" + joint3), up_lb, up_ub],
                                     [str("R_" + joint4), str("R_" + joint5), str("R_" + joint6), up_lb2, up_ub2],
                                     [str("L_" + joint4), str("L_" + joint5), str("L_" + joint6), up_lb2, up_ub2]]
                else:
                    s.information = [
                        [str("R_" + joint1), str("R_" + joint2), str("R_" + joint3), down_lb, down_ub],
                        [str("L_" + joint1), str("L_" + joint2), str("L_" + joint3), down_lb, down_ub],
                        [str("R_" + joint4), str("R_" + joint5), str("R_" + joint6), down_lb2, down_ub2],
                        [str("L_" + joint4), str("L_" + joint5), str("L_" + joint6), down_lb2, down_ub2]]

                if right_angle is not None and left_angle is not None and right_angle2 is not None and left_angle2 is not None:
                    # Check exercise completion
                    if left_right_differ:
                        if (up_lb < right_angle < up_ub) & (down_lb < left_angle < down_ub) & \
                                (up_lb2 < right_angle2 < up_ub2) & (down_lb2 < left_angle2 < down_ub2) & (not flag):
                            flag = True
                            counter += 1
                            s.number_of_repetitions_in_training += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (down_lb < right_angle < down_ub) & (up_lb < left_angle < up_ub) & \
                                (down_lb2 < right_angle2 < down_ub2) & (up_lb2 < left_angle2 < up_ub2) & (flag):
                            flag = False
                    else:
                        if (up_lb < right_angle < up_ub) & (up_lb < left_angle < up_ub) & \
                                (up_lb2 < right_angle2 < up_ub2) & (up_lb2 < left_angle2 < up_ub2) & (not flag):
                            flag = True
                            counter += 1
                            s.number_of_repetitions_in_training += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (down_lb < right_angle < down_ub) & (down_lb < left_angle < down_ub) & \
                                (down_lb2 < right_angle2 < down_ub2) & (down_lb2 < left_angle2 < down_ub2) & (flag):
                            flag = False

            if counter == s.rep:
                s.req_exercise = ""
                s.success_exercise = True
                break

        s.ex_list.update({exercise_name: counter})
        Excel.wf_joints(exercise_name, list_joints)

    def exercise_two_angles_3d_with_axis_check(self, exercise_name, joint1, joint2, joint3, up_lb, up_ub, down_lb, down_ub,
                               joint4, joint5, joint6, up_lb2, up_ub2, down_lb2, down_ub2, diff_size, 
                               use_alternate_angles=False, left_right_differ=False):
        """Track exercise with two angles plus axis distance check"""
        flag = True
        counter = 0
        list_joints = []
        s.time_of_change_position = time.time()
        
        while s.req_exercise == exercise_name:
            while s.did_training_paused and not s.stop_requested:
                time.sleep(0.01)
                if self.previous_angles != {}:
                    self.previous_angles = {}
        
            joints = self.get_skeleton_data()
            if joints is not None:
                right_angle = self.calc_angle_3d(joints[str("R_" + joint1)], joints[str("R_" + joint2)],
                                                 joints[str("R_" + joint3)], "R_1")
                left_angle = self.calc_angle_3d(joints[str("L_" + joint1)], joints[str("L_" + joint2)],
                                                joints[str("L_" + joint3)], "L_1")
                
                if use_alternate_angles:
                    right_angle2 = self.calc_angle_3d(joints[str("R_" + joint4)], joints[str("R_" + joint5)],
                                                      joints[str("L_" + joint6)], "R_2")
                    left_angle2 = self.calc_angle_3d(joints[str("L_" + joint4)], joints[str("L_" + joint5)],
                                                     joints[str("R_" + joint6)], "L_2")
                else:
                    right_angle2 = self.calc_angle_3d(joints[str("R_" + joint4)], joints[str("R_" + joint5)],
                                                      joints[str("R_" + joint6)], "R_2")
                    left_angle2 = self.calc_angle_3d(joints[str("L_" + joint4)], joints[str("L_" + joint5)],
                                                     joints[str("L_" + joint6)], "L_2")

                if right_angle is not None and left_angle is not None and right_angle2 is not None and left_angle2 is not None:
                    if left_right_differ:
                        if (up_lb < right_angle < up_ub) & (down_lb < left_angle < down_ub) & \
                                (up_lb2 < right_angle2 < up_ub2) & (down_lb2 < left_angle2 < down_ub2) & \
                                (abs(joints["L_shoulder"].x - joints["R_shoulder"].x) < 200) & (not flag):
                            flag = True
                            counter += 1
                            s.number_of_repetitions_in_training += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (down_lb < right_angle < down_ub) & (up_lb < left_angle < up_ub) & \
                                (down_lb2 < right_angle2 < down_ub2) & (up_lb2 < left_angle2 < up_ub2) & \
                                (abs(joints["L_shoulder"].x - joints["R_shoulder"].x) < 200) & (flag):
                            flag = False
                    else:
                        if (up_lb < right_angle < up_ub) & (up_lb < left_angle < up_ub) & \
                                (up_lb2 < right_angle2 < up_ub2) & (up_lb2 < left_angle2 < up_ub2) & (not flag):
                            flag = True
                            counter += 1
                            s.number_of_repetitions_in_training += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (down_lb < right_angle < down_ub) & (down_lb < left_angle < down_ub) & \
                                (down_lb2 < right_angle2 < down_ub2) & (down_lb2 < left_angle2 < down_ub2) & (flag):
                            flag = False

            if counter == s.rep:
                s.req_exercise = ""
                s.success_exercise = True
                break

        s.ex_list.update({exercise_name: counter})
        Excel.wf_joints(exercise_name, list_joints)

    def exercise_three_angles_3d(self, exercise_name, joint1, joint2, joint3, up_lb, up_ub, down_lb, down_ub,
                               joint4, joint5, joint6, up_lb2, up_ub2, down_lb2, down_ub2,
                                joint7, joint8, joint9, up_lb3, up_ub3, down_lb3, down_ub3, 
                                use_alternate_angles=False, left_right_differ=False):
        """Track exercise with three angles (6 joints total)"""
        flag = True
        counter = 0
        list_joints = []
        s.time_of_change_position = time.time()
        
        while s.req_exercise == exercise_name:
            while s.did_training_paused and not s.stop_requested:
                time.sleep(0.01)
                if self.previous_angles != {}:
                    self.previous_angles = {}
        
            joints = self.get_skeleton_data()
            if joints is not None:
                right_angle = self.calc_angle_3d(joints[str("R_" + joint1)], joints[str("R_" + joint2)],
                                                 joints[str("R_" + joint3)], "R_1")
                left_angle = self.calc_angle_3d(joints[str("L_" + joint1)], joints[str("L_" + joint2)],
                                                joints[str("L_" + joint3)], "L_1")

                right_angle2 = self.calc_angle_3d(joints[str("R_" + joint4)], joints[str("R_" + joint5)],
                                                 joints[str("R_" + joint6)], "R_2")
                left_angle2 = self.calc_angle_3d(joints[str("L_" + joint4)], joints[str("L_" + joint5)],
                                                joints[str("L_" + joint6)], "L_2")

                if use_alternate_angles:
                    right_angle3 = self.calc_angle_3d(joints[str("R_" + joint7)], joints[str("R_" + joint8)],
                                                      joints[str("L_" + joint9)], "R_3")
                    left_angle3 = self.calc_angle_3d(joints[str("L_" + joint7)], joints[str("L_" + joint8)],
                                                     joints[str("R_" + joint9)], "L_3")
                else:
                    right_angle3 = self.calc_angle_3d(joints[str("R_" + joint7)], joints[str("R_" + joint8)],
                                                      joints[str("R_" + joint9)], "R_3")
                    left_angle3 = self.calc_angle_3d(joints[str("L_" + joint7)], joints[str("L_" + joint8)],
                                                     joints[str("L_" + joint9)], "L_3")

                if right_angle is not None and left_angle is not None and \
                        right_angle2 is not None and left_angle2 is not None and \
                        right_angle3 is not None and left_angle3 is not None:

                    if (up_lb < right_angle < up_ub) & (up_lb < left_angle < up_ub) & \
                            (up_lb2 < right_angle2 < up_ub2) & (up_lb2 < left_angle2 < up_ub2) & \
                            (up_lb3 < right_angle3 < up_ub3) & (up_lb3 < left_angle3 < up_ub3) & (not flag):
                        flag = True
                        counter += 1
                        s.number_of_repetitions_in_training += 1
                        s.patient_repetitions_counting_in_exercise += 1
                        print(f"counter: {counter}")
                        say(str(counter))
                    elif (down_lb < right_angle < down_ub) & (down_lb < left_angle < down_ub) & \
                            (down_lb2 < right_angle2 < down_ub2) & (down_lb2 < left_angle2 < down_ub2) & \
                            (down_lb3 < right_angle3 < down_ub3) & (down_lb3 < left_angle3 < down_ub3) & (flag):
                        flag = False

            if counter == s.rep:
                s.req_exercise = ""
                s.success_exercise = True
                break

        s.ex_list.update({exercise_name: counter})
        Excel.wf_joints(exercise_name, list_joints)

    def exercise_one_angle_3d_by_sides(self, exercise_name, joint1, joint2, joint3, one_lb, one_ub, two_lb, two_ub, side):
        """Track exercise with one angle, checking position by side"""
        flag = True
        counter = 0
        list_joints = []
        s.time_of_change_position = time.time()
        
        while s.req_exercise == exercise_name:
            while s.did_training_paused and not s.stop_requested:
                time.sleep(0.01)
                if self.previous_angles != {}:
                    self.previous_angles = {}
            
            joints = self.get_skeleton_data()
            if joints is not None:
                right_angle = self.calc_angle_3d(joints[str("R_" + joint1)], joints[str("R_" + joint2)],
                                          joints[str("R_" + joint3)], "R_1")
                left_angle = self.calc_angle_3d(joints[str("L_" + joint1)], joints[str("L_" + joint2)],
                                         joints[str("L_" + joint3)], "L_1")

                if side == 'right':
                    if right_angle is not None and left_angle is not None:
                        if (one_lb < right_angle < one_ub) & (joints[str("R_wrist")].x > joints[str("L_shoulder")].x + 50) & \
                           (joints[str("nose")].y - 50 > joints[str("R_wrist")].y) & (not flag):
                            flag = True
                            counter += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            s.number_of_repetitions_in_training += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (two_lb < right_angle < two_ub) & (joints[str("R_wrist")].x < joints[str("L_shoulder")].x - 400) & (flag):
                            flag = False
                else:
                    if right_angle is not None and left_angle is not None:
                        if (one_lb < left_angle < one_ub) & (joints[str("R_shoulder")].x - 50 > joints[str("L_wrist")].x) & \
                           (joints[str("nose")].y - 50 > joints[str("L_wrist")].y) & (not flag):
                            flag = True
                            counter += 1
                            s.number_of_repetitions_in_training += 1
                            s.patient_repetitions_counting_in_exercise += 1
                            print(f"counter: {counter}")
                            say(str(counter))
                        elif (two_lb < left_angle < two_ub) & (joints[str("L_wrist")].x > joints[str("R_shoulder")].x + 400) & (flag):
                            flag = False

            if counter == s.rep:
                s.req_exercise = ""
                s.success_exercise = True
                break

        s.ex_list.update({exercise_name: counter})
        Excel.wf_joints(exercise_name, list_joints)

    # ==================== EXERCISE DEFINITIONS ====================

    def hello_waving(self):
        """Check if the participant waved"""
        while s.req_exercise == "hello_waving":
            joints = self.get_skeleton_data()
            if joints is not None:
                right_shoulder = joints[str("R_shoulder")]
                right_wrist = joints[str("R_wrist")]
                if right_shoulder.y < right_wrist.y != 0:
                    s.waved_has_tool = True
                    s.req_exercise = ""

    # Ball Exercises
    def ball_bend_elbows(self):  # EX1
        self.exercise_two_angles_3d("ball_bend_elbows", "shoulder", "elbow", "wrist", 150, 180, 10, 60,
                                    "elbow", "shoulder", "hip", 0, 60, 0, 60)

    def ball_raise_arms_above_head(self):  # EX2
        self.exercise_two_angles_3d("ball_raise_arms_above_head", "hip", "shoulder", "elbow", 125, 170, 0, 50,
                                    "shoulder", "elbow", "wrist", 120, 180, 135, 180)

    def ball_switch(self):  # EX3
        self.exercise_two_angles_3d("ball_switch", "shoulder", "elbow", "wrist", 100, 180, 140, 180,
                                    "wrist", "hip", "hip", 95, 140, 35, 70, True, True)

    def ball_open_arms_and_forward(self):  # EX4
        self.exercise_three_angles_3d("ball_open_arms_and_forward", "hip", "shoulder", "elbow", 40, 120, 80, 120,
                                      "shoulder", "elbow", "wrist", 0, 180, 140, 180,
                                    "elbow", "shoulder", "shoulder", 60, 135, 150, 180, True)

    def ball_open_arms_above_head(self):  # EX5
        self.exercise_two_angles_3d("ball_open_arms_above_head", "elbow", "shoulder", "hip", 145, 180, 80, 110,
                                   "shoulder", "elbow", "wrist", 130, 180, 130, 180)

    # Band Exercises
    def band_open_arms(self):  # EX6
        self.exercise_two_angles_3d("band_open_arms", "hip", "shoulder", "wrist", 85, 120, 70, 120,
                                    "wrist", "shoulder", "shoulder", 135, 170, 70, 110, True)

    def band_open_arms_and_up(self):  # EX7
        self.exercise_three_angles_3d("band_open_arms_and_up", "hip", "shoulder", "wrist", 125, 170, 20, 100,
                                    "shoulder", "elbow", "wrist", 130, 180, 0, 180,
                                    "elbow", "shoulder", "shoulder", 110, 160, 70, 105, True)

    def band_up_and_lean(self):  # EX8
        self.exercise_two_angles_3d("band_up_and_lean", "shoulder", "elbow", "wrist", 125, 180, 125, 180,
                                   "wrist", "hip", "hip", 120, 170, 50, 100, True, True)

    def band_straighten_left_arm_elbows_bend_to_sides(self):  # EX9
        self.exercise_two_angles_3d("band_straighten_left_arm_elbows_bend_to_sides", "shoulder", "elbow", "wrist", 135, 180, 10, 40,
                                    "elbow", "shoulder", "hip", 0, 35, 0, 30)

    def band_straighten_right_arm_elbows_bend_to_sides(self):  # EX10
        self.exercise_two_angles_3d("band_straighten_right_arm_elbows_bend_to_sides", "shoulder", "elbow", "wrist", 135, 180, 10, 40,
                                    "elbow", "shoulder", "hip", 0, 35, 0, 30)

    # Stick Exercises
    def stick_bend_elbows(self):  # EX11
        self.exercise_two_angles_3d("stick_bend_elbows", "shoulder", "elbow", "wrist", 135, 180, 10, 40,
                                    "elbow", "shoulder", "hip", 0, 35, 0, 30)

    def stick_bend_elbows_and_up(self):  # EX12
        self.exercise_two_angles_3d("stick_bend_elbows_and_up", "hip", "shoulder", "elbow", 110, 170, 10, 50,
                                 "shoulder", "elbow", "wrist", 125, 180, 30, 85)

    def stick_raise_arms_above_head(self):  # EX13
        self.exercise_two_angles_3d("stick_raise_arms_above_head", "hip", "shoulder", "elbow", 115, 180, 10, 55,
                                    "wrist", "elbow", "shoulder", 130, 180, 130, 180)

    def stick_switch(self):  # EX14
        self.exercise_two_angles_3d_with_axis_check("stick_switch", "shoulder", "elbow", "wrist", 0, 180, 140, 180,
                                    "wrist", "hip", "hip", 95, 140, 35, 70, 200, True, True)

    def stick_up_and_lean(self):  # EX15
        self.exercise_two_angles_3d("stick_up_and_lean", "shoulder", "elbow", "wrist", 125, 180, 125, 180,
                                   "wrist", "hip", "hip", 120, 170, 50, 100, True, True)

    # Weights Exercises  
    def weights_open_arms_and_forward(self):  # EX18
        self.exercise_two_angles_3d("weights_open_arms_and_forward", "hip", "shoulder", "elbow", 40, 120, 80, 120,
                                    "shoulder", "elbow", "wrist", 0, 180, 140, 180)

    def weights_abduction(self):  # EX19
        self.exercise_two_angles_3d("weights_abduction", "hip", "shoulder", "elbow", 80, 120, 0, 40,
                                    "shoulder", "elbow", "wrist", 130, 180, 130, 180)

    # No Tool Exercises
    def notool_hands_behind_and_lean(self):  # EX20
        self.exercise_two_angles_3d("notool_hands_behind_and_lean", "shoulder", "elbow", "wrist", 10, 70, 10, 70,
                                    "elbow", "shoulder", "hip", 30, 95, 125, 170, False, True)

    def notool_right_hand_up_and_bend(self):  # EX21
        self.exercise_one_angle_3d_by_sides("notool_right_hand_up_and_bend", "hip", "shoulder", "wrist", 120, 160, 0, 180, "right")

    def notool_left_hand_up_and_bend(self):  # EX22
        self.exercise_one_angle_3d_by_sides("notool_left_hand_up_and_bend", "hip", "shoulder", "wrist", 120, 160, 0, 180, "left")

    def notool_raising_hands_diagonally(self):  # EX23
        self.exercise_two_angles_3d_with_axis_check("notool_raising_hands_diagonally", "wrist", "shoulder", "hip", 0, 100, 105, 135,
                                    "elbow", "shoulder", "shoulder", 0, 180, 40, 75, 200, True, True)

    def notool_right_bend_left_up_from_side(self):  # EX24
        self.exercise_two_angles_3d("notool_right_bend_left_up_from_side", "shoulder", "elbow", "wrist", 120, 160, 20, 80,
                                    "hip", "shoulder", "elbow", 80, 120, 0, 40)

    def notool_left_bend_right_up_from_side(self):  # EX25
        self.exercise_two_angles_3d("notool_left_bend_right_up_from_side", "shoulder", "elbow", "wrist", 120, 160, 20, 80,
                                    "hip", "shoulder", "elbow", 80, 120, 0, 40)


# Main execution (for testing)
if __name__ == '__main__':
    s.camera_num = 1
    s.rep = 10
    s.waved = False
    s.success_exercise = False
    s.finish_workout = False
    s.finish_program = False
    s.req_exercise = "ball_bend_elbows"
    s.number_of_repetitions_in_training = 0
    s.patient_repetitions_counting_in_exercise = 0
    s.max_repetitions_in_training = 0
    s.ex_list = {}
    
    camera = RealsenseNew()
    camera.start()
    
    print("RealSense camera started. Press Ctrl+C to stop.")
    try:
        camera.join()
    except KeyboardInterrupt:
        s.finish_program = True
        print("\nShutting down...")