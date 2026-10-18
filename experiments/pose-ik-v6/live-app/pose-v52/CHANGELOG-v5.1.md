# v5.1: three licensed motion inputs; core unchanged

Relative to the preserved v5 ZIP, application changes are restricted to clip data, UI/version and source metadata. Worker, joint policy, frozen-v4 policy and frame queue are byte-identical. Inference, thresholds, predictions, render logic and clock/scheduling code were not changed. The full application diff is v5-to-v5.1-inputs.diff.

Primary input bundle:
- commons-overhead25: 25 fps overhead kettlebell squat, 1280×720, 385 frames / 15.4 s. Author Cavemantraining (Taco Fleur), CC BY-SA 4.0. VP9 to H264, audio removed, no spatial scaling; every selected original video frame retained, source PTS minus 0.043 s.
- commons-jumping2997: original 640×480 jumping jacks/burpees, about 29.97 fps, first 599 frames / 19.986 s. Author Taco fleur (Cavemantraining), CC BY-SA 4.0. VP8 to H264, audio removed, no scaling or frame-rate upsampling; PTS minus 0.003 s. This is neither basketball nor 720p.
- commons-pirouettes25: 25 fps ballet turns, 1280×720, 434 frames / 17.36 s. Author Fanny Schertzer, CC BY-SA 3.0. Original 1920×1080 downscaled, Theora to H264, audio removed, all video frames and PTS retained.

Original source files remain separately preserved. Packaged media are explicitly marked as derived and attributed under their source licenses. Source and derived SHA256, changes and per-frame mapping are in active-candidates.json and the input ZIP. None are the unavailable historical Pexels input bytes; tested frame rates are 25 / 29.97 / 25, not the historical 24 / 25 / 30 combination.

A further optional 30 fps single-leg squat selector is retained in the UI but is not in the primary input bundle or three final v5.1 runs. Existing v5 ZIPs and prior logs are retained unchanged; new runs use distinct names.
