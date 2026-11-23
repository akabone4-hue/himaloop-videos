"""engine.py — 物理シミュレーション動画の共通部品（描画・音・書き出し）

縦 1080x1920 / 60fps の動画を pygame で 1 コマずつ描き、ffmpeg に流し込んで mp4 にします。
音はすべてこのファイル内で合成するので、外部の音源・素材は使いません。
物理は常に 240Hz で進めるため、プレビュー(30fps)でも本番(60fps)でも同じ展開になります。
"""

import colorsys
import math
import os
import subprocess
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np          # noqa: E402
import pygame               # noqa: E402
from pygame import gfxdraw  # noqa: E402

W, H = 1080, 1920
SR = 44100
PHYS_HZ = 240
CX, CY = W // 2, 930        # 画面下はアプリのUIに隠れるので、中心を少し上に置く


# ---------------------------------------------------------------- colors
def hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return int(r * 255), int(g * 255), int(b * 255)


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def midi_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


PENTA = [0, 2, 4, 7, 9]


def penta(i, base=60):
    """ペンタトニック音階の i 番目（どう鳴らしても濁らない）。"""
    return base + 12 * (i // 5) + PENTA[i % 5]


# ---------------------------------------------------------------- audio
def _env(n, attack=0.004):
    a = max(1, int(attack * SR))
    e = np.ones(n, dtype=np.float32)
    e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    return e


def synth_pluck(freq):
    n = int(0.9 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    w = (np.sin(2 * np.pi * freq * t) * np.exp(-5.0 * t)
         + 0.5 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-9.0 * t)
         + 0.22 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-16.0 * t))
    return (w * _env(n)).astype(np.float32) / 1.4


def synth_piano(freq):
    n = int(1.6 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    w = np.zeros(n, dtype=np.float32)
    for k, amp in enumerate([1.0, 0.55, 0.3, 0.18, 0.1, 0.06], start=1):
        w += amp * np.sin(2 * np.pi * freq * k * t * (1 + 0.0004 * k * k)) * np.exp(-(2.2 + 0.9 * k) * t)
    return (w * _env(n, 0.003)).astype(np.float32) / 1.9


def synth_marimba(freq):
    """木琴のような丸い音（倍音は 1 : 4 : 10）。跳ねる音を続けて鳴らしても耳に刺さらない。"""
    n = int(1.0 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    w = (np.sin(2 * np.pi * freq * t) * np.exp(-4.2 * t)
         + 0.22 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-15.0 * t)
         + 0.06 * np.sin(2 * np.pi * 10 * freq * t) * np.exp(-34.0 * t))
    return (w * _env(n, 0.006)).astype(np.float32) / 1.25


# 跳ねる音に使う分散和音（C → G → Am → F）。でたらめな高さで鳴らすより、曲の伴奏のように聞こえる。
ARP_PROG = [[60, 64, 67, 72, 76], [55, 59, 62, 67, 71], [57, 60, 64, 69, 72], [53, 57, 60, 65, 69]]
ARP_PAT = [0, 1, 2, 3, 4, 3, 2, 1]


def synth_glock(freq):
    """鉄琴の澄んだ音（倍音は 1 : 2.76 : 5.4。金属の棒の鳴り方）。"""
    n = int(1.5 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    w = (np.sin(2 * np.pi * freq * t) * np.exp(-3.2 * t)
         + 0.42 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-7.0 * t)
         + 0.16 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-14.0 * t))
    return (w * _env(n, 0.002)).astype(np.float32) / 1.5


def synth_wood(freq):
    """木のコースに玉が当たる「コツッ」という短い音。"""
    n = int(0.12 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(int(freq))
    noise = rng.standard_normal(n).astype(np.float32) * np.exp(-220 * t) * 0.25
    w = (np.sin(2 * np.pi * freq * t) * np.exp(-55 * t)
         + 0.45 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-90 * t) + noise)
    return (w * _env(n, 0.001)).astype(np.float32) / 1.4


def synth_thud(freq):
    n = int(0.22 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = freq * (0.45 + 0.55 * np.exp(-28 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    rng = np.random.default_rng(int(freq))
    noise = rng.standard_normal(n).astype(np.float32) * np.exp(-90 * t) * 0.35
    return ((np.sin(phase) * np.exp(-16 * t) + noise) * _env(n, 0.002)).astype(np.float32)


def synth_pop(freq):
    n = int(0.16 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = freq * (1 + 1.2 * np.minimum(t / 0.05, 1.0))
    phase = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(phase) * np.exp(-26 * t) * _env(n, 0.002)).astype(np.float32)


def synth_click(freq):
    n = int(0.07 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    return (np.sin(2 * np.pi * freq * t) * np.exp(-70 * t) * _env(n, 0.001)).astype(np.float32)


SYNTH = {"pluck": synth_pluck, "marimba": synth_marimba, "glock": synth_glock, "wood": synth_wood, "piano": synth_piano, "thud": synth_thud, "pop": synth_pop, "click": synth_click}


class Audio:
    def __init__(self):
        self.events = []      # (時刻, 種類, 周波数, 音量, 長さ)
        self._last = {}

    def play(self, t, freq, vol=0.5, kind="pluck", channel=None, min_gap=0.0, dur=None):
        """channel を指定すると、そのチャンネルで min_gap 秒以内の連打を間引く。
        dur を指定すると、その秒数のあと音をすばやく消す（旋律で前の音が残って濁らないように）。"""
        if channel is not None:
            if t - self._last.get(channel, -99.0) < min_gap:
                return False
            self._last[channel] = t
        self.events.append((float(t), kind, float(freq), float(vol), dur))
        return True

    def note(self, t, midi, vol=0.5, kind="pluck", **kw):
        return self.play(t, midi_hz(midi), vol, kind, **kw)

    def render(self, duration):
        n = int((duration + 2.0) * SR)
        buf = np.zeros(n, dtype=np.float32)
        cache = {}
        for t, kind, freq, vol, dur in self.events:
            key = (kind, round(freq, 1))
            if key not in cache:
                cache[key] = SYNTH[kind](freq)
            wv = cache[key]
            if dur is not None and int(dur * SR) < len(wv):
                k = int(dur * SR)
                wv = wv.copy()
                wv[k:] *= np.exp(-np.arange(len(wv) - k, dtype=np.float32) / (0.07 * SR))
            i = int(t * SR)
            if i >= n or i < 0:
                continue
            j = min(n, i + len(wv))
            buf[i:j] += wv[: j - i] * vol
        buf = buf[: int(duration * SR)]
        ref = float(np.percentile(np.abs(buf), 99.9)) if len(buf) else 0.0
        if ref > 1e-6:
            buf = np.tanh(buf * (0.9 / ref)) * 0.85     # 重なりすぎた部分だけやわらかく潰す
        return buf


# ---------------------------------------------------------------- video
class Video:
    def __init__(self, out_path, fps=60, preview=False, dry=False):
        self.out_path = out_path
        self.fps = fps
        self.sub = PHYS_HZ // fps          # 1 コマあたりの物理ステップ数
        self.dt = 1.0 / PHYS_HZ
        self.dry = dry                     # True: 物理だけ回して長さを測る（描画・書き出しなし）
        self.frames = 0
        self.audio = Audio()
        self.proc = None
        if dry:
            return
        pygame.font.init()
        self.surf = pygame.Surface((W, H))
        self.trail = pygame.Surface((W, H))
        self.trail.fill((0, 0, 0))
        self._fonts = {}
        self._tmp_video = out_path + ".v.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-an"]
        if preview:
            cmd += ["-vf", "scale=540:960", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17"]
        cmd += ["-pix_fmt", "yuv420p", self._tmp_video]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    @property
    def t(self):
        return self.frames / self.fps

    # ---- frame lifecycle
    def begin(self, bg=(0, 0, 0), fade=None):
        """1 コマの描き始め。fade を指定すると残像レイヤーを薄めてから背景に重ねる。"""
        if self.dry:
            return
        self.surf.fill(bg)
        if fade is not None:
            k = int(255 * fade)
            self.trail.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
            # 掛け算だけだと暗い色が 0 まで下がりきらず、通った跡がうっすら残り続ける。少し引いて完全に消す
            self.trail.fill((3, 3, 3), special_flags=pygame.BLEND_RGB_SUB)
            self.surf.blit(self.trail, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def end(self, glow=0.5):
        """1 コマを書き出す。glow は光のにじみの強さ（0 でなし）。"""
        self.frames += 1
        if self.dry:
            return
        out = self.surf
        if glow > 0:
            small = pygame.transform.smoothscale(self.surf, (W // 8, H // 8))
            small = pygame.transform.smoothscale(small, (W // 16, H // 16))
            blur = pygame.transform.smoothscale(small, (W, H))
            k = int(255 * glow)
            blur.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
            out = self.surf.copy()
            out.blit(blur, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.proc.stdin.write(pygame.image.tobytes(out, "RGB"))

    def finish(self):
        duration = self.frames / self.fps
        if self.dry:
            return duration
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg (video) failed")
        pcm = (self.audio.render(duration) * 32767).astype(np.int16)
        wav_path = self.out_path + ".a.wav"
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", self._tmp_video, "-i", wav_path,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest",
                        "-movflags", "+faststart", self.out_path], check=True)
        os.remove(self._tmp_video)
        os.remove(wav_path)
        return duration

    # ---- drawing helpers (dry のときは何もしない)
    def font(self, size):
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    def text(self, s, size, center, color=(255, 255, 255), outline=4, target=None, alpha=255):
        """白文字＋黒フチの字幕。"""
        if self.dry:
            return
        target = target or self.surf
        f = self.font(size)
        img = f.render(s, True, color)
        rect = img.get_rect(center=(int(center[0]), int(center[1])))
        if outline:
            dark = f.render(s, True, (0, 0, 0))
            for dx in (-outline, 0, outline):
                for dy in (-outline, 0, outline):
                    if dx or dy:
                        target.blit(dark, rect.move(dx, dy))
        if alpha < 255:
            img.set_alpha(alpha)
        target.blit(img, rect)

    def circle(self, color, pos, r, target=None, outline=None, width=0):
        if self.dry:
            return
        target = target or self.surf
        x, y, r = int(pos[0]), int(pos[1]), int(r)
        if r < 1 or x < -r - 50 or x > W + r + 50 or y < -r - 50 or y > H + r + 50:
            return
        if width:                       # 輪郭だけ
            pygame.draw.circle(target, color, (x, y), r, width)
            gfxdraw.aacircle(target, x, y, r, color)
            return
        gfxdraw.filled_circle(target, x, y, r, color)
        gfxdraw.aacircle(target, x, y, r, color)
        if outline:
            gfxdraw.aacircle(target, x, y, r, outline)
            if r > 3:
                gfxdraw.aacircle(target, x, y, r - 1, outline)

    def arc_band(self, color, center, r_in, r_out, a0, a1, target=None):
        """a0→a1（ラジアン）の太い円弧。すき間のあるリングに使う。"""
        if self.dry:
            return
        target = target or self.surf
        steps = max(6, int(abs(a1 - a0) * r_out / 10))
        pts = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((center[0] + math.cos(a) * r_out, center[1] + math.sin(a) * r_out))
        for i in range(steps, -1, -1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((center[0] + math.cos(a) * r_in, center[1] + math.sin(a) * r_in))
        gfxdraw.filled_polygon(target, pts, color)
        gfxdraw.aapolygon(target, pts, color)

    def line(self, color, p1, p2, width=1, target=None):
        if self.dry:
            return
        target = target or self.surf
        if width <= 1:
            pygame.draw.aaline(target, color, p1, p2)
        else:
            pygame.draw.line(target, color, p1, p2, width)


# ---------------------------------------------------------------- particles
class Particles:
    def __init__(self):
        self.items = []     # [x, y, vx, vy, life, max_life, color, size]

    def burst(self, rng, pos, color, n=14, speed=420, life=0.6, size=5, gravity=True):
        for _ in range(n):
            a = rng.uniform(0, math.tau)
            s = rng.uniform(0.3, 1.0) * speed
            self.items.append([pos[0], pos[1], math.cos(a) * s, math.sin(a) * s,
                               life * rng.uniform(0.6, 1.0), life, color, size * rng.uniform(0.6, 1.2), gravity])

    def step(self, dt):
        alive = []
        for p in self.items:
            p[4] -= dt
            if p[4] <= 0:
                continue
            if p[8]:
                p[3] += 900 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            alive.append(p)
        self.items = alive

    def draw(self, v, target=None, offset=(0, 0)):
        if v.dry:
            return
        for p in self.items:
            k = p[4] / p[5]
            v.circle(mix((0, 0, 0), p[6], k), (p[0] - offset[0], p[1] - offset[1]), max(1, p[7] * k), target=target)


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi
