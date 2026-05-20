# camera_tracker.py
# Neximus Camera Tracking Module
# Moondream2 (CPU) for intelligent object/face detection via natural language.
# OpenCV CSRT tracker at 30Hz between Moondream2 detections.
# PI control loop writes boom arm and camera pan percent to PLC analog outputs.
# Start/stop via voice command or UI button. Mode selectable: face or object.

import cv2
import threading
import logging
import time
import numpy as np
from typing import Optional, Callable
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CAMERA_INDEX        = 0
CAMERA_BACKEND      = cv2.CAP_DSHOW
FRAME_WIDTH         = 640
FRAME_HEIGHT        = 480
LOOP_HZ             = 30
LOOP_INTERVAL       = 1.0 / LOOP_HZ
DEADBAND_PX         = 8               # pixels — no correction inside this zone
OUTPUT_TAG_BOOM     = "Analog_Output_3"
OUTPUT_TAG_CAMERA   = "Analog_Output_4"
INPUT_TAG_BOOM      = "Boom_Position"
INPUT_TAG_CAMERA    = "Camera_Position"
OUTPUT_MIN          = 0.0
OUTPUT_MAX          = 100.0
BOOM_CENTER         = 50.0
CAMERA_CENTER       = 50.0

# How often Moondream2 re-runs detection (seconds)
# CSRT tracks between detections at full 30Hz
MOONDREAM_INTERVAL  = 0.5

# Default PI gains
DEFAULT_KP_BOOM     = 0.25
DEFAULT_KI_BOOM     = 0.02
DEFAULT_KP_CAMERA   = 0.25
DEFAULT_KI_CAMERA   = 0.02


# ---------------------------------------------------------------------------
# PI Controller
# ---------------------------------------------------------------------------
class PIController:
    def __init__(self, kp: float, ki: float, out_min: float, out_max: float,
                 center: float = 50.0):
        self.kp      = kp
        self.ki      = ki
        self.out_min = out_min
        self.out_max = out_max
        self.center  = center
        self._integral = 0.0

    def reset(self):
        self._integral = 0.0

    def update(self, error: float, dt: float) -> float:
        self._integral += error * dt
        max_integral = (self.out_max - self.out_min) / max(self.ki, 1e-6)
        self._integral = max(-max_integral, min(max_integral, self._integral))
        output = self.center + (self.kp * error) + (self.ki * self._integral)
        return max(self.out_min, min(self.out_max, output))

    def set_gains(self, kp: float, ki: float):
        self.kp = kp
        self.ki = ki


# ---------------------------------------------------------------------------
# Moondream2 Detector (CPU, runs in background thread)
# ---------------------------------------------------------------------------
class MoondreamDetector:
    """
    Loads Moondream2 once on CPU and provides detect() calls.
    Runs detection in a background thread so it never blocks the 30Hz loop.
    """

    def __init__(self):
        self._model     = None
        self._tokenizer = None
        self._loaded    = False
        self._loading   = False
        self._lock      = threading.Lock()

        # Latest detection result — updated by background thread
        self._result_box  = None   # (x1, y1, x2, y2) normalized 0-1, or None
        self._result_lock = threading.Lock()

        # Detection request queue
        self._pending_frame  = None
        self._pending_prompt = None
        self._pending_lock   = threading.Lock()
        self._detect_event   = threading.Event()
        self._stop_event     = threading.Event()

        # Start worker thread
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def load(self):
        """Load Moondream2 model (call once at tracker start)."""
        if self._loaded or self._loading:
            return
        self._loading = True
        logger.info("[Moondream] Loading model on CPU...")
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            with self._lock:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    "vikhyatk/moondream2", trust_remote_code=True)
                self._model = AutoModelForCausalLM.from_pretrained(
                    "vikhyatk/moondream2",
                    trust_remote_code=True,
                    device_map="cpu"
                )
                self._model.eval()
                self._loaded = True
            logger.info("[Moondream] Model loaded and ready on CPU")
        except Exception as e:
            logger.error(f"[Moondream] Failed to load model: {e}")
            self._loaded = False
        self._loading = False

    def is_loaded(self) -> bool:
        return self._loaded

    def request_detection(self, frame: np.ndarray, prompt: str):
        """
        Submit a frame for detection. Non-blocking.
        Result available via get_latest_box().
        """
        with self._pending_lock:
            self._pending_frame  = frame.copy()
            self._pending_prompt = prompt
        self._detect_event.set()

    def get_latest_box(self):
        """
        Returns latest bounding box as (cx, cy) pixel coords in FRAME_WIDTH x FRAME_HEIGHT,
        or (None, None) if no detection yet.
        """
        with self._result_lock:
            box = self._result_box
        if box is None:
            return None, None
        x1, y1, x2, y2 = box
        cx = int(((x1 + x2) / 2) * FRAME_WIDTH)
        cy = int(((y1 + y2) / 2) * FRAME_HEIGHT)
        return cx, cy

    def clear_result(self):
        with self._result_lock:
            self._result_box = None

    def stop(self):
        self._stop_event.set()
        self._detect_event.set()
        # Clear any pending detection so stale prompts don't run after restart
        with self._pending_lock:
            self._pending_frame  = None
            self._pending_prompt = None
        # Wait for worker to actually exit (max 2s)
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)

    def restart(self):
        """Restart the worker thread after a stop() — keeps loaded model."""
        # Ensure old worker is fully dead before starting a new one
        if self._worker and self._worker.is_alive():
            self._stop_event.set()
            self._detect_event.set()
            self._worker.join(timeout=2.0)
        self._stop_event.clear()
        self._detect_event.clear()
        # Clear any stale pending detection
        with self._pending_lock:
            self._pending_frame  = None
            self._pending_prompt = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self):
        """Background thread: processes detection requests one at a time."""
        while not self._stop_event.is_set():
            self._detect_event.wait(timeout=1.0)
            self._detect_event.clear()

            if self._stop_event.is_set():
                break

            with self._pending_lock:
                frame  = self._pending_frame
                prompt = self._pending_prompt
                self._pending_frame  = None
                self._pending_prompt = None

            if frame is None or prompt is None:
                continue

            if not self._loaded:
                continue

            try:
                result_box = self._run_detection(frame, prompt)
                with self._result_lock:
                    self._result_box = result_box
            except Exception as e:
                logger.error(f"[Moondream] Detection error: {e}")

    def _run_detection(self, frame: np.ndarray, prompt: str):
        """
        Run Moondream2 object detection using detect() API directly.
        No text generation — just locate the object and return normalized bbox.
        Returns (x1, y1, x2, y2) normalized 0-1, or None.
        """
        with self._lock:
            if not self._loaded:
                logger.warning("[Moondream] detect() called but model not loaded")
                return None
            try:
                pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                logger.info(f"[Moondream] Running detect() for prompt: '{prompt}'")
                detect_result = self._model.detect(pil_image, prompt)
                logger.info(f"[Moondream] detect() raw result: {detect_result}")
                # Handle both list format and dict format {'objects': [...]}
                if isinstance(detect_result, dict):
                    detect_result = detect_result.get('objects', [])
                if detect_result and len(detect_result) > 0:
                    obj = detect_result[0]
                    logger.info(f"[Moondream] First object: {obj} type={type(obj)}")
                    if hasattr(obj, 'x_min'):
                        box = (obj.x_min, obj.y_min, obj.x_max, obj.y_max)
                        logger.info(f"[Moondream] bbox (attr): {box}")
                        return box
                    elif isinstance(obj, dict):
                        x1 = obj.get('x_min', obj.get('xmin', 0.3))
                        y1 = obj.get('y_min', obj.get('ymin', 0.3))
                        x2 = obj.get('x_max', obj.get('xmax', 0.7))
                        y2 = obj.get('y_max', obj.get('ymax', 0.7))
                        box = (x1, y1, x2, y2)
                        logger.info(f"[Moondream] bbox (dict): {box}")
                        return box
                    else:
                        logger.warning(f"[Moondream] Unknown result format: {type(obj)} = {obj}")
                else:
                    logger.info(f"[Moondream] No objects found for '{prompt}'")
                return None
            except Exception as e:
                logger.error(f"[Moondream] detect() failed: {e}", exc_info=True)
                return None

    def _parse_location_from_text(self, answer: str):
        """
        Rough location estimate from Moondream's text answer.
        Maps location words to approximate normalized bounding boxes.
        Returns (x1, y1, x2, y2) normalized, or None.
        """
        if not answer or len(answer) < 5:
            return None

        # Default to center
        x1, y1, x2, y2 = 0.35, 0.35, 0.65, 0.65

        if "left" in answer:
            x1, x2 = 0.05, 0.4
        elif "right" in answer:
            x1, x2 = 0.6, 0.95
        elif "center" in answer or "middle" in answer:
            x1, x2 = 0.3, 0.7

        if "top" in answer or "upper" in answer:
            y1, y2 = 0.05, 0.4
        elif "bottom" in answer or "lower" in answer:
            y1, y2 = 0.6, 0.95

        return (x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# CameraTracker
# ---------------------------------------------------------------------------
class CameraTracker:
    """
    Autonomous camera tracking module for Neximus.

    Moondream2 detects the target every MOONDREAM_INTERVAL seconds.
    OpenCV CSRT tracker maintains lock at 30Hz between detections.
    PI controllers drive Analog_Output_3 (boom) and Analog_Output_4 (camera).
    """

    MODE_FACE   = "face"
    MODE_OBJECT = "object"

    def __init__(self,
                 plc_write_func:  Optional[Callable] = None,
                 plc_read_func:   Optional[Callable] = None,
                 status_callback: Optional[Callable] = None):
        self._plc_write  = plc_write_func
        self._plc_read   = plc_read_func
        self._status_cb  = status_callback

        self._mode        = self.MODE_FACE
        self._object_desc = "person"      # Moondream prompt for object mode

        self._running    = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # PI controllers
        self._pi_boom   = PIController(DEFAULT_KP_BOOM,   DEFAULT_KI_BOOM,
                                       OUTPUT_MIN, OUTPUT_MAX, BOOM_CENTER)
        self._pi_camera = PIController(DEFAULT_KP_CAMERA, DEFAULT_KI_CAMERA,
                                       OUTPUT_MIN, OUTPUT_MAX, CAMERA_CENTER)

        # PLC tag names — set via set_tags() before start()
        self._tag_output_boom     = OUTPUT_TAG_BOOM
        self._tag_output_camera   = OUTPUT_TAG_CAMERA
        self._tag_feedback_boom   = INPUT_TAG_BOOM
        self._tag_feedback_camera = INPUT_TAG_CAMERA

        # Moondream detector (always created, loads model on start)
        self._moondream = MoondreamDetector()

        # OpenCV CSRT tracker instance
        self._csrt       = None
        self._csrt_active = False

        # Face cascade for face mode
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Public readouts for UI
        self.current_boom_output     = BOOM_CENTER
        self.current_camera_output   = CAMERA_CENTER
        self.current_boom_feedback   = 0.0
        self.current_camera_feedback = 0.0
        self.current_error_x         = 0.0
        self.current_error_y         = 0.0
        self.target_detected         = False

        # Preview frame buffer — background thread writes, main thread reads
        self._latest_frame      = None
        self._frame_lock        = threading.Lock()

        # Per-tag write error cache — suppress repeated identical errors
        self._last_write_err: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_plc_write_func(self, func: Callable):
        self._plc_write = func

    def set_plc_read_func(self, func: Callable):
        self._plc_read = func

    def set_status_callback(self, func: Callable):
        self._status_cb = func

    def set_tags(self, output_boom: str, output_camera: str,
                 feedback_boom: str = None, feedback_camera: str = None):
        """Set PLC tag names to use for outputs and feedback."""
        self._tag_output_boom    = output_boom
        self._tag_output_camera  = output_camera
        self._tag_feedback_boom  = feedback_boom
        self._tag_feedback_camera = feedback_camera
        logger.info(f"[Tracker] Tags set — boom={output_boom} camera={output_camera} "
                    f"boom_fb={feedback_boom} camera_fb={feedback_camera}")

    def set_gains(self, kp_boom: float, ki_boom: float,
                  kp_camera: float, ki_camera: float):
        self._pi_boom.set_gains(kp_boom, ki_boom)
        self._pi_camera.set_gains(kp_camera, ki_camera)

    def set_mode_face(self):
        self._mode = self.MODE_FACE
        self._csrt_active = False
        logger.info("[Tracker] Mode: FACE")
        self._notify_status("Mode: Face")

    def set_mode_object(self, description: str = "person"):
        self._mode = self.MODE_OBJECT
        self._object_desc = description.strip()
        self._csrt_active = False
        self._moondream.clear_result()
        logger.info(f"[Tracker] Mode: OBJECT ({self._object_desc})")
        self._notify_status(f"Mode: Object ({self._object_desc})")

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._pi_boom.reset()
        self._pi_camera.reset()
        self._csrt_active = False

        # Restart the Moondream worker thread (may have been stopped by previous stop())
        # then load the model if not already loaded
        self._moondream.restart()
        threading.Thread(target=self._moondream.load, daemon=True).start()

        self._thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("[Tracker] Started")
        self._notify_status("Tracking: Running")

    def stop(self):
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        self._moondream.stop()  # Flushes pending detections and joins worker
        # Wait for tracking loop thread to exit (max 3s)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._csrt_active = False
        logger.info("[Tracker] Stopped")
        self._notify_status("Tracking: Stopped")

    def is_running(self) -> bool:
        return self._running

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Return the most recent annotated frame as a BGR numpy array, or None.
        Safe to call from any thread (main/tkinter thread).
        """
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_mode(self) -> str:
        return self._mode

    def get_object_desc(self) -> str:
        return self._object_desc

    # ------------------------------------------------------------------
    # Main tracking loop (30Hz)
    # ------------------------------------------------------------------
    def _tracking_loop(self):
        cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
        if not cap.isOpened():
            logger.error("[Tracker] Camera not found")
            self._notify_status("Error: Camera not found")
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"[Tracker] Camera resolution: {actual_w}x{actual_h} (requested {FRAME_WIDTH}x{FRAME_HEIGHT})")

        frame_cx = actual_w // 2
        frame_cy = actual_h // 2

        last_time        = time.time()
        last_md_time     = 0.0   # last time Moondream ran

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                now = time.time()
                dt  = max(now - last_time, 1e-6)
                last_time = now

                target_x, target_y = None, None

                if self._mode == self.MODE_FACE:
                    # Face mode — OpenCV Haar at full speed, no Moondream needed
                    target_x, target_y = self._detect_face(frame)

                elif self._mode == self.MODE_OBJECT:
                    # Object mode — Moondream every N seconds, CSRT tracks between
                    if self._csrt_active:
                        # Try CSRT first
                        ok, bbox = self._csrt.update(frame)
                        if ok:
                            bx, by, bw, bh = [int(v) for v in bbox]
                            target_x = bx + bw // 2
                            target_y = by + bh // 2
                            # Draw CSRT box
                            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh),
                                          (0, 200, 255), 2)
                        else:
                            # CSRT lost target
                            self._csrt_active = False
                            self._moondream.clear_result()
                            target_x, target_y = None, None

                    # Schedule Moondream re-detection
                    if (now - last_md_time) >= MOONDREAM_INTERVAL:
                        if self._moondream.is_loaded():
                            self._moondream.request_detection(frame, self._object_desc)
                            last_md_time = now

                    # Check if Moondream returned a new result
                    md_cx, md_cy = self._moondream.get_latest_box()
                    if md_cx is not None:
                        # Re-initialize CSRT on new Moondream detection
                        box_size = 80
                        bbox = (
                            max(0, md_cx - box_size // 2),
                            max(0, md_cy - box_size // 2),
                            box_size, box_size
                        )
                        # Try legacy namespace first, then root, then fall back to KCF
                        if hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerCSRT_create'):
                            self._csrt = cv2.legacy.TrackerCSRT_create()
                        elif hasattr(cv2, 'TrackerCSRT_create'):
                            self._csrt = cv2.TrackerCSRT_create()
                        else:
                            logger.warning('[Tracker] TrackerCSRT_create not found - falling back to TrackerKCF')
                            self._csrt = cv2.TrackerKCF_create() if hasattr(cv2, 'TrackerKCF_create') else None
                        if self._csrt is None:
                            logger.error('[Tracker] No CSRT or KCF tracker available in this OpenCV build')
                            self._csrt_active = False
                            continue
                        self._csrt.init(frame, bbox)
                        self._csrt_active = True
                        target_x, target_y = md_cx, md_cy
                        self._moondream.clear_result()

                # PI control
                self.target_detected = target_x is not None
                if self.target_detected:
                    error_x = float(target_x - frame_cx)
                    error_y = float(frame_cy - target_y)  # inverted: face above center = positive = boom up
                    self.current_error_x = error_x
                    self.current_error_y = error_y

                    boom_out   = self._pi_boom.update(error_y, dt)
                    camera_out = self._pi_camera.update(error_x, dt)

                    self.current_boom_output   = boom_out
                    self.current_camera_output = camera_out

                    self._write_plc(self._tag_output_boom,   boom_out)
                    self._write_plc(self._tag_output_camera, camera_out)

                    # Draw target indicator
                    cv2.circle(frame, (target_x, target_y), 10, (0, 255, 0), 2)
                    cv2.line(frame, (frame_cx, frame_cy),
                             (target_x, target_y), (0, 255, 0), 1)
                else:
                    self.current_error_x = 0.0
                    self.current_error_y = 0.0

                # Read PLC feedback
                self._read_feedback()

                # Draw overlay
                self._draw_overlay(frame, frame_cx, frame_cy)

                # Push annotated frame to buffer for tkinter canvas (main thread reads at 10fps)
                with self._frame_lock:
                    self._latest_frame = frame

                # Maintain loop frequency
                elapsed = time.time() - now
                sleep_t = LOOP_INTERVAL - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)

        except Exception as e:
            logger.error(f"[Tracker] Loop error: {e}")
            import traceback
            traceback.print_exc()
            self._notify_status(f"Error: {e}")
        finally:
            cap.release()
            with self._frame_lock:
                self._latest_frame = None
            self._running = False
            self._notify_status("Tracking: Stopped")

    # ------------------------------------------------------------------
    # Face detection
    # ------------------------------------------------------------------
    def _detect_face(self, frame):
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(40, 40)
        )
        if len(faces) == 0:
            return None, None
        largest = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest
        cx, cy = x + w // 2, y + h // 2
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return cx, cy

    # ------------------------------------------------------------------
    # PLC read/write
    # ------------------------------------------------------------------
    def _write_plc(self, tag: str, value: float):
        if not self._plc_write:
            return
        try:
            self._plc_write(tag, round(value, 2))
            # Clear cached error on success so a future failure is logged once
            self._last_write_err.pop(tag, None)
        except Exception as e:
            err_str = str(e)
            if self._last_write_err.get(tag) != err_str:
                logger.error(f"[Tracker] PLC write failed ({tag}): {e}")
                self._last_write_err[tag] = err_str

    def _read_feedback(self):
        if not self._plc_read:
            return
        if self._tag_feedback_boom:
            try:
                boom = self._plc_read(self._tag_feedback_boom)
                if boom is not None:
                    self.current_boom_feedback = float(boom)
            except Exception:
                pass
        if self._tag_feedback_camera:
            try:
                cam = self._plc_read(self._tag_feedback_camera)
                if cam is not None:
                    self.current_camera_feedback = float(cam)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Overlay
    # ------------------------------------------------------------------
    def _draw_overlay(self, frame, cx: int, cy: int):
        # Crosshair
        cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (255, 255, 255), 1)
        cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (255, 255, 255), 1)

        # Status text
        mode_str = "FACE" if self._mode == self.MODE_FACE else f"OBJ: {self._object_desc}"
        detected_str = "TARGET" if self.target_detected else "SEARCHING"
        color = (0, 255, 0) if self.target_detected else (0, 100, 255)

        cv2.putText(frame, f"Mode: {mode_str}",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, detected_str,
                    (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        cv2.putText(frame, f"Boom: {self.current_boom_output:.1f}%",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"Cam:  {self.current_camera_output:.1f}%",
                    (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"ErrX: {self.current_error_x:.0f}px",
                    (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"ErrY: {self.current_error_y:.0f}px",
                    (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        if self._mode == self.MODE_OBJECT and not self._moondream.is_loaded():
            cv2.putText(frame, "Loading Moondream2...",
                        (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

    # ------------------------------------------------------------------
    # Status callback
    # ------------------------------------------------------------------
    def _notify_status(self, msg: str):
        if self._status_cb:
            try:
                self._status_cb(msg)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_tracker_instance: Optional[CameraTracker] = None


def get_tracker() -> Optional[CameraTracker]:
    return _tracker_instance


def initialize_tracker(plc_write_func=None, plc_read_func=None,
                       status_callback=None) -> CameraTracker:
    global _tracker_instance
    _tracker_instance = CameraTracker(plc_write_func, plc_read_func, status_callback)
    return _tracker_instance