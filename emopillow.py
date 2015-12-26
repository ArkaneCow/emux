import blender
import cv2

from moviepy.editor import *

import syncer

from threading import Thread

VIDEO_A = "angry.mp4"
VIDEO_B = "sad.mp4"

OUTPUT_FPS = 10

a = VideoFileClip(VIDEO_A)
b = VideoFileClip(VIDEO_B)

# a_frame = cv2.cvtColor(a.get_frame(6.6), cv2.COLOR_RGB2BGR)
# b_frame = cv2.cvtColor(b.get_frame(6.6), cv2.COLOR_RGB2BGR)
#
# c_frame = blender.generate_midframe(a_frame, b_frame, 0.95)
#
# cv2.imwrite("c_frame.jpg", c_frame)


synced_b = syncer.sync_clips(a, b)

print("done syncing")

time = 0
tstep = 1 / OUTPUT_FPS
frame = 0


def process_frame(a, b, factor, frame):
    frame_a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
    frame_b = cv2.cvtColor(b, cv2.COLOR_RGB2BGR)
    frame_c = blender.generate_midframe(frame_a, frame_b, factor)
    cv2.imwrite("frame" + str(frame) + ".jpg", frame_c)

while time < a.duration:
    print("frame at " + str(time))
    t = Thread(target=process_frame, args=(a.get_frame(time), synced_b.get_frame(time), 1.0, frame,))
    t.start()
    frame += 1
    time += tstep