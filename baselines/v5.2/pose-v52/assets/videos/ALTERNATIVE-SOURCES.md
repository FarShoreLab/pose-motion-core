# Video-input restoration, 10 October 2026

## Original three clips remain unavailable

The original Pexels squats, basketball, and turning-dance inputs named in `manifest.json` were not present in the earlier delivery archives. All three pinned HD URLs, and all three current default higher-resolution downloads linked from their public official pages, returned HTTP 403. The current rendition attempts returned Cloudflare `error code: 1010`. No user-agent impersonation, access-control bypass, mirror, or prior demonstration recording was used.

`manifest.json` and `SOURCES.md` are unchanged historical provenance. Their hashes and technical fields are not fresh verification of files currently present. See `restoration-report.json` for explicit unavailable-file status.

## Available independent alternatives

The following are original bytes from Intel's dedicated public sample-video repository. Its media repository uses [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with the [repository license](https://github.com/intel-iot-devkit/sample-videos/blob/master/LICENSE) retained locally as `intel-LICENSE`. Credit: Intel IoT DevKit sample-videos contributors. Retain attribution and the license link in any demo/report containing these videos; describe any changes made. This acquisition made no edits.

1. `intel-worker-zone-detection.mp4`: [source](https://github.com/intel-iot-devkit/sample-videos/blob/master/worker-zone-detection.mp4). Real people walking and turning in a work area, viewed from above. Several intervals contain one person, while others contain two. Native 60000/1001 fps; 1920 × 1080; 75.875800 seconds; 4548 decoded frames. All frames are retained. This is a walking/turning test, not a squat, basketball, or dance test.
2. `intel-store-aisle-detection.mp4`: [source](https://github.com/intel-iot-devkit/sample-videos/blob/master/store-aisle-detection.mp4). Several people walk among shelves and overlap. Native 60000/1001 fps; 720 × 404; 65.415350 video seconds; 3921 decoded frames. This is an optional multi-person/occlusion stress input, not a clean single-person benchmark.

`alternative-input-manifest.json` records exact SHA-256, byte sizes, video and container durations, attribution, and full-source intervals. The matching `.ffprobe.json`, `.framemd5`, `.frame-audit.json`, and `.frame-pts.json` files contain fresh technical verification. The providers' original videos contain a small number of exactly repeated decoded frames; this is disclosed in the audit and was not introduced here. No interpolation or FPS conversion was performed. Contact sheets are review-only, not benchmark inputs.

These scenes cannot establish performance on the missing three clips or reproduce their historical results. A new paired comparison can use identical alternative-file bytes in both implementations and clearly state its limited motion coverage.

## Auxiliary test files, excluded from real high-frame-rate claims

- `smoke-google-squats-5fps.mp4` is the existing TensorFlow public [squats fixture](https://github.com/tensorflow/tfjs-models/blob/master/pose-detection/test_data/pose_squats.mp4): 720 × 1280, 5 fps, 13 seconds, 65 decoded frames. It is useful only for smoke tests; it proves neither 24-fps input nor sustained 24-fps inference.
- `alternative-google-pose-1.mp4` is the TensorFlow public [pose fixture](https://github.com/tensorflow/tfjs-models/blob/master/pose-detection/test_data/pose_1.mp4): 576 × 576, 30 fps, 4 seconds, 120 decoded frames. [The official test describes it as synthetic](https://github.com/tensorflow/tfjs-models/blob/master/pose-detection/src/movenet/movenet_test.ts). It must not be presented as real-camera evidence. No separate media redistribution license was confirmed for these two Google fixtures; do not infer one solely from a code license.
- `intel-one-by-one-person-detection.mp4` and `intel-face-demographics-walking-and-pause.mp4` are additional CC BY 4.0 Intel media candidates, measured at 10 and 12 fps respectively. They were not selected for the high-frame-rate evaluation.

`active-inputs.json` offers explicit separate input IDs and labels for implementation. It does not rename alternatives to the missing Pexels filenames.
