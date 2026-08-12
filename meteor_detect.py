#!/usr/bin/env python3
"""Live spectrum and state-based meteor detection for WAV files and Twitch."""

from __future__ import annotations

import argparse
import csv
import logging
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator

import numpy as np

EPSILON = np.finfo(np.float64).tiny
OUTPUT_DIR = Path("out")

SIGNAL_BAND = (950.0, 1050.0)
NOISE_1_BAND = (750.0, 850.0)
NOISE_2_BAND = (1150.0, 1250.0)
DETECTION_BANDS = (
    ("Signal", SIGNAL_BAND, "tab:green"),
    ("Noise 1", NOISE_1_BAND, "tab:cyan"),
    ("Noise 2", NOISE_2_BAND, "tab:purple"),
)


def shifted_detection_bands(
        frequency_offset_hz: float,
) -> tuple[tuple[str, tuple[float, float], str], ...]:
    """Shift all detection bands by the same frequency offset."""
    return tuple(
        (
            name,
            (lower + frequency_offset_hz, upper + frequency_offset_hz),
            color,
        )
        for name, (lower, upper), color in DETECTION_BANDS
    )


def pcm_to_float(data: bytes, sample_width: int, channels: int) -> np.ndarray:
    """Convert little-endian PCM frames to mono float32 in the range [-1, 1]."""
    if sample_width == 1:
        samples = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(data, dtype=np.uint8)
        raw = raw[: raw.size - raw.size % 3].reshape(-1, 3)
        values = (
                raw[:, 0].astype(np.int32)
                | (raw[:, 1].astype(np.int32) << 8)
                | (raw[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        samples = values.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        samples = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Nicht unterstützte PCM-Bittiefe: {sample_width * 8} Bit")

    samples = samples[: samples.size - samples.size % channels]
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32, copy=False)


class WavSource(AbstractContextManager["WavSource"]):
    def __init__(self, filename: str, chunk_frames: int, realtime: bool) -> None:
        self.filename = filename
        self.chunk_frames = chunk_frames
        self.realtime = realtime
        self.wav: wave.Wave_read | None = None
        self.sample_rate = 0
        self.channels = 0
        self.sample_width = 0

    def __enter__(self) -> "WavSource":
        self.wav = wave.open(self.filename, "rb")
        if self.wav.getcomptype() != "NONE":
            raise ValueError("Nur unkomprimierte PCM-WAV-Dateien werden unterstützt")
        self.sample_rate = self.wav.getframerate()
        self.channels = self.wav.getnchannels()
        self.sample_width = self.wav.getsampwidth()
        return self

    def chunks(self) -> Iterator[np.ndarray]:
        assert self.wav is not None
        deadline = time.monotonic()
        while data := self.wav.readframes(self.chunk_frames):
            chunk = pcm_to_float(data, self.sample_width, self.channels)
            if chunk.size:
                yield chunk
            if self.realtime:
                deadline += len(chunk) / self.sample_rate
                time.sleep(max(0.0, deadline - time.monotonic()))

    def __exit__(self, *exc: object) -> None:
        if self.wav is not None:
            self.wav.close()


class TwitchSource(AbstractContextManager["TwitchSource"]):
    def __init__(
            self,
            channel: str,
            sample_rate: int,
            chunk_frames: int,
            quality: str,
            retry_delay: float,
            stall_timeout: float,
            logger: logging.Logger,
    ) -> None:
        self.url = channel if "://" in channel else f"https://twitch.tv/{channel}"
        self.sample_rate = sample_rate
        self.chunk_frames = chunk_frames
        self.quality = quality
        self.retry_delay = retry_delay
        self.stall_timeout = stall_timeout
        self.logger = logger
        self.streamlink: subprocess.Popen[bytes] | None = None
        self.ffmpeg: subprocess.Popen[bytes] | None = None
        self.streamlink_stderr = None
        self.ffmpeg_stderr = None
        self.started_at = time.monotonic()
        self.connected_at: float | None = None
        self.outage_started_at: float | None = None
        self.interruptions = 0
        self.total_downtime = 0.0

    def __enter__(self) -> "TwitchSource":
        for program in ("streamlink", "ffmpeg"):
            if shutil.which(program) is None:
                raise RuntimeError(
                    f"'{program}' wurde nicht gefunden. Unter macOS: brew install {program}"
                )

        self.logger.info("Twitch-Überwachung gestartet: %s", self.url)
        return self

    def _start_pipeline(self) -> None:
        self.streamlink_stderr = tempfile.TemporaryFile()
        self.ffmpeg_stderr = tempfile.TemporaryFile()
        self.streamlink = subprocess.Popen(
            ["streamlink", "--stdout", self.url, self.quality],
            stdout=subprocess.PIPE,
            stderr=self.streamlink_stderr,
        )
        assert self.streamlink.stdout is not None
        self.ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-vn",
                "-ac", "1", "-ar", str(self.sample_rate), "-f", "f32le", "pipe:1",
            ],
            stdin=self.streamlink.stdout,
            stdout=subprocess.PIPE,
            stderr=self.ffmpeg_stderr,
        )
        self.streamlink.stdout.close()

    @staticmethod
    def _read_error_file(error_file: object) -> str:
        if error_file is None:
            return ""
        try:
            error_file.seek(0)  # type: ignore[attr-defined]
            return error_file.read().decode(errors="replace").strip()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            return ""

    def _pipeline_error(self) -> str:
        details = [
            self._read_error_file(self.streamlink_stderr),
            self._read_error_file(self.ffmpeg_stderr),
        ]
        return " | ".join(detail for detail in details if detail)

    def _stop_pipeline(self) -> None:
        for process in (self.ffmpeg, self.streamlink):
            if process is not None and process.poll() is None:
                process.terminate()
        for process in (self.ffmpeg, self.streamlink):
            if process is not None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for error_file in (self.streamlink_stderr, self.ffmpeg_stderr):
            if error_file is not None:
                error_file.close()
        self.streamlink = None
        self.ffmpeg = None
        self.streamlink_stderr = None
        self.ffmpeg_stderr = None

    def _pipeline_chunks(self) -> Iterator[np.ndarray]:
        assert self.ffmpeg is not None and self.ffmpeg.stdout is not None
        wanted = self.chunk_frames * 4
        audio_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=16)
        stop_reader = threading.Event()
        heartbeat = np.empty(0, dtype=np.float32)
        last_audio = time.monotonic()

        def put_audio(chunk: np.ndarray | None) -> None:
            while not stop_reader.is_set():
                try:
                    audio_queue.put(chunk, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def read_audio() -> None:
            try:
                while not stop_reader.is_set():
                    data = self.ffmpeg.stdout.read(wanted)
                    if not data:
                        break
                    chunk = np.frombuffer(data, dtype="<f4").copy()
                    if chunk.size:
                        put_audio(chunk)
            finally:
                put_audio(None)

        reader = threading.Thread(
            target=read_audio,
            name="twitch-audio-reader",
            daemon=True,
        )
        reader.start()

        # HLS audio arrives in bursts. Read it in the background and emit it at
        # audio speed, so network waits never block Matplotlib's event loop.
        next_chunk = time.monotonic()
        try:
            while True:
                delay = next_chunk - time.monotonic()
                if delay > 0:
                    stop_reader.wait(min(delay, 0.02))
                    yield heartbeat
                    continue

                try:
                    chunk = audio_queue.get(timeout=0.02)
                except queue.Empty:
                    if time.monotonic() - last_audio >= self.stall_timeout:
                        raise RuntimeError(
                            f"Seit {self.stall_timeout:g} s keine Audiodaten empfangen"
                        )
                    yield heartbeat
                    continue

                if chunk is None:
                    break
                last_audio = time.monotonic()
                next_chunk = max(next_chunk, time.monotonic()) + (
                        chunk.size / self.sample_rate
                )
                yield chunk
        finally:
            stop_reader.set()
            reader.join(timeout=0.2)

        # Give both processes a moment to publish their exit status and errors.
        for process in (self.ffmpeg, self.streamlink):
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
        streamlink_failed = self.streamlink is not None and self.streamlink.poll() not in (None, 0)
        ffmpeg_failed = self.ffmpeg.poll() not in (None, 0)
        detail = self._pipeline_error()
        if ffmpeg_failed or streamlink_failed:
            raise RuntimeError(detail or "Twitch-Stream konnte nicht gelesen werden")
        raise RuntimeError(detail or "Twitch-Stream wurde beendet")

    def chunks(self) -> Iterator[np.ndarray]:
        heartbeat = np.empty(0, dtype=np.float32)
        attempt = 0
        while True:
            attempt += 1
            received_audio = False
            try:
                self.logger.info("Verbindungsversuch %d", attempt)
                self._start_pipeline()
                for chunk in self._pipeline_chunks():
                    if chunk.size and not received_audio:
                        received_audio = True
                        now = time.monotonic()
                        if self.connected_at is None:
                            self.logger.info("Twitch-Stream läuft; Audiodaten werden empfangen")
                        else:
                            downtime = now - (self.outage_started_at or now)
                            self.total_downtime += downtime
                            self.logger.info(
                                "Twitch-Stream fortgesetzt nach %.1f s Unterbrechung",
                                downtime,
                            )
                        self.connected_at = now
                        self.outage_started_at = None
                        attempt = 0
                    yield chunk
            except (OSError, RuntimeError) as error:
                if self.outage_started_at is None:
                    self.outage_started_at = time.monotonic()
                    if self.connected_at is not None:
                        self.interruptions += 1
                self.logger.error(
                    "Twitch-Stream unterbrochen/nicht erreichbar: %s", error
                )
            finally:
                self._stop_pipeline()

            self.logger.info(
                "Automatischer Neuversuch in %.1f s", self.retry_delay
            )
            retry_at = time.monotonic() + self.retry_delay
            while time.monotonic() < retry_at:
                yield heartbeat
                time.sleep(min(0.02, max(0.0, retry_at - time.monotonic())))

    def __exit__(self, *exc: object) -> None:
        self._stop_pipeline()
        runtime = time.monotonic() - self.started_at
        current_downtime = 0.0
        if self.outage_started_at is not None:
            current_downtime = time.monotonic() - self.outage_started_at
        self.logger.info(
            "Twitch-Report: Laufzeit %.1f s, Unterbrechungen %d, "
            "gesamte Ausfallzeit %.1f s",
            runtime,
            self.interruptions,
            self.total_downtime + current_downtime,
        )


class RollingSpectrum:
    def __init__(
            self,
            sample_rate: int,
            fft_size: int,
            hop_size: int,
            history: float,
            keep_history: bool = True,
    ) -> None:
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.hop_size = hop_size
        self.history = history
        self.keep_history = keep_history
        self.window = np.hanning(fft_size).astype(np.float32)
        self.normalization = sample_rate * float(np.sum(self.window ** 2))
        self.buffer = np.empty(0, dtype=np.float32)
        max_columns = max(2, int(np.ceil(history * sample_rate / hop_size)))
        self.columns: deque[np.ndarray] = deque(maxlen=max_columns)

    def add(self, samples: np.ndarray) -> list[np.ndarray]:
        added: list[np.ndarray] = []
        self.buffer = np.concatenate((self.buffer, samples))
        while self.buffer.size >= self.fft_size:
            frame = self.buffer[: self.fft_size]
            spectrum = np.fft.rfft(frame * self.window)
            psd = np.abs(spectrum) ** 2 / self.normalization
            if self.fft_size % 2 == 0:
                psd[1:-1] *= 2.0
            else:
                psd[1:] *= 2.0
            if self.keep_history:
                self.columns.append(psd)
            added.append(psd)
            self.buffer = self.buffer[self.hop_size:]
        return added

    def matrix(self) -> np.ndarray | None:
        if not self.columns:
            return None
        return np.column_stack(self.columns)


class DetectionState(Enum):
    ESTIMATE_THRESHOLD = "Schwellwert abschätzen"
    DETECT = "Detektieren"
    PAUSED = "Detektion ausgesetzt"
    EVENT = "Event aktiv"


@dataclass(frozen=True)
class DetectionMeasurement:
    elapsed: float
    signal_db: float
    noise_1_db: float
    noise_2_db: float
    snr_db: float
    threshold_db: float
    state: DetectionState


@dataclass(frozen=True)
class MeteorEvent:
    start_elapsed: float
    stop_elapsed: float
    start_time: datetime
    stop_time: datetime
    snr_mean_db: float
    snr_max_db: float
    discarded: bool


class MeteorDetector:
    """Zustandsautomat aus dem Detektionsdiagramm."""

    def __init__(
            self,
            frequencies: np.ndarray,
            hop_seconds: float,
            threshold_window: float,
            threshold_sigma: float,
            noise_tolerance_db: float,
            event_timeout: float,
            event_threshold_offset_db: float,
            threshold_freeze: float,
            frequency_offset_hz: float,
            event_csv: Path,
            logger: logging.Logger,
    ) -> None:
        self.hop_seconds = hop_seconds
        self.threshold_window = threshold_window
        self.threshold_sigma = threshold_sigma
        self.noise_tolerance_db = noise_tolerance_db
        self.event_timeout = event_timeout
        self.event_threshold_offset_db = event_threshold_offset_db
        self.threshold_freeze = threshold_freeze
        self.frequency_offset_hz = frequency_offset_hz
        self.logger = logger
        self.elapsed = 0.0
        self.state = DetectionState.ESTIMATE_THRESHOLD
        self.baseline: deque[float] = deque(
            maxlen=max(2, int(np.ceil(threshold_window / hop_seconds)))
        )
        self.event_started_at: float | None = None
        self.event_started_wall: datetime | None = None
        self.event_snrs: list[float] = []
        self.baseline_frozen_until = 0.0
        self.events: deque[MeteorEvent] = deque(maxlen=1000)
        self.event_csv = self._create_event_csv(event_csv)
        self.logger.info("Neue Event-CSV angelegt: %s", self.event_csv)

        self.df = float(frequencies[1] - frequencies[0])
        shifted_bands = shifted_detection_bands(frequency_offset_hz)
        masks = tuple(
            (frequencies >= band[0]) & (frequencies <= band[1])
            for _, band, _ in shifted_bands
        )
        self.signal_mask, self.noise_1_mask, self.noise_2_mask = masks
        if not all(mask.any() for mask in (
                self.signal_mask, self.noise_1_mask, self.noise_2_mask
        )):
            lower_frequency = min(band[0] for _, band, _ in shifted_bands)
            upper_frequency = max(band[1] for _, band, _ in shifted_bands)
            raise ValueError(
                "FFT/Aufnahmerate kann die Detektionsbänder "
                f"{lower_frequency:g}–{upper_frequency:g} Hz nicht auflösen"
            )
        self.logger.info(
            "Gemeinsamer Frequenz-Offset: %+.3f Hz", self.frequency_offset_hz
        )
        self.logger.info("Zustand: %s", self.state.value)

    @staticmethod
    def _csv_fields() -> list[str]:
        return [
            "start_time", "stop_time", "start_seconds", "stop_seconds",
            "duration_seconds", "snr_mean_db", "snr_max_db", "status",
        ]

    @classmethod
    def _create_event_csv(cls, base_path: Path) -> Path:
        base_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = base_path.suffix or ".csv"
        stem = base_path.stem if base_path.suffix else base_path.name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f_UTC")
        sequence = 0
        while True:
            counter = "" if sequence == 0 else f"_{sequence}"
            event_csv = base_path.parent / f"{stem}_{timestamp}{counter}{suffix}"
            try:
                with event_csv.open("x", newline="", encoding="utf-8") as csv_file:
                    csv.DictWriter(
                        csv_file, fieldnames=cls._csv_fields()
                    ).writeheader()
                return event_csv
            except FileExistsError:
                sequence += 1

    def _write_event(self, event: MeteorEvent) -> None:
        with self.event_csv.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self._csv_fields())
            writer.writerow({
                "start_time": event.start_time.isoformat(timespec="milliseconds"),
                "stop_time": event.stop_time.isoformat(timespec="milliseconds"),
                "start_seconds": f"{event.start_elapsed:.3f}",
                "stop_seconds": f"{event.stop_elapsed:.3f}",
                "duration_seconds": f"{event.stop_elapsed - event.start_elapsed:.3f}",
                "snr_mean_db": f"{event.snr_mean_db:.3f}",
                "snr_max_db": f"{event.snr_max_db:.3f}",
                "status": "discarded_timeout" if event.discarded else "detected",
            })
            csv_file.flush()

    def _band_db(self, psd: np.ndarray, mask: np.ndarray) -> float:
        power = float(np.sum(psd[mask]) * self.df)
        return 10.0 * np.log10(max(power, EPSILON))

    def _set_state(self, state: DetectionState, reason: str) -> None:
        if state is self.state:
            return
        previous = self.state
        self.state = state
        self.logger.info(
            "Zustand: %s -> %s (%s)", previous.value, state.value, reason
        )

    def _threshold(self) -> float:
        if len(self.baseline) < self.baseline.maxlen:
            return np.nan
        values = np.asarray(self.baseline, dtype=np.float64)
        return float(values.mean() + self.threshold_sigma * values.std())

    def _finish_event(self, discarded: bool) -> None:
        assert self.event_started_at is not None
        assert self.event_started_wall is not None
        duration = self.elapsed - self.event_started_at
        snrs = np.asarray(self.event_snrs, dtype=np.float64)
        event = MeteorEvent(
            start_elapsed=self.event_started_at,
            stop_elapsed=self.elapsed,
            start_time=self.event_started_wall,
            stop_time=datetime.now(timezone.utc),
            snr_mean_db=float(snrs.mean()),
            snr_max_db=float(snrs.max()),
            discarded=discarded,
        )
        self.events.append(event)
        self._write_event(event)
        if discarded:
            self.logger.warning(
                "Event verworfen: start=%.3fs dauer=%.3fs grund=Timeout",
                self.event_started_at, duration,
            )
        else:
            self.logger.info(
                "Event beendet: start=%.3fs stop=%.3fs dauer=%.3fs "
                "snr_mittel=%.3fdB snr_max=%.3fdB",
                self.event_started_at, self.elapsed, duration,
                float(snrs.mean()), float(snrs.max()),
            )
        self.event_started_at = None
        self.event_started_wall = None
        self.event_snrs = []
        self.baseline_frozen_until = self.elapsed + self.threshold_freeze
        self.logger.info(
            "Schwellwert bis %.3fs eingefroren (%.1f s Nachlauf)",
            self.baseline_frozen_until, self.threshold_freeze,
        )
        self._set_state(DetectionState.DETECT, "Event abgeschlossen")

    def process(self, psd: np.ndarray) -> DetectionMeasurement:
        self.elapsed += self.hop_seconds
        signal_db = self._band_db(psd, self.signal_mask)
        noise_1_db = self._band_db(psd, self.noise_1_mask)
        noise_2_db = self._band_db(psd, self.noise_2_mask)
        noise_db = (noise_1_db + noise_2_db) / 2.0
        snr_db = signal_db - noise_db
        noise_agrees = abs(noise_1_db - noise_2_db) <= self.noise_tolerance_db

        if self.state is DetectionState.EVENT:
            threshold_db = self._threshold() - self.event_threshold_offset_db
            self.event_snrs.append(snr_db)
            if self.elapsed - (self.event_started_at or self.elapsed) >= self.event_timeout:
                self._finish_event(discarded=True)
            elif snr_db <= threshold_db:
                self._finish_event(discarded=False)
        elif not noise_agrees:
            self._set_state(
                DetectionState.PAUSED,
                f"Noise-Kanäle weichen um {abs(noise_1_db - noise_2_db):.2f} dB ab",
            )
            threshold_db = self._threshold()
        else:
            if self.state is DetectionState.PAUSED:
                target = (DetectionState.DETECT if len(self.baseline) == self.baseline.maxlen
                          else DetectionState.ESTIMATE_THRESHOLD)
                self._set_state(target, "Noise-Kanäle stimmen wieder überein")

            threshold_db = self._threshold()
            if self.state is DetectionState.ESTIMATE_THRESHOLD:
                self.baseline.append(snr_db)
                threshold_db = self._threshold()
                if np.isfinite(threshold_db):
                    self._set_state(
                        DetectionState.DETECT,
                        f"Baseline über {self.threshold_window:g} s vollständig",
                    )
            elif self.state is DetectionState.DETECT:
                if np.isfinite(threshold_db) and snr_db > threshold_db:
                    self.event_started_at = self.elapsed
                    self.event_started_wall = datetime.now(timezone.utc)
                    self.event_snrs = [snr_db]
                    event_threshold_db = threshold_db - self.event_threshold_offset_db
                    self.logger.info(
                        "Event gestartet: start=%.3fs snr=%.3fdB "
                        "schwellwert=%.3fdB (um %.1fdB abgesenkt)",
                        self.elapsed, snr_db, event_threshold_db,
                        self.event_threshold_offset_db,
                    )
                    self._set_state(DetectionState.EVENT, "Schwellwert überschritten")
                    threshold_db = event_threshold_db
                else:
                    if self.elapsed >= self.baseline_frozen_until:
                        self.baseline.append(snr_db)
                        threshold_db = self._threshold()

        return DetectionMeasurement(
            self.elapsed, signal_db, noise_1_db, noise_2_db,
            snr_db, threshold_db, self.state,
        )


def plot_stream(
        source: WavSource | TwitchSource,
        args: argparse.Namespace,
        label: str,
        logger: logging.Logger,
) -> None:
    sample_rate = source.sample_rate
    fft_size = args.fft_size
    if fft_size > sample_rate * args.history:
        raise ValueError("FFT-Fenster ist länger als der dargestellte Zeitraum")
    hop_size = max(1, round(sample_rate * args.update))
    # Keep enough data for both independently configurable time windows.
    spectrum = RollingSpectrum(
        sample_rate,
        fft_size,
        hop_size,
        max(args.history, args.psd_history),
        keep_history=not args.no_gui,
    )
    spectrogram_columns = max(1, int(np.ceil(args.history * sample_rate / hop_size)))
    psd_columns = max(1, int(np.ceil(args.psd_history * sample_rate / hop_size)))

    frequencies = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    max_frequency = min(args.max_freq, sample_rate / 2)
    frequency_mask = frequencies <= max_frequency
    shown_frequencies = frequencies[frequency_mask]
    detector = MeteorDetector(
        frequencies=frequencies,
        hop_seconds=hop_size / sample_rate,
        threshold_window=args.threshold_window,
        threshold_sigma=args.threshold_sigma,
        noise_tolerance_db=args.noise_tolerance_db,
        event_timeout=args.event_timeout,
        event_threshold_offset_db=args.event_threshold_offset_db,
        threshold_freeze=args.threshold_freeze,
        frequency_offset_hz=args.freq_offset_hz,
        event_csv=args.event_csv,
        logger=logger,
    )

    if args.no_gui:
        logger.info("GUI deaktiviert; Detektion läuft im Headless-Modus")
        try:
            for chunk in source.chunks():
                if chunk.size:
                    for psd in spectrum.add(chunk):
                        detector.process(psd)
        except KeyboardInterrupt:
            pass
        return

    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    measurement_limit = max(2, int(np.ceil(args.history * sample_rate / hop_size)))
    measurements: deque[DetectionMeasurement] = deque(maxlen=measurement_limit)

    plt.ion()
    figure = plt.figure(figsize=(13, 9))
    grid = figure.add_gridspec(2, 2, width_ratios=[4, 1], height_ratios=[3, 2])
    spectrogram_axis = figure.add_subplot(grid[0, 0])
    psd_axis = figure.add_subplot(grid[0, 1], sharey=spectrogram_axis)
    measurement_axis = figure.add_subplot(grid[1, :])
    figure.canvas.manager.set_window_title("Live Audio Spectrum")
    placeholder = np.full((frequency_mask.sum(), 2), args.db_min)
    image = spectrogram_axis.imshow(
        placeholder,
        origin="lower",
        aspect="auto",
        extent=(-args.history, 0, 0, max_frequency),
        cmap=args.cmap,
        vmin=args.db_min,
        vmax=args.db_max,
    )
    colorbar = figure.colorbar(image, ax=spectrogram_axis, pad=0.015)
    colorbar.set_label("PSD [dB/Hz]")
    psd_line, = psd_axis.plot(np.full_like(shown_frequencies, args.db_min), shown_frequencies)
    snr_line, = measurement_axis.plot([], [], label="SNR", color="tab:blue")
    threshold_line, = measurement_axis.plot(
        [], [], label="Schwellwert", color="tab:red", linestyle="--"
    )
    noise_difference_line, = measurement_axis.plot(
        [], [], label="|Noise 1 - Noise 2|", color="tab:gray", alpha=0.7
    )
    event_artists: list[object] = []

    spectrogram_axis.set(
        title=f"Letzte {args.history:g} s – {label}",
        ylabel="Frequenz [Hz]",
        xlim=(-args.history, 0),
        ylim=(0, max_frequency),
    )
    spectrogram_axis.set_xlabel("Zeit relativ zu jetzt [s]")
    psd_axis.set(
        title=f"PSD\nletzte {args.psd_history:g} s",
        xlabel="mittlere PSD [dB/Hz]",
        xlim=(args.db_min, args.db_max),
        ylim=(0, max_frequency),
    )
    psd_axis.grid(alpha=0.25)
    band_legend_handles: list[Patch] = []
    for band_name, (lower_frequency, upper_frequency), color in shifted_detection_bands(
            args.freq_offset_hz
    ):
        for axis in (spectrogram_axis, psd_axis):
            axis.axhspan(
                lower_frequency,
                upper_frequency,
                facecolor=color,
                edgecolor=color,
                linewidth=1.0,
                alpha=0.16,
                zorder=1,
            )
        band_legend_handles.append(
            Patch(
                facecolor=color,
                edgecolor=color,
                alpha=0.25,
                label=f"{band_name} ({lower_frequency:g}–{upper_frequency:g} Hz)",
            )
        )
    psd_axis.legend(handles=band_legend_handles, loc="best", fontsize="small")
    measurement_axis.set(
        title=f"Messwerte – Zustand: {detector.state.value}",
        xlabel="Zeit relativ zu jetzt [s]",
        ylabel="Pegel / Differenz [dB]",
        xlim=(-args.history, 0),
    )
    measurement_axis.grid(alpha=0.25)
    measurement_axis.legend(
        handles=[
            snr_line, threshold_line, noise_difference_line,
            Patch(facecolor="tab:orange", alpha=0.22, label="Event aktiv"),
            Patch(facecolor="tab:green", alpha=0.18, label="Event erkannt"),
            Patch(facecolor="tab:red", alpha=0.18, label="Event verworfen"),
        ],
        loc="upper left",
    )
    figure.tight_layout()

    last_draw = 0.0

    def update_plot(force: bool = False) -> None:
        nonlocal last_draw, event_artists
        now = time.monotonic()
        if not force and now - last_draw < args.update * 0.8:
            return
        matrix = spectrum.matrix()
        if matrix is None:
            return
        spectrogram_data = matrix[frequency_mask, -spectrogram_columns:]
        duration = max(
            hop_size / sample_rate,
            spectrogram_data.shape[1] * hop_size / sample_rate,
        )
        spectrogram_db = 10.0 * np.log10(np.maximum(spectrogram_data, EPSILON))
        image.set_data(spectrogram_db)
        image.set_extent((-min(args.history, duration), 0, 0, max_frequency))
        psd_data = matrix[frequency_mask, -psd_columns:]
        mean_psd_db = 10.0 * np.log10(np.maximum(psd_data.mean(axis=1), EPSILON))
        psd_line.set_data(mean_psd_db, shown_frequencies)
        if measurements:
            latest = measurements[-1].elapsed
            relative_time = np.asarray([item.elapsed - latest for item in measurements])
            snr_line.set_data(relative_time, [item.snr_db for item in measurements])
            threshold_line.set_data(
                relative_time, [item.threshold_db for item in measurements]
            )
            noise_difference_line.set_data(
                relative_time,
                [abs(item.noise_1_db - item.noise_2_db) for item in measurements],
            )
            measurement_axis.relim()
            measurement_axis.autoscale_view(scalex=False, scaley=True)
            measurement_axis.set_title(
                f"Messwerte – Zustand: {measurements[-1].state.value}"
            )
            for artist in event_artists:
                artist.remove()
            event_artists = []
            earliest = latest - args.history
            visible_events: list[tuple[float, float, str, float]] = []
            for event in detector.events:
                if event.stop_elapsed >= earliest:
                    color = "tab:red" if event.discarded else "tab:green"
                    visible_events.append((
                        event.start_elapsed - latest,
                        event.stop_elapsed - latest,
                        color,
                        0.18,
                    ))
            if detector.event_started_at is not None:
                visible_events.append((
                    detector.event_started_at - latest, 0.0, "tab:orange", 0.22
                ))
            for start, stop, color, alpha in visible_events:
                event_artists.extend([
                    spectrogram_axis.axvspan(start, stop, color=color, alpha=alpha),
                    measurement_axis.axvspan(start, stop, color=color, alpha=alpha),
                ])
        figure.canvas.draw_idle()
        figure.canvas.flush_events()
        plt.pause(0.001)
        # Measure the refresh interval from the completed draw. Otherwise a slow
        # backend can immediately start the next full redraw and starve the UI.
        last_draw = time.monotonic()

    try:
        for chunk in source.chunks():
            if not plt.fignum_exists(figure.number):
                break
            if chunk.size:
                for psd in spectrum.add(chunk):
                    measurements.append(detector.process(psd))
                update_plot()
            else:
                # Live-source heartbeat: process window events without doing an
                # expensive redraw while the audio data has not changed.
                figure.canvas.flush_events()
                plt.pause(0.001)
    except KeyboardInterrupt:
        pass

    if plt.fignum_exists(figure.number):
        update_plot(force=True)
    if args.save:
        figure.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"Plot gespeichert: {args.save}")
    if plt.fignum_exists(figure.number) and not args.no_hold:
        plt.ioff()
        plt.show()
    else:
        plt.close(figure)


def positive_float(value: str) -> float:
    result = float(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("muss größer als 0 sein")
    return result


def add_plot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--history", type=positive_float, default=60.0,
                        help="sichtbarer Zeitraum in Sekunden (Standard: 60)")
    parser.add_argument("--psd-history", type=positive_float, default=10.0,
                        help="Zeitraum für die gemittelte PSD in Sekunden (Standard: 10)")
    parser.add_argument("--update", type=positive_float, default=0.10,
                        help="Zeitabstand der Spektren in Sekunden (Standard: 0.10)")
    parser.add_argument("--fft-size", type=int, default=2048,
                        help="FFT-Größe in Samples (Standard: 2048)")
    parser.add_argument("--max-freq", type=positive_float, default=3000.0,
                        help="höchste dargestellte Frequenz in Hz (Standard: 3000)")
    parser.add_argument(
        "--freq-offset-hz",
        type=float,
        default=0.0,
        help="gemeinsamer Frequenz-Offset aller drei Detektionskanäle in Hz "
             "(Standard: 0)",
    )
    parser.add_argument("--db-min", type=float, default=-120.0,
                        help="untere Farb-/PSD-Grenze (Standard: -120)")
    parser.add_argument("--db-max", type=float, default=-20.0,
                        help="obere Farb-/PSD-Grenze (Standard: -20)")
    parser.add_argument("--cmap", default="magma", help="Matplotlib-Farbskala")
    parser.add_argument("--save", metavar="PNG", help="letzten Plot zusätzlich speichern")
    parser.add_argument("--no-gui", action="store_true",
                        help="ohne GUI und Spektrogramm-Historie ausführen")
    parser.add_argument("--no-hold", action="store_true",
                        help="Fenster am Ende nicht geöffnet halten")
    parser.add_argument("--threshold-window", type=positive_float, default=10.0,
                        help="Baseline-Fenster in Sekunden (Standard: 10)")
    parser.add_argument("--threshold-sigma", type=positive_float, default=4.0,
                        help="Standardabweichungen über Rolling Mean (Standard: 4)")
    parser.add_argument("--noise-tolerance-db", type=positive_float, default=6.0,
                        help="maximale Differenz der Noise-Kanäle (Standard: 6 dB)")
    parser.add_argument("--event-timeout", type=positive_float, default=120.0,
                        help="Event nach dieser Dauer verwerfen (Standard: 120 s)")
    parser.add_argument("--event-threshold-offset-db", type=positive_float, default=2.0,
                        help="Schwellwert während eines Events absenken "
                             "(Standard: 2 dB)")
    parser.add_argument("--threshold-freeze", type=positive_float, default=10.0,
                        help="Baseline nach Event einfrieren (Standard: 10 s)")
    parser.add_argument(
        "--event-csv",
        type=Path,
        default=OUTPUT_DIR / "meteor_events.csv",
        help="Basisname der neuen Event-CSV (Standard: out/meteor_events.csv)",
    )


def configure_logger(log_file: Path) -> logging.Logger:
    logger = logging.getLogger("meteor_detect")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rollierendes Audio-Spektrogramm mit gemittelter PSD"
    )
    subparsers = parser.add_subparsers(dest="source", required=True)

    wav_parser = subparsers.add_parser("wav", help="PCM-WAV-Datei abspielen/analysieren")
    wav_parser.add_argument("file", type=Path)
    wav_parser.add_argument("--no-realtime", action="store_true",
                            help="WAV so schnell wie möglich statt in Echtzeit lesen")
    wav_parser.add_argument(
        "--log-file",
        type=Path,
        default="meteor_detect.log",
        help="Logdatei (Standard: meteor_detect.log)",
    )
    add_plot_arguments(wav_parser)

    twitch_parser = subparsers.add_parser("twitch", help="Twitch-Kanal live analysieren")
    twitch_parser.add_argument("channel", help="Kanalname oder vollständige Twitch-URL")
    twitch_parser.add_argument("--sample-rate", type=int, default=4000,
                               help="Audio-Abtastrate in Hz (Standard: 4000)")
    twitch_parser.add_argument("--quality", default="audio_only",
                               help="Streamlink-Qualität (Standard: audio_only)")
    twitch_parser.add_argument("--retry-delay", type=positive_float, default=10.0,
                               help="Pause vor Neuverbindung in Sekunden (Standard: 10)")
    twitch_parser.add_argument("--stall-timeout", type=positive_float, default=10.0,
                               help="Reconnect ohne Audiodaten nach Sekunden (Standard: 10)")
    twitch_parser.add_argument(
        "--log-file",
        type=Path,
        default="meteor_detect.log",
        help="Logdatei (Standard: meteor_detect.log)",
    )
    add_plot_arguments(twitch_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.fft_size < 16:
        parser.error("--fft-size muss mindestens 16 sein")
    if args.db_min >= args.db_max:
        parser.error("--db-min muss kleiner als --db-max sein")
    if args.no_gui and args.save:
        parser.error("--save kann nicht zusammen mit --no-gui verwendet werden")

    try:
        if args.source == "wav":
            if not args.file.is_file():
                parser.error(f"WAV-Datei nicht gefunden: {args.file}")
            with wave.open(str(args.file), "rb") as wav_info:
                rate = wav_info.getframerate()
            chunk_frames = max(1, round(rate * args.update))
            logger = configure_logger(args.log_file)
            logger.info("WAV-Analyse gestartet: %s", args.file)
            with WavSource(str(args.file), chunk_frames, not args.no_realtime) as source:
                plot_stream(source, args, args.file.name, logger)
        else:
            if args.sample_rate <= 0:
                parser.error("--sample-rate muss größer als 0 sein")
            chunk_frames = max(1, round(args.sample_rate * args.update))
            logger = configure_logger(args.log_file)
            with TwitchSource(
                    args.channel,
                    args.sample_rate,
                    chunk_frames,
                    args.quality,
                    args.retry_delay,
                    args.stall_timeout,
                    logger,
            ) as source:
                plot_stream(source, args, args.channel, logger)
    except (OSError, ValueError, RuntimeError, wave.Error) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
