import json
import socket
import time
import threading
import cv2
import numpy as np
import pygame
from djitellopy import Tello
from pyzbar import pyzbar

# ESP32 details (IP address and port)
ESP32_IP = '10.0.0.71'  # Replace with your ESP32's IP address
ESP32_PORT = 8889 # Choose a port that ESP32 is listening to

# Initialize Pygame for gamepad input
pygame.init()
pygame.joystick.init()
# Check for connected joysticks
joystick_count = pygame.joystick.get_count()
if joystick_count == 0:
    print("No joystick connected.")
    exit()
else:
    # Initialize the first joystick
    gamepad = pygame.joystick.Joystick(0)
    gamepad.init()
    print(f"Gamepad detected: {gamepad.get_name()}")

# Initialize UDP socket to communicate with ESP32
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Create a Tello drone object
tello = Tello()

# Global mode (either "sales" or "inventory")
mode = "inventory"  # Default mode
in_flight = False  # Tracks whether the drone is flying
drone_connected = False
current_qr_data = None # Stores the most recently detected QR code data

def initial_connect():
    global tello, drone_connected
    print("Attempting to connect to Tello...")
    try:
        # Set a custom retry count and timeout for the initial connection
        tello.RETRY_COUNT = 25
        tello.RESPONSE_TIMEOUT = 1000
        tello.connect()
        print("Initial connection successful")
        drone_connected = True
        return True
    except Exception as e:
        print(f"Initial connection failed: {str(e)}")
        return False

def verify_drone_connection():
    global drone_connected
    try:
        # Try to get the battery level as a simple command to check connection
        battery = tello.get_battery()
        print(f"Drone battery level: {battery}%")
        drone_connected = True
        return True
    except Exception as e:
        print(f"Failed to connect to drone: {str(e)}")
        drone_connected = False
        return False

def print_gamepad_info():
    num_axes = gamepad.get_numaxes()
    print(f"Number of axes: {num_axes}")
    for i in range(num_axes):
        print(f"Axis {i} value: {gamepad.get_axis(i)}")

def read_joystick_axis(axis):
    num_axes = gamepad.get_numaxes()
    if axis >= num_axes:
        print(f"Error: Axis {axis} does not exist on this gamepad.")
        return 0  # Return default value if axis doesn't exist
    else:
        return gamepad.get_axis(axis)

# Detect and read QR codes from the frame
def detect_qr_code(frame):
    global current_qr_data
    decoded_objects = pyzbar.decode(frame)
    for obj in decoded_objects:
        qr_data = obj.data.decode('utf-8')
        (x, y, w, h) = obj.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        current_qr_data = qr_data
    return frame

# Send the data from QR Code to ESP32
def send_data_to_esp32(qr_data, model):
    try:
        json_data = json.loads(qr_data)  # Convert scanned QR data into a JSON object
        json_data["mode"] = model  # Add current mode (sales or inventory)
        json_str = json.dumps(json_data)  # Convert back to string
        sock.sendto(json_str.encode('utf-8'), (ESP32_IP, ESP32_PORT))  # Send to ESP32
        print(f"Sent JSON data to ESP32: {json_str}")
    except Exception as e:
        print(f"Error sending data to ESP32: {str(e)}")

# Function to handle gamepad input and control the drone
def handle_gamepad_input():
    global mode, in_flight, current_qr_data
    while True:
        pygame.event.pump()
        # D-Pad controls for directional and diagonal movement
        dpad_up = gamepad.get_button(11)
        dpad_down = gamepad.get_button(12)
        dpad_left = gamepad.get_button(13)
        dpad_right = gamepad.get_button(14)

        # Read joystick positions for drone control (priority below D-Pad)
        left_right = read_joystick_axis(0)
        forward_backward = read_joystick_axis(1)
        up_down = read_joystick_axis(2)
        yaw = read_joystick_axis(3)

        # Face buttons for additional control
        square = gamepad.get_button(2)  # Rotate counterclockwise
        circle = gamepad.get_button(1)  # Rotate clockwise
        cross = gamepad.get_button(0)  # Move down
        triangle = gamepad.get_button(3)  # Move up

        # Button controls
        left_bumper = gamepad.get_button(9)  # Takeoff
        right_bumper = gamepad.get_button(10)  # Land
        left_trigger = read_joystick_axis(4)  # QR code scan
        right_trigger = read_joystick_axis(5) # Toggle mode between sales/inventory

        if not drone_connected:
            print("Attempting to reconnect to drone...")
            if verify_drone_connection():
                print("Reconnected to drone")
            else:
                print("Failed to reconnect. Retrying in 5 seconds...")
                time.sleep(5)
                continue

        # Takeoff (Right Shoulder Button)
        if right_bumper == 1:  # Takeoff
            print("Attempting takeoff...")
            tello.takeoff()
            time.sleep(1)

        # Land (Left Shoulder Button)
        if left_bumper == 1:
            print("Attempting to land...")
            tello.land()
            time.sleep(1)

        # Mode toggle button (Left Trigger)
        if left_trigger > 0.5:
            if mode == "sales":
                mode = "inventory"
            else:
                mode = "sales"
            print(f"Mode toggled to: {mode}")
            time.sleep(0.5)  # Debounce

        # D-Pad directional and diagonal controls (overrides joystick values)
        if dpad_up == 1:  # Forward
            tello.move_forward(20)
            print("Moving forward.")
        elif dpad_down == 1:  # Backward
            tello.move_back(20)
            print("Moving backward.")
        elif dpad_left == 1:  # Left
            tello.move_left(20)
            print("Moving left.")
        elif dpad_right == 1:  # Right
            tello.move_right(20)
            print("Moving right.")
        elif dpad_up == 1 and dpad_left == 1:  # Forward-left
            tello.move_left(15)
            tello.move_forward(15)
            print("Moving forward-left.")
        elif dpad_up == 1 and dpad_right == 1:  # Forward-right
            tello.move_right(15)
            tello.move_forward(15)
            print("Moving forward-right.")
        elif dpad_down == -1 and dpad_left == 1:  # Back-left
            tello.move_left(15)
            tello.move_back(15)
            print("Moving back-left.")
        elif dpad_down == 1 and dpad_right == 1:  # Back-right
            tello.move_right(15)
            tello.move_back(15)
            print("Moving back-right.")

        # Face button controls for movement
        if square:  # Rotate counterclockwise
            tello.rotate_counter_clockwise(30)
            print("Rotating counterclockwise.")
        elif circle:  # Rotate clockwise
            tello.rotate_clockwise(30)
            print("Rotating clockwise.")
        elif cross:  # Move down
            tello.move_down(20)
            print("Moving down.")
        elif triangle:  # Move up
            tello.move_up(20)
            print("Moving up.")

        # Capture button (Right Trigger)
        if right_trigger > 0.5 and current_qr_data:  # If Left Trigger is pressed
            print("QR Code captured")
            send_data_to_esp32(current_qr_data, mode)
            current_qr_data = None  # Reset after sending

        time.sleep(0.5)  # Small delay to avoid hogging CPU

# Function to continuously display video stream
def display_video_stream():
    while True:
        try:
            frame = tello.get_frame_read().frame
            if frame is not None:
                # Display the frame
                detect_qr_code(frame)
                cv2.imshow("Tello Camera Feed", frame)
                cv2.waitKey(1)
        except Exception as e:
            print(f"Error in video stream: {str(e)}")
            time.sleep(1)

# Main function
def main():
    # Initialize Tello drone
    global tello, drone_connected
    try:
        if initial_connect():
            if verify_drone_connection():
                print("Tello connected successfully")
                tello.streamon()
                print("Video stream started")
                # Start the video display thread
                video_thread = threading.Thread(target=display_video_stream)
                video_thread.daemon = True  # Daemon thread so it exits when main program exits
                video_thread.start()

                # Initialize gamepad
                print_gamepad_info()

                # Start handling gamepad input
                handle_gamepad_input()
            else:
                print("Failed to verify drone connection")
        else:
            print("Failed to establish initial connection with the drone")
    except Exception as e:
        print(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program interrupted by user")
    finally:
        print("Cleaning up...")
        if drone_connected:
            tello.land()
            tello.streamoff()
        pygame.quit()
        cv2.destroyAllWindows()
        sock.close()
        print("Cleanup completed")