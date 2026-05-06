import os
import threading
import time
from multiprocessing.connection import Client, Listener
from pathlib import Path

import numpy as np


class GestureTracker:
    """Background thread for tracking hand gestures using MediaPipe Tasks."""

    DEFAULT_PIPE_NAME = r"\\.\pipe\shadertoy_gesture"
    PIPE_AUTHKEY = b"shadertoy-gesture-v1"

    def __init__(
        self,
        camera_index: int = 0,
        model_path: str | None = None,
        mode: str = "native",
        pipe_name: str | None = None,
    ):
        """
        mode: 'native' -> capture via camera + mediapipe
              'remote' -> receive gesture packets from native publisher via Windows named pipe
        pipe_name: named pipe address. Defaults to SHADERTOY_GESTURE_PIPE or \\.\pipe\shadertoy_gesture.
        """
        self.camera_index = camera_index
        self.mode = mode
        self.pipe_name = pipe_name or os.environ.get("SHADERTOY_GESTURE_PIPE", self.DEFAULT_PIPE_NAME)
        self.model_path = self._resolve_model_path(model_path) if mode == "native" else None

        self._running = False
        self._lock = threading.Lock()

        self._hand_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._hand_action = 0.0

        self.thread = None
        self.cap = None
        self._landmarker = None
        self._pub_thread = None
        self._pipe_listener = None

    def _resolve_model_path(self, model_path: str | None) -> Path:
        candidates = []
        env_path = os.environ.get("SHADERTOY_HAND_LANDMARKER_MODEL")
        if model_path:
            candidates.append(Path(model_path))
        if env_path:
            candidates.append(Path(env_path))

        default_dir = Path(__file__).resolve().parent / "assets"
        default_path = default_dir / "hand_landmarker.task"
        candidates.append(default_path)

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return default_path

    def _require_local_model(self) -> Path:
        if self.model_path is None:
            raise RuntimeError("gesture model path is not configured")
        if self.model_path.is_file():
            return self.model_path
        raise RuntimeError(
            f"本地手势模型不存在: {self.model_path}. "
            "请将 hand_landmarker.task 固定到仓库路径，或通过 SHADERTOY_HAND_LANDMARKER_MODEL 指定本地文件。"
        )

    def get_gesture_data(self):
        """Return a copy of the current gesture data thread-safely."""
        with self._lock:
            return self._hand_pos.copy(), self._hand_action

    def start_capture(self):
        if self._running:
            return

        if self.mode == "native":
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision

            self._require_local_model()

            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"Could not open camera {self.camera_index}. "
                    "可能原因包括：摄像头被占用、Windows 隐私设置禁止桌面应用访问摄像头，或设备索引不正确。"
                )

            base_options = mp_tasks.BaseOptions(model_asset_path=str(self.model_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)

            self._running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

            self._pub_thread = threading.Thread(target=self._pipe_publisher_loop, daemon=True)
            self._pub_thread.start()

        elif self.mode == "remote":
            self._running = True
            self.thread = threading.Thread(target=self._pipe_client_loop, daemon=True)
            self.thread.start()

        else:
            raise ValueError(f"Unknown GestureTracker mode: {self.mode}")

    def stop_capture(self):
        self._running = False

        if self._pipe_listener is not None:
            try:
                self._pipe_listener.close()
            except Exception:
                pass
            self._pipe_listener = None

        if self.thread:
            self.thread.join(timeout=0.5)

        if self.cap:
            self.cap.release()

        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None

        if getattr(self, "_pub_thread", None):
            try:
                self._pub_thread.join(timeout=0.5)
            except Exception:
                pass

    def _capture_loop(self):
        import cv2
        import mediapipe as mp

        if self._landmarker is None:
            print("[gesture] hand landmarker was not initialized")
            self._running = False
            return

        smooth_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        smooth_action = 0.0
        alpha = 0.3

        try:
            while self._running:
                success, frame = self.cap.read()
                if not success:
                    time.sleep(0.01)
                    continue

                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = cv2.flip(image, 1)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)

                try:
                    results = self._landmarker.detect(mp_image)
                except RuntimeError as e:
                    message = str(e)
                    if "cannot schedule new futures after shutdown" in message.lower():
                        print("[gesture] landmarker is shutting down, stopping capture loop")
                        break
                    raise

                target_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                target_action = 0.0

                if results.hand_landmarks:
                    hand_landmarks = results.hand_landmarks[0]
                    index_tip = hand_landmarks[8]
                    target_pos = np.array([index_tip.x, 1.0 - index_tip.y, index_tip.z], dtype=np.float32)

                    thumb_tip = hand_landmarks[4]
                    dx = thumb_tip.x - index_tip.x
                    dy = thumb_tip.y - index_tip.y
                    dz = thumb_tip.z - index_tip.z
                    dist = (dx**2 + dy**2 + dz**2) ** 0.5

                    pinch_max = 0.02
                    pinch_min = 0.1
                    if dist <= pinch_max:
                        target_action = 1.0
                    elif dist >= pinch_min:
                        target_action = 0.0
                    else:
                        target_action = 1.0 - (dist - pinch_max) / (pinch_min - pinch_max)

                smooth_pos = smooth_pos * (1 - alpha) + target_pos * alpha
                smooth_action = smooth_action * (1 - alpha) + target_action * alpha

                with self._lock:
                    self._hand_pos = smooth_pos
                    self._hand_action = smooth_action

        finally:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception:
                    pass

    def _pipe_publisher_loop(self):
        """Publish latest gesture data to a Windows named pipe."""
        listener = None
        try:
            listener = Listener(self.pipe_name, family="AF_PIPE", authkey=self.PIPE_AUTHKEY)
            self._pipe_listener = listener
            print(f"[gesture] named pipe publisher ready at {self.pipe_name}")

            while self._running:
                try:
                    conn = listener.accept()
                except Exception:
                    if self._running:
                        time.sleep(0.1)
                    continue

                try:
                    while self._running:
                        with self._lock:
                            payload = (
                                float(self._hand_pos[0]),
                                float(self._hand_pos[1]),
                                float(self._hand_pos[2]),
                                float(self._hand_action),
                            )

                        try:
                            conn.send(payload)
                        except (EOFError, BrokenPipeError, OSError):
                            break

                        time.sleep(1.0 / 30.0)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        except Exception as e:
            if self._running:
                print(f"[gesture] named pipe publisher failed: {e}")
        finally:
            if listener is not None:
                try:
                    listener.close()
                except Exception:
                    pass
            if self._pipe_listener is listener:
                self._pipe_listener = None

    def _pipe_client_loop(self):
        """Receive gesture data from the named pipe publisher."""
        last_error_logged = None
        while self._running:
            conn = None
            try:
                conn = Client(self.pipe_name, family="AF_PIPE", authkey=self.PIPE_AUTHKEY)
                print(f"[gesture] named pipe client connected to {self.pipe_name}")
                last_error_logged = None

                while self._running:
                    try:
                        payload = conn.recv()
                    except EOFError:
                        break

                    if not payload or len(payload) != 4:
                        continue

                    x, y, z, a = payload
                    with self._lock:
                        self._hand_pos = np.array([x, y, z], dtype=np.float32)
                        self._hand_action = float(a)

            except Exception as e:
                error_text = str(e)
                if error_text != last_error_logged:
                    print(f"[gesture] named pipe client waiting: {e}")
                    last_error_logged = error_text
                if self._running:
                    time.sleep(0.2)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass