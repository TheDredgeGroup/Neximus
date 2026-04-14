"""
Control Loop Module - Dredge Group
PI proportional-integral control loop using PyLogix persistent connection.
Runs in a background thread so Neximus remains fully operational.

Direction: 'direct'  -> output =  Kp * error + Ki * integral
           'reverse' -> output = -(Kp * error + Ki * integral)

Anti-windup: conditional - only accumulates integral in the direction
             that can still affect output (stops accumulating when clamped).
"""

import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Silence pylogix verbose logging
logging.getLogger('pylogix').setLevel(logging.WARNING)

try:
    from pylogix import PLC
    PYLOGIX_AVAILABLE = True
    logger.info("controlloop: PyLogix available")
except ImportError:
    PYLOGIX_AVAILABLE = False
    logger.error("controlloop: PyLogix not installed - run: pip install pylogix")

# How often to log cycle stats (seconds)
_LOG_INTERVAL_SEC = 30.0


class ControlLoop:
    """
    PI control loop with persistent PyLogix connection.
    Runs in a background thread. Neximus can query status at any time.
    """

    def __init__(self, ip: str, slot: int = 0):
        self.ip   = ip
        self.slot = slot

        # Tag names - set at start()
        self.tag_feedback: str = ''
        self.tag_output:   str = ''
        self.tag_setpoint: str = ''

        # Control parameters
        self.setpoint:   float = 0.0
        self.gain:       float = 1.0    # Kp
        self.ki:         float = 0.0    # Ki
        self.output_min: float = 0.0
        self.output_max: float = 100.0
        self.direction:  str   = 'direct'

        # Live state
        self.feedback:       float = 0.0
        self.output:         float = 0.0
        self.error:          float = 0.0
        self.integral:       float = 0.0
        self.cycle_time_ms:  float = 0.0
        self.cycle_count:    int   = 0
        self.last_error_msg: str   = ''

        self._running:  bool = False
        self._sp_dirty: bool = False
        self._thread:   Optional[threading.Thread] = None
        self._lock:     threading.Lock = threading.Lock()

        # Optional callback each cycle: (feedback, output, error, cycle_ms)
        self.on_cycle: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self,
              tag_feedback:  str,
              tag_output:    str,
              tag_setpoint:  str,
              setpoint:      float,
              gain:          float,
              ki:            float = 0.0,
              direction:     str   = 'direct',
              reset_integral: bool = False) -> bool:
        """
        Start the PI control loop.

        Args:
            tag_feedback:    PLC tag for analog input (feedback)
            tag_output:      PLC tag for analog output
            tag_setpoint:    PLC tag for setpoint (written to PLC on start)
            setpoint:        Initial setpoint value
            gain:            Proportional gain (Kp)
            ki:              Integral gain (Ki)
            direction:       'direct' or 'reverse'
            reset_integral:  If True, zero the integrator before starting

        Returns:
            True if thread started successfully
        """
        if not PYLOGIX_AVAILABLE:
            logger.error("Cannot start - PyLogix not installed")
            return False

        if self._running:
            logger.warning("Control loop already running")
            return False

        if not tag_feedback or not tag_output or not tag_setpoint:
            logger.error("Cannot start - one or more tag names are empty")
            return False

        self.tag_feedback  = tag_feedback
        self.tag_output    = tag_output
        self.tag_setpoint  = tag_setpoint
        self.setpoint      = float(setpoint)
        self.gain          = float(gain)
        self.ki            = float(ki)
        self.direction     = direction if direction in ('direct', 'reverse') else 'direct'
        self.cycle_count   = 0
        self.last_error_msg = ''
        self._sp_dirty     = False

        if reset_integral:
            self.integral = 0.0
            logger.info("Integral reset to 0")

        self._running = True
        self._thread  = threading.Thread(
            target=self._loop,
            name='ControlLoop',
            daemon=True
        )
        self._thread.start()
        logger.info(
            f"PI loop started | {self.ip} slot={self.slot} | "
            f"FB={tag_feedback} OUT={tag_output} SP_tag={tag_setpoint} | "
            f"SP={setpoint} Kp={gain} Ki={ki} dir={self.direction} "
            f"integral={'reset' if reset_integral else 'held'}"
        )
        return True

    def stop(self):
        """Stop the loop and close PLC connection."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("Control loop stopped")

    def set_setpoint(self, value: float):
        """Change setpoint while running - writes to PLC tag on next cycle."""
        with self._lock:
            self.setpoint  = float(value)
            self._sp_dirty = True
        logger.info(f"Setpoint -> {value}")

    def set_gain(self, value: float):
        with self._lock:
            self.gain = float(value)
        logger.info(f"Kp -> {value}")

    def set_ki(self, value: float):
        with self._lock:
            self.ki = float(value)
        logger.info(f"Ki -> {value}")

    def set_direction(self, direction: str):
        with self._lock:
            self.direction = direction if direction in ('direct', 'reverse') else 'direct'
        logger.info(f"Direction -> {self.direction}")

    def set_output_limits(self, low: float, high: float):
        with self._lock:
            self.output_min = float(low)
            self.output_max = float(high)

    def reset_integral(self):
        """Zero the integrator while running."""
        with self._lock:
            self.integral = 0.0
        logger.info("Integral reset to 0")

    def get_status(self) -> dict:
        return {
            'running':       self._running,
            'setpoint':      self.setpoint,
            'gain':          self.gain,
            'ki':            self.ki,
            'direction':     self.direction,
            'feedback':      round(self.feedback, 4),
            'output':        round(self.output, 4),
            'error':         round(self.error, 4),
            'integral':      round(self.integral, 4),
            'cycle_time_ms': round(self.cycle_time_ms, 2),
            'cycle_count':   self.cycle_count,
            'last_error':    self.last_error_msg,
            'plc_ip':        self.ip,
            'tag_feedback':  self.tag_feedback,
            'tag_output':    self.tag_output,
            'tag_setpoint':  self.tag_setpoint,
        }

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self):
        logger.info(f"Connecting to PLC {self.ip} slot {self.slot}...")

        try:
            with PLC() as plc:
                plc.IPAddress     = self.ip
                plc.ProcessorSlot = self.slot

                # Verify connection
                test = plc.Read(self.tag_feedback)
                if test.Status != 'Success':
                    self.last_error_msg = f"Initial read failed: {test.Status}"
                    logger.error(self.last_error_msg)
                    self._running = False
                    return

                logger.info(f"Connected. Initial feedback = {test.Value}")

                # Write setpoint to PLC on start
                plc.Write(self.tag_setpoint, self.setpoint)
                logger.info(f"Wrote setpoint {self.setpoint} -> {self.tag_setpoint}")

                last_log_time = time.perf_counter()
                last_cycle_time = time.perf_counter()

                # ---- PI CONTROL LOOP ----
                while self._running:
                    t_start = time.perf_counter()

                    # Calculate dt from last cycle (seconds)
                    dt = t_start - last_cycle_time
                    last_cycle_time = t_start

                    with self._lock:
                        sp        = self.setpoint
                        kp        = self.gain
                        ki        = self.ki
                        direction = self.direction
                        o_min     = self.output_min
                        o_max     = self.output_max
                        if self._sp_dirty:
                            plc.Write(self.tag_setpoint, sp)
                            self._sp_dirty = False

                    # Read feedback
                    fb_result = plc.Read(self.tag_feedback)
                    if fb_result.Status != 'Success':
                        self.last_error_msg = f"Read error: {fb_result.Status}"
                        logger.warning(self.last_error_msg)
                        time.sleep(0.1)
                        continue

                    feedback = float(fb_result.Value)
                    error    = sp - feedback

                    # --- Integral with conditional anti-windup ---
                    # Output saturation check uses PREVIOUS cycle's output
                    output_saturated_high = self.output >= o_max
                    output_saturated_low  = self.output <= o_min

                    if direction == 'direct':
                        # Direct: positive error drives output up
                        # Block accumulation only in the saturating direction
                        if not (output_saturated_high and error > 0) and \
                           not (output_saturated_low  and error < 0):
                            with self._lock:
                                self.integral += error * dt
                    else:
                        # Reverse: positive error drives output down
                        if not (output_saturated_low  and error > 0) and \
                           not (output_saturated_high and error < 0):
                            with self._lock:
                                self.integral += error * dt

                    # Read integral - clamp to output limits to prevent runaway
                    with self._lock:
                        self.integral = max(-o_max, min(o_max, self.integral))
                        integral = self.integral

                    # PI output
                    raw_output = kp * error + ki * integral

                    # Apply direction
                    if direction == 'reverse':
                        raw_output = -raw_output

                    # Clamp OUTPUT only - not the integral
                    output = max(o_min, min(o_max, raw_output))

                    # Write output
                    wr = plc.Write(self.tag_output, output)
                    if wr.Status != 'Success':
                        self.last_error_msg = f"Write error: {wr.Status}"
                        logger.warning(self.last_error_msg)
                    else:
                        self.last_error_msg = ''

                    # Update live state
                    self.feedback      = feedback
                    self.output        = output
                    self.error         = error
                    self.cycle_count  += 1
                    self.cycle_time_ms = (time.perf_counter() - t_start) * 1000

                    # Time-based logging - every 30 seconds
                    now = time.perf_counter()
                    if now - last_log_time >= _LOG_INTERVAL_SEC:
                        logger.info(
                            f"#{self.cycle_count} | FB={feedback:.3f} "
                            f"SP={sp:.3f} ERR={error:.3f} INT={integral:.3f} "
                            f"OUT={output:.3f} | {self.cycle_time_ms:.2f}ms/cycle"
                        )
                        last_log_time = now

                    if self.on_cycle:
                        try:
                            self.on_cycle(feedback, output, error, self.cycle_time_ms)
                        except Exception as e:
                            logger.warning(f"on_cycle callback error: {e}")

                # Zero output on clean stop
                try:
                    plc.Write(self.tag_output, 0.0)
                    logger.info("Output zeroed on stop")
                except Exception:
                    pass

        except Exception as e:
            self.last_error_msg = str(e)
            logger.error(f"Control loop exception: {e}")
        finally:
            self._running = False
            logger.info("Control loop thread exited")


# ------------------------------------------------------------------
# Module-level instance
# ------------------------------------------------------------------

_loop_instance: Optional[ControlLoop] = None


def get_loop() -> Optional[ControlLoop]:
    return _loop_instance


def initialize_control_loop(ip: str, slot: int = 0) -> ControlLoop:
    global _loop_instance
    _loop_instance = ControlLoop(ip=ip, slot=slot)
    logger.info(f"ControlLoop initialized for {ip} slot {slot}")
    return _loop_instance