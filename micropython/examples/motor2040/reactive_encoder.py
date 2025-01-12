import gc
import time
from plasma import WS2812
from motor import Motor, motor2040
from encoder import Encoder, MMME_CPR
from pimoroni import Button, PID, NORMAL_DIR  # , REVERSED_DIR

"""
A demonstration of how a motor with an encoder can be used
as a programmable rotary encoder for user input, with
force-feedback for arbitrary detents and end stops.

Press "Boot" to exit the program.

NOTE: Plasma WS2812 uses the RP2040's PIO system, and as
such may have problems when running code multiple times.
If you encounter issues, try resetting your board.
"""

MOTOR_PINS = motor2040.MOTOR_A          # The pins of the motor being profiled
ENCODER_PINS = motor2040.ENCODER_A      # The pins of the encoder attached to the profiled motor
GEAR_RATIO = 50                         # The gear ratio of the motor
COUNTS_PER_REV = MMME_CPR * GEAR_RATIO  # The counts per revolution of the motor's output shaft

DIRECTION = NORMAL_DIR                  # The direction to spin the motor in. NORMAL_DIR (0), REVERSED_DIR (1)
SPEED_SCALE = 5.4                       # The scaling to apply to the motor's speed to match its real-world speed

UPDATES = 100                           # How many times to update the motor per second
UPDATE_RATE = 1 / UPDATES
PRINT_DIVIDER = 4                       # How many of the updates should be printed (i.e. 2 would be every other update)

# Multipliers for the different printed values, so they appear nicely on the Thonny plotter
SPD_PRINT_SCALE = 20                    # Driving Speed multipler

DETENT_SIZE = 20                        # The size (in degrees) of each detent region
MIN_DETENT = -12                        # The minimum detent that can be counted to
MAX_DETENT = +12                        # The maximum detent that can be counted to
MAX_DRIVE_PERCENT = 0.5                 # The maximum drive force (as a percent) to apply when crossing detents

BRIGHTNESS = 0.4                        # The brightness of the RGB LED

# PID values
POS_KP = 0.14                           # Position proportional (P) gain
POS_KI = 0.0                            # Position integral (I) gain
POS_KD = 0.0022                         # Position derivative (D) gain


# Free up hardware resources ahead of creating a new Encoder
gc.collect()

# Create a motor and set its speed scale
m = Motor(MOTOR_PINS, direction=DIRECTION, speed_scale=SPEED_SCALE, deadzone=0.05)

# Create an encoder, using PIO 0 and State Machine 0
enc = Encoder(0, 0, ENCODER_PINS, direction=DIRECTION, counts_per_rev=COUNTS_PER_REV, count_microsteps=True)

# Create the LED, using PIO 0 and State Machine 1
led = WS2812(motor2040.NUM_LEDS, 0, 1, motor2040.LED_DATA)

# Create the user button
user_sw = Button(motor2040.USER_SW)

# Create PID object for position control
pos_pid = PID(POS_KP, POS_KI, POS_KD, UPDATE_RATE)

# Start updating the LED
led.start()

# Enable the motor to get started
m.enable()


current_detent = 0


# Function to deal with a detent change
def detent_change(change):
    global current_detent

    # Update the current detent and pid setpoint
    current_detent += change
    pos_pid.setpoint = (current_detent * DETENT_SIZE)     # Update the motor position setpoint
    print("Detent =", current_detent)

    # Convert the current detent to a hue and set the onboard led to it
    hue = (current_detent - MIN_DETENT) / (MAX_DETENT - MIN_DETENT)
    led.set_hsv(0, hue, 1.0, BRIGHTNESS)


# Call the function once to set the setpoint and print the value
detent_change(0)


# Continually move the motor until the user button is pressed
while user_sw.raw() is not True:

    # Capture the state of the encoder
    capture = enc.capture()

    # Get the current detent's centre angle
    detent_angle = (current_detent * DETENT_SIZE)

    # Is the current angle above the region of this detent?
    if capture.degrees > detent_angle + (DETENT_SIZE / 2):
        # Is there another detent we can move to?
        if current_detent < MAX_DETENT:
            detent_change(1)    # Increment to the next detent

    # Is the current angle below the region of this detent?
    elif capture.degrees < detent_angle - (DETENT_SIZE / 2):
        # Is there another detent we can move to?
        if current_detent > MIN_DETENT:
            detent_change(-1)    # Decrement to the next detent

    # Calculate the velocity to move the motor closer to the position setpoint
    vel = pos_pid.calculate(capture.degrees, capture.degrees_per_second)

    # If the current angle is within the detent range, limit the max vel
    # (aka feedback force) that the user will feel when turning the motor between detents
    if (capture.degrees >= MIN_DETENT * DETENT_SIZE) and (capture.degrees <= MAX_DETENT * DETENT_SIZE):
        vel = max(min(vel, MAX_DRIVE_PERCENT), -MAX_DRIVE_PERCENT)

    # Set the new motor driving speed
    m.speed(vel)

    time.sleep(UPDATE_RATE)

# Disable the motor
m.disable()

# Turn off the LED
led.clear()
