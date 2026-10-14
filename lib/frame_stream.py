"""Continuous H.264 encoding; no full-timeline tensor or video re-encode on mux."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import wave

import numpy as np
import torch

from .video_export import _ffmpeg_bin, _frames_to_rgb_u8, _even


class FrameStream:
    def __init__(self, root, name, *, width, height, fps, audio_enabled=True):
        self.root, self.name = Path(root), name
        self.width, self.height = _even(width), _even(height)
        self.fps = float(fps)
        self.frames = self.audio_samples = 0
        self.has_audio = False
        self.closed = False
        self.video = self.root / f"{name}.video.mkv"
        self.wav_path = self.root / f"{name}.audio.wav"
        self.errors = (self.root / f"{name}.encoder.log").open("w+b")
        self.wav = None
        self.proc = None
        try:
            if audio_enabled:
                self.wav = wave.open(str(self.wav_path), "wb")
                self.wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            self.proc = subprocess.Popen([
                _ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-threads", "2",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{self.width}x{self.height}",
                "-r", str(self.fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-threads", "2",
                "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18", "-flush_packets", "1",
                str(self.video)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.errors)
        except BaseException:
            self.abort()
            raise

    def append(self, frames, audio=None):
        if self.closed:
            raise RuntimeError("Rolling encoder is already closed")
        h, w = map(int, frames.shape[1:3])
        if h > self.height or w > self.width:
            raise ValueError("Rolling encoder canvas changed unexpectedly")
        try:
            for index in range(int(frames.shape[0])):
                rgb = _frames_to_rgb_u8(frames[index:index + 1])[0]
                if (h, w) != (self.height, self.width):
                    padded = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    y, x = (self.height - h) // 2, (self.width - w) // 2
                    padded[y:y+h, x:x+w] = rgb
                    rgb = padded
                self.proc.stdin.write(memoryview(np.ascontiguousarray(rgb)).cast("B"))
            count = int(frames.shape[0])
            if self.wav is not None:
                # Round the cumulative timeline, not each segment separately.
                target = round((self.frames + count) / self.fps * 48000)
                self._append_audio(audio, target - self.audio_samples)
                self.audio_samples = target
            self.frames += count
        except BaseException:
            self.abort()
            raise

    def _append_audio(self, audio, samples):
        tensor = (audio or {}).get("waveform")
        pcm = b""
        if isinstance(tensor, torch.Tensor) and tensor.numel():
            sr = int(audio.get("sample_rate") or 0)
            if sr <= 0:
                raise ValueError("Rolling audio has an invalid sample rate")
            x = tensor.detach().cpu().float()
            if x.ndim == 2:
                x = x.unsqueeze(0)
            if x.ndim != 3 or x.shape[1] < 1:
                raise ValueError("Rolling audio must be [B,C,T]")
            x = x[0, :2]
            if x.shape[0] == 1:
                x = x.expand(2, -1)
            raw = (x.T.clamp(-1, 1) * 32767).to(torch.int16).contiguous().numpy().astype("<i2", copy=False).tobytes()
            if sr == 48000:
                pcm = raw
            else:
                # Only PCM is resampled; video stays in the persistent encoder.
                result = subprocess.run([_ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
                    "-f", "s16le", "-ar", str(sr), "-ac", "2", "-i", "pipe:0",
                    "-f", "s16le", "-ar", "48000", "-ac", "2", "pipe:1"],
                    input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode:
                    raise RuntimeError(result.stderr.decode(errors="replace")[-2000:])
                pcm = result.stdout
            self.has_audio = True
        length = max(0, samples) * 4
        self.wav.writeframesraw(pcm[:length])
        remaining = length - len(pcm[:length])
        silence = b"\0" * 65536
        while remaining > 0:
            chunk = min(remaining, len(silence))
            self.wav.writeframesraw(silence[:chunk])
            remaining -= chunk

    def _close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
                self.proc.stdin = None
            self.proc.wait(timeout=3600)
            if self.proc.returncode:
                self.errors.seek(0)
                raise RuntimeError("Rolling video encoder failed: " + self.errors.read().decode(errors="replace")[-2000:])
        except BaseException:
            if self.proc and self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait()
            raise
        finally:
            try:
                if self.wav:
                    self.wav.close()
            finally:
                self.wav = None
                self.errors.close()

    def finish(self):
        self._close()
        dest = self.root / f"{self.name}.mp4"
        staging = self.root / f".{self.name}.mux.mp4"
        command = [_ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(self.video)]
        if self.has_audio:
            command += ["-i", str(self.wav_path)]
        command += ["-map", "0:v:0", "-c:v", "copy"]
        if self.has_audio:
            command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-af", "apad"]
        else:
            command += ["-an"]
        command += ["-t", f"{self.frames / self.fps:.9f}", "-movflags", "+faststart", str(staging)]
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError("Rolling mux failed: " + result.stderr.decode(errors="replace")[-2000:])
        os.replace(staging, dest)
        self.video.unlink(missing_ok=True)
        self.wav_path.unlink(missing_ok=True)
        return dest

    def abort(self):
        if self.proc and self.proc.poll() is None:
            # Close gracefully so already-written Matroska packets remain usable.
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                    self.proc.stdin = None
                self.proc.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait()
        if self.wav:
            try:
                self.wav.close()
            except OSError:
                pass  # Preserve the original failure (e.g. a full disk).
            finally:
                self.wav = None
        if not self.errors.closed:
            self.errors.close()
        self.closed = True
