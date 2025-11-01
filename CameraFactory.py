"""
CameraFactory - Creates the appropriate camera backend based on Settings
This allows seamless switching between ZED and RealSense cameras
"""
import Settings as s


def create_camera():
    """
    Factory function to create the appropriate camera object based on Settings.camera_type
    Returns: Camera object (either Camera for ZED or Realsense for RealSense)
    """
    if s.camera_type == "zed":
        print(f"🎥 Initializing ZED Camera...")
        from Camera_zed import Camera
        return Camera()
    
    elif s.camera_type == "realsense":
        print(f"🎥 Initializing RealSense Camera...")
        from Camera_realsense import RealsenseNew
        return RealsenseNew()
    
    else:
        raise ValueError(f"❌ Unknown camera_type: '{s.camera_type}'. Must be 'zed' or 'realsense'")


def get_camera_info():
    """Returns information about the current camera configuration"""
    return {
        "type": s.camera_type,
        "name": "ZED Camera" if s.camera_type == "zed" else "Intel RealSense",
        "backend": "PyZedWrapper" if s.camera_type == "zed" else "MediaPipe"
    }

