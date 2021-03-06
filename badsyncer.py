import scipy.signal as signal
import scipy.io.wavfile as wav

import numpy
import cv2

import itertools
from scipy.fftpack import dct

from audiofiles import utility

from moviepy.editor import *

FIT_THRESHOLD = 5.0

MIN_MATCH_NUM = 4
MAX_MATCH_NUM = 4

SPEC_MAX = 2500
SPEC_MIN = -3000

detector = cv2.ORB_create()
matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

def mel(hertz):
    return 1125 * numpy.log(1 + hertz/ 700)
def mel_inv(mels):
    return 700 * (numpy.exp(mels / 1125) - 1)
def filterbanks(low, high, num):
    return [mel_inv(x) for x in range(int(mel(low)), int(mel(high)), int((mel(high) - mel(low)) / (num - 1)))]
def hf(f, m, k):
    if k < f[max(0, m - 1)]:
        return 0
    elif k >= f[m - 1] and k < f[m]:
        return (k - f[m - 1]) / (f[m] - f[m - 1])
    elif k >= f[m] and k < f[m + 1]:
        return (f[m + 1] - k) / (f[m + 1] - f[m])
    elif k >= f[min(len(f) - 1, m + 1)]:
        return 0
    else:
        return 0

def to_mfcc(r, specgram):
    frame_banks = [int(((specgram.size + 1) * x) / r) for x in filterbanks(200, 12000, 8)]
    max_bank = numpy.max(numpy.asarray(frame_banks))
    frame_mels = list(itertools.starmap(lambda x, y : hf(frame_banks, x, y) * specgram[y], itertools.product(range(len(frame_banks)), range(max_bank))))
    frame_ampl = [numpy.log(numpy.sum(x)) if x != 0 else 0 for x in frame_mels]
    return dct(frame_ampl, axis=0)

class SignalFinder(object):
    def __init__(self, r, s):
        self.r = r
        self.s = s
        self.fingers = None

    @staticmethod
    def generate_spectrogram(r, s):
        specgram = signal.spectrogram(s, fs=r)
        spec = numpy.asarray([to_mfcc(r, f) for f in specgram[2].transpose()])
        print(numpy.min(spec))
        print(numpy.max(spec))
        spec[spec == -numpy.inf] = 0
        spec = numpy.clip(spec, SPEC_MIN, SPEC_MAX)
        spec -= SPEC_MIN
        spec /= (SPEC_MAX - SPEC_MIN)
        spec *= 255
        spec = spec.astype(dtype=numpy.uint8)
        spec = spec.transpose()
        return (specgram[0], specgram[1], spec)

    @staticmethod
    def get_finger(r, s):
        specgram = SignalFinder.generate_spectrogram(r, s)
        # time and keypoints
        return (specgram[0], specgram[1], detector.detectAndCompute(specgram[2], None))

    def train_fingers(self):
        self.fingers = SignalFinder.get_finger(self.r, self.s)

    def find_signal(self, r, s):
        if self.fingers is None:
            self.train_fingers()
        query = SignalFinder.get_finger(r, s)
        f1 = query[0]
        t1 = query[1]
        kp1 = query[2][0]
        des1 = query[2][1]
        f2 = self.fingers[0]
        t2 = self.fingers[1]
        kp2 = self.fingers[2][0]
        des2 = self.fingers[2][1]
        matches = matcher.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)[:MAX_MATCH_NUM]
        if len(matches) < MIN_MATCH_NUM:
            return (0, 0) # use actual exceptions
        src_pts = numpy.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = numpy.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, FIT_THRESHOLD)
        h = f1.size
        w = t1.size
        pts = numpy.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(pts, M)
        times = numpy.clip(sorted([d[0][0] for d in dst]), 0, t2.size - 1)
        ti = int(times[0])
        tf = int(times[-1])
        timestart = t2[ti]
        timelength = t2[tf] - t2[ti]
        return (timestart, timelength)

def stereo_to_mono(s):
    return utility.float2pcm(numpy.mean(s, axis = 1))

def sync_clips(a, b, t):
    b_audio = stereo_to_mono(b.audio.to_soundarray())
    b_r = b.audio.fps
    sm = SignalFinder(b_r, b_audio)
    sm.train_fingers()
    time = a.duration
    clips = []
    clip_start = 0
    while time > 0:
        clip_length = min(time, t)
        a_clip = a.subclip(clip_start, clip_start + clip_length)
        a_audio = stereo_to_mono(a_clip.audio.to_soundarray())
        a_r = a_clip.audio.fps
        ati, atd = sm.find_signal(a_r, a_audio)
        b_match = None
        if atd == 0:
            b_match = a_clip
        else:
            b_match = b.subclip(ati, ati + atd).speedx(atd / clip_length)
        clips.append(b_match)
        print("a: " + str(clip_start) + " - " + str(clip_length) + " b: " + str(ati) + " - " + str(atd))
        clip_start += clip_length
        time -= clip_length
    synced = concatenate(clips)
    return synced
r1, s1 = wav.read('angry.wav')
r2, s2 = wav.read('sad.wav')
s1 = s1[:23000]
cv2.imwrite('1.jpg', SignalFinder.generate_spectrogram(r1, s1)[2])
cv2.imwrite('2.jpg', SignalFinder.generate_spectrogram(r2, s2)[2])
sm = SignalFinder(r2, s2)
sm.train_fingers()
print(sm.find_signal(r1, s1))
angry = VideoFileClip('angry.mp4')
sad = VideoFileClip('sad.mp4')
sad_sync = sync_clips(angry, sad, 1)
sad_sync.set_audio(angry.audio).write_videofile('sadsync.mp4')