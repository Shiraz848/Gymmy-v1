"""
Test Script for RealSense + MediaPipe Integration
This allows you to test the camera system without the full Gymmy application
"""

import time
import threading
import Settings as s
from MP import MP
from Camera_realsense import RealsenseNew


def test_mediapipe_only():
    """Test MediaPipe capture and visualization only"""
    print("\n" + "="*60)
    print("TEST 1: MediaPipe Capture Only")
    print("="*60)
    print("This will open your webcam and show skeleton detection.")
    print("Press 'q' to stop.\n")
    
    s.finish_program = False
    
    mp_thread = MP()
    mp_thread.start()
    
    try:
        mp_thread.join()
    except KeyboardInterrupt:
        s.finish_program = True
        print("\nStopped by user")


def test_full_integration():
    """Test full integration: MediaPipe -> UDP -> Camera_realsense"""
    print("\n" + "="*60)
    print("TEST 2: Full Integration Test")
    print("="*60)
    print("Testing MediaPipe + Camera_realsense communication")
    print("This will test one exercise (ball_bend_elbows)")
    print("Press Ctrl+C to stop.\n")
    
    # Initialize settings
    s.camera_num = 1
    s.rep = 5  # Test with 5 repetitions
    s.waved = False
    s.success_exercise = False
    s.finish_workout = False
    s.finish_program = False
    s.req_exercise = ""
    s.number_of_repetitions_in_training = 0
    s.patient_repetitions_counting_in_exercise = 0
    s.max_repetitions_in_training = 0
    s.ex_list = {}
    s.did_training_paused = False
    s.stop_requested = False
    
    # Start camera
    camera = RealsenseNew()
    camera.start()
    
    print("\n✅ Camera started successfully!")
    print("   Waiting for skeleton data...")
    
    # Wait a bit for MediaPipe to start sending data
    time.sleep(3)
    
    # Test getting skeleton data
    print("\n📊 Testing skeleton data reception...")
    for i in range(3):
        joints = camera.get_skeleton_data()
        if joints:
            print(f"   ✅ Frame {i+1}: Received {len(joints)} joints")
            # Show a few joint positions
            if "nose" in joints:
                print(f"      Nose position: ({joints['nose'].x:.1f}, {joints['nose'].y:.1f}, {joints['nose'].z:.1f})")
            if "R_wrist" in joints:
                print(f"      R_wrist position: ({joints['R_wrist'].x:.1f}, {joints['R_wrist'].y:.1f}, {joints['R_wrist'].z:.1f})")
        else:
            print(f"   ⚠️  Frame {i+1}: No data received")
        time.sleep(0.5)
    
    # Test angle calculation
    print("\n🔢 Testing angle calculation...")
    joints = camera.get_skeleton_data()
    if joints and "R_shoulder" in joints and "R_elbow" in joints and "R_wrist" in joints:
        angle = camera.calc_angle_3d(
            joints["R_shoulder"],
            joints["R_elbow"],
            joints["R_wrist"],
            "test_angle"
        )
        if angle:
            print(f"   ✅ Right elbow angle: {angle}°")
        else:
            print("   ⚠️  Could not calculate angle")
    
    # Now test an actual exercise
    print("\n🏋️  Testing exercise: ball_bend_elbows")
    print(f"   Target: {s.rep} repetitions")
    print("   Start doing the exercise now!\n")
    
    s.req_exercise = "ball_bend_elbows"
    s.time_of_change_position = time.time()
    
    # Wait for exercise to complete or timeout
    start_time = time.time()
    timeout = 60  # 60 seconds timeout
    
    while s.req_exercise != "" and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    # Results
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    if s.success_exercise:
        print(f"✅ Exercise completed successfully!")
        print(f"   Repetitions: {s.ex_list.get('ball_bend_elbows', 0)}/{s.rep}")
    elif time.time() - start_time >= timeout:
        print(f"⏱️  Test timed out after {timeout} seconds")
        print(f"   Repetitions: {s.ex_list.get('ball_bend_elbows', 0)}/{s.rep}")
    else:
        print(f"⚠️  Exercise stopped")
        print(f"   Repetitions: {s.ex_list.get('ball_bend_elbows', 0)}/{s.rep}")
    
    print("\n✅ Test complete!")
    
    # Cleanup
    s.finish_program = True
    time.sleep(1)


def test_skeleton_data_stream():
    """Test continuous skeleton data stream and display stats"""
    print("\n" + "="*60)
    print("TEST 3: Skeleton Data Stream")
    print("="*60)
    print("Monitoring skeleton data for 10 seconds...")
    print("This tests data reception without visualization.\n")
    
    # Initialize
    s.finish_program = False
    
    # Start MP backend
    mp_thread = MP()
    mp_thread.daemon = True
    mp_thread.start()
    
    # Start camera (receiver)
    camera = RealsenseNew()
    
    time.sleep(2)  # Wait for MP to initialize
    
    # Collect stats
    received_count = 0
    failed_count = 0
    joint_visibility = {}
    
    start_time = time.time()
    duration = 10  # seconds
    
    print("📊 Collecting data...\n")
    
    while time.time() - start_time < duration:
        joints = camera.get_skeleton_data()
        if joints:
            received_count += 1
            for joint_name, joint in joints.items():
                if joint_name not in joint_visibility:
                    joint_visibility[joint_name] = 0
                if joint.visible:
                    joint_visibility[joint_name] += 1
        else:
            failed_count += 1
        time.sleep(0.033)  # ~30 FPS
    
    # Results
    total_frames = received_count + failed_count
    success_rate = (received_count / total_frames * 100) if total_frames > 0 else 0
    
    print("="*60)
    print("STREAM STATISTICS")
    print("="*60)
    print(f"Total frames processed: {total_frames}")
    print(f"Successful frames: {received_count}")
    print(f"Failed frames: {failed_count}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"\nFPS: {received_count / duration:.1f}")
    
    print("\n📍 Joint Visibility (% of frames):")
    important_joints = ["nose", "L_shoulder", "R_shoulder", "L_elbow", "R_elbow", 
                       "L_wrist", "R_wrist", "L_hip", "R_hip"]
    for joint in important_joints:
        if joint in joint_visibility:
            visibility_pct = (joint_visibility[joint] / received_count * 100) if received_count > 0 else 0
            print(f"   {joint:15s}: {visibility_pct:5.1f}%")
    
    print("\n✅ Stream test complete!")
    
    # Cleanup
    s.finish_program = True
    time.sleep(1)


def main():
    """Main test menu"""
    print("\n" + "="*60)
    print("🎥 RealSense + MediaPipe Test Suite")
    print("="*60)
    print("\nAvailable Tests:")
    print("  1. MediaPipe Capture Only (with visualization)")
    print("  2. Full Integration Test (exercise tracking)")
    print("  3. Skeleton Data Stream Test (performance stats)")
    print("  4. Run All Tests")
    print("  0. Exit")
    
    choice = input("\nSelect test [0-4]: ").strip()
    
    if choice == "1":
        test_mediapipe_only()
    elif choice == "2":
        test_full_integration()
    elif choice == "3":
        test_skeleton_data_stream()
    elif choice == "4":
        print("\n🚀 Running all tests...\n")
        test_skeleton_data_stream()
        time.sleep(2)
        test_full_integration()
    elif choice == "0":
        print("\n👋 Goodbye!")
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        s.finish_program = True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        s.finish_program = True
        print("\n✅ Test script finished")

