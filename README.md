# ShaderToy-like audio visualizer framework

This workspace contains a minimal ShaderToy-like viewer that loads a GLSL fragment shader and provides a fixed set of uniforms including audio FFT data.

Files:

- `viewer.py` - Minimal OpenGL viewer that loads a fragment shader and uploads an audio FFT as `iChannel0`.
- `audio_recorder.py` - Existing audio capture helper that looks for loopback devices (Stereo Mix) on Windows.
- `test.glsl` - Example fragment shader demonstrating a simple bar visualization using `iChannel0`.
- `requirements.txt` - Python dependencies.

How to run (PowerShell):

```powershell
python -m pip install -r requirements.txt
python viewer.py test.glsl
```

Notes:

- If `audio_recorder.py` finds a loopback device (Stereo Mix), the viewer will use it; otherwise a synthetic FFT will be used.
- To add more shaders, create files in a `shaders/` folder and run `viewer.py shaders/your.glsl`.

Next steps you can ask me to implement:

- Upload FFT into a 1D texture properly and add smoothing/time decay.
- Add a small UI to switch shaders and control parameters.
- Integrate an AI prompt generator that emits GLSL fragment shaders given a style description and required uniforms.
