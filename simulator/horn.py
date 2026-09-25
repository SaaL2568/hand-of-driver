"""Synthesised car horn. Silently does nothing if no audio device is available."""
import numpy as np
import pygame


class Horn:
    def __init__(self):
        self.sound = None
        self.playing = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            freq, size, channels = pygame.mixer.get_init()
            t = np.arange(int(freq * 0.5)) / freq  # 0.5 s loop
            # Two-tone horn (like a real car's dual horn), softened square-ish wave
            wave = np.tanh(3 * np.sin(2 * np.pi * 400 * t)) + np.tanh(3 * np.sin(2 * np.pi * 500 * t))
            wave = (wave / np.abs(wave).max() * 0.35 * 32767).astype(np.int16)
            if channels > 1:
                wave = np.repeat(wave[:, None], channels, axis=1)
            self.sound = pygame.sndarray.make_sound(np.ascontiguousarray(wave))
        except Exception as err:
            print(f"[Horn] Audio unavailable ({err}) - horn is visual only.")

    def set(self, on: bool):
        """Start/stop the looping horn; call every frame with the desired state."""
        if self.sound is None or on == self.playing:
            return
        if on:
            self.sound.play(loops=-1)
        else:
            self.sound.stop()
        self.playing = on
