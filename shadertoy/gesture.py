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
        self._hand_depth_ref = 0.0  # 手掌中心深度参考，用于补偿深度变化导致的xy跳变
        self._pinch_enabled = True  # 握拳检测开关（默认开启）

        self.thread = None
        self.cap = None
        self._landmarker = None
        self._pub_thread = None
        self._pipe_listener = None
        self._frame_log_counter = 0

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
            return self._hand_pos.copy(), self._hand_action, self._hand_depth_ref

    def set_pinch_enabled(self, enabled: bool):
        """Enable or disable pinch/grip detection."""
        with self._lock:
            self._pinch_enabled = enabled

    def is_pinch_enabled(self) -> bool:
        """Check if pinch detection is enabled."""
        with self._lock:
            return self._pinch_enabled

    def start_capture(self):
        if self._running:
            return

        if self.mode == "native":
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision

            self._require_local_model()

            # 尽量降低摄像头内部缓冲，减少“读到旧帧”的延迟
            backend = getattr(cv2, "CAP_DSHOW", None)
            if backend is not None and os.name == "nt":
                self.cap = cv2.VideoCapture(self.camera_index, backend)
            else:
                self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"Could not open camera {self.camera_index}. "
                    "可能原因包括：摄像头被占用、Windows 隐私设置禁止桌面应用访问摄像头，或设备索引不正确。"
                )

            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
            except Exception:
                pass

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
        # 降低平滑带来的时滞，位置比动作更重要
        # 改进：手腕比手指尖更稳定，可以用更强的平滑（更小的alpha）来消除微小波动
        alpha_pos = float(os.environ.get("SHADERTOY_GESTURE_POS_ALPHA", "0.45"))
        alpha_action = float(os.environ.get("SHADERTOY_GESTURE_ACTION_ALPHA", "0.4"))

        try:
            while self._running:
                loop_start = time.perf_counter()
                success, frame = self.cap.read()
                if not success:
                    time.sleep(0.01)
                    continue
                read_ms = (time.perf_counter() - loop_start) * 1000.0

                detect_start = time.perf_counter()
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
                target_depth_ref = 0.0

                if results.hand_landmarks:
                    hand_landmarks = results.hand_landmarks[0]
                    
                    # 焦点坐标：使用手腕(landmark 0)而非手指尖(landmark 8)作为焦点源
                    # 原因: 手腕随手部整体运动，不受手指弯曲影响，更稳定
                    wrist = hand_landmarks[0]
                    target_pos = np.array([wrist.x, 1.0 - wrist.y, wrist.z], dtype=np.float32)
                    
                    # 计算手掌中心深度参考: 手腕(0) + 中指尖(12) + 无名指尖(16) 的平均
                    # 用作深度感知补偿的参考值
                    palm_depth = (hand_landmarks[0].z + hand_landmarks[12].z + hand_landmarks[16].z) / 3.0
                    target_depth_ref = float(palm_depth)

                    # 握拳检测：只基于xy距离（忽略z方向波动）
                    # 这样可以避免深度变化导致的握拳状态频繁抖动
                    # 握拳时=默认大小，张开时=放大
                    if self._pinch_enabled:
                        thumb_tip = hand_landmarks[4]
                        index_tip = hand_landmarks[8]
                        dx = thumb_tip.x - index_tip.x
                        dy = thumb_tip.y - index_tip.y
                        # 仅使用xy平面距离，忽略z方向噪声
                        dist = (dx**2 + dy**2) ** 0.5

                        pinch_max = 0.02
                        pinch_min = 0.1
                        if dist <= pinch_max:
                            target_action = 1.0
                        elif dist >= pinch_min:
                            target_action = 0.0
                        else:
                            target_action = 1.0 - (dist - pinch_max) / (pinch_min - pinch_max)
                    else:
                        # 握拳检测关闭，保持为握拳状态（target_action = 0.0）
                        target_action = 0.0

                detect_ms = (time.perf_counter() - detect_start) * 1000.0

                smooth_pos = smooth_pos * (1 - alpha_pos) + target_pos * alpha_pos
                smooth_action = smooth_action * (1 - alpha_action) + target_action * alpha_action

                with self._lock:
                    self._hand_pos = smooth_pos
                    self._hand_action = smooth_action
                    self._hand_depth_ref = target_depth_ref

                self._frame_log_counter += 1
                if self._frame_log_counter % 60 == 0:
                    total_ms = (time.perf_counter() - loop_start) * 1000.0
                    print(
                        f"[gesture] frame={self._frame_log_counter} read_ms={read_ms:.1f} "
                        f"detect_ms={detect_ms:.1f} total_ms={total_ms:.1f}"
                    )

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
                                float(self._hand_depth_ref),
                            )

                        try:
                            conn.send(payload)
                        except (EOFError, BrokenPipeError, OSError):
                            break

                        time.sleep(1.0 / 60.0)
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

                    if not payload or len(payload) != 5:
                        continue

                    x, y, z, a, depth_ref = payload
                    with self._lock:
                        self._hand_pos = np.array([x, y, z], dtype=np.float32)
                        self._hand_action = float(a)
                        self._hand_depth_ref = float(depth_ref)

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