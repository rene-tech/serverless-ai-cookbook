"""Reuse upstream ultrasound assets and physics in an independently named scene."""
from i4h_arena.scenes.panda_phantom import PandaPhantomScene


class ProbeCalibrationScene(PandaPhantomScene):
    name = 'probe_calibration'
