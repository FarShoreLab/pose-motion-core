# Independent v4 audit

## Verdict

The specific display/uncertainty changes pass: the video snapshot, filtered 2D observations and filtered 3D observations share the exact frame ID/epoch/source PTS; unsupported joints are absent rather than connected as reliable observations. Live predictions are a separate amber dashed display, use only already-observed history, expire after 150 ms from each joint's latest measured source PTS, and are never counted as new detections. Offline replay repair uses only short, same-context measured brackets, has purple labels, and can be turned off to restore unrepaired observations.

This is **sparse frame-paired observation playback**, not full native-video-cadence motion. The recorded natural runs do **not** meet the former 20-new-valid-poses/s or 200 ms P95 delay targets. Three 22-second runs do not establish a 60-second stability pass. Exact pairing is achieved by retaining the same captured frame until its result, not by eliminating inference latency.

## Independently recomputed final recorded natural runs

| Clip | Window (s) | Paired updates | Raw-valid paired FPS | Strict-valid paired FPS | New-pair delay P95 (ms) | Held-image age P95 (ms) | Blank reset/start time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Slow squat | 22.002 | 218 | 9.91 | 9.82 | 241.8 | 304.0 | 2.535 |
| Basketball | 22.002 | 162 | 7.36 | 0.00 | 446.6 | 587.4 | 5.138 |
| Turn | 22.001 | 203 | 9.23 | 5.50 | 233.1 | 293.6 | 2.605 |

All 583 final paired updates have equal video/2D/3D frame IDs and zero same-frame PTS mismatch. All three audits pass phase causality, original source-clock mapping, immutable measured coordinates, per-joint state handling, unique observation counting, prediction provenance, and delay arithmetic.

Raw-valid uses the unchanged v3 average confidence criterion. Strict-valid requires all 12 major joints to pass the new per-joint gate. Do not compare v3 raw-valid FPS directly with v4 strict-valid FPS. Basketball's zero strict-valid rate means at least one of those major joints remained unsupported, even though other joints are shown.

The new-pair delay ends at software draw submission. Held-image age accounts continuously for the age of a frozen paired image until the next update or reset; blanks are counted separately. Neither is a physical photon measurement. Gaps between new pairs reached 2.04/2.40/2.13 seconds, including model reset intervals.

## Natural footage versus injected missingness

Final slow/fast/challenge logs have synthetic_fault_injection=false. A basketball recording frame visibly shows 24 measured and 9 uncertain joints, with missing limb segments absent. Confidence states are not perfect labels of real physical occlusion; high-confidence model errors may remain. There is no ground-truth 3D accuracy validation.

The repair demonstration intentionally masks five left-arm joints on selected frames, sets synthetic_fault_injection=true, and visibly labels the intervention. Its success is a controlled handling test, not proof of recovering real occluded anatomy. The replay log includes 70 repaired-joint displays across 14 updates and 46 unrepaired-toggle updates; all tested repair brackets are <=350 ms and same-epoch/same-clip. The off toggle restores original confidence-filtered observations. Full unmodified model arrays remain in raw logs.

## Video and source evidence

- results/new-live-v4.mp4: 100.000-second H.264 recording, 1364x1024, 30 fps. Recorded command uses ffmpeg x11grab of the actual cloud desktop, not offline trajectory rendering. SHA-256: bd32de94fa5ef9cd2a6c1534892a6dec8763e2c41277f59734e51e23afe53b0b.
- The basketball screenshot at recording 36.5 s shows frame 95, source PTS 4.920 s, 24 measured/9 uncertain. Raw pair wall time maps to recording 36.364 s.
- The turning screenshot at recording 60 s shows frame 83, source PTS 4.233333 s, 33 measured. Raw pair wall time maps to recording 59.841 s.
- results/replay-v4.mp4: actual 55.000-second desktop recording. Independently extracted replay frames show purple repaired joints with offline/future-bracket/synthetic labels, and the unchecked toggle with the corresponding unsupported joints absent.
- In that recording, amber dashed live prediction is visible at about 16.118 s and absent at about 16.168 s when it exceeds the horizon. Policy tests and sampled raw provenance provide the precise bound; recording frames are not an independent submillisecond timing instrument.
- results/source-snapshot/SHA256SUMS passes and matches current app files. Final app SHA-256: 5f8eb5f94d8b8fe0722d4c0892813a3001be874738dad1509d3556a0d1f7ddde. Policy: 0385f6c8758f323f45a02a8185ee46d4e41618186a4ca24e0fc7e7a5227d78ed. Worker: 215c9a6317ddfdc0e581892f00b60aaccb3ca574639b1826ba3c22e75e67161e (unchanged from v3).

## Verification and limitations

- npm test rerun: JavaScript syntax, 14 independent policy tests, 14 auditor tests and HTTP Range checks pass.
- audit_v4/audit_raw.py independently audits raw exports; run-specific *.audit.json files include input SHA-256.
- Policy tests exercise immutable frozen input; confidence absence/nonfinite input; local loss and recovery; synthetic labels; exact horizon boundary; reset/backwards-time/long-gap behavior; bounded velocity; short bracket repair; missing leading/trailing endpoints; and no repair across epochs.
- Auditor failure-injection tests reject mismatched identities, shortened delay, future inference/prediction, rewritten measured coordinates, estimate-as-detection counts, invalid repair endpoints/toggles, duplicate observation counts, and incorrect hold-age accounting.
- Prediction event logs are sampled at roughly 200 ms, not every preview redraw; the between-sample bound is established by source inspection and pure policy tests.
- Exact image identity relies on the retained capture bitmap path plus the earlier browser frame-identity diagnostic. Log equality alone cannot establish image pixels. No new coded-frame browser diagnostic was run for v4.
- Natural 60-second sustained runs and a full interrupted-controls runtime matrix were not rerun as part of this audit. Unit reset tests and recorded loop/clip/replay transitions are covered.
- Preserved v3 source hashes still match its original final report. Initial v4 22-second prechecks are separately labeled under results/precheck and are not substituted for final recorded runs.

## Reproduce

node --test audit_v4/test_joint_policy_independent.mjs

python3 -m unittest discover -s audit_v4 -p 'test_*.py' -v

python3 audit_v4/audit_raw.py results/slow-v4.json --out audit_v4/slow-v4.audit.json

Repeat the raw audit for fast-v4.json, challenge-v4.json and repair-demo-v4-replay.json. This audit does not edit app files or generate model outputs.

## Before/after visual comparison check

`deliverables/before-after-v3-v4-20s.mp4` is a 19.967-second, 30 fps sequential comparison. Inspected frames from each half. The first half is explicitly titled “BEFORE - final-v3 | same basketball source, separate live run”; the second identifies v4 strict-paired observations and hidden missing joints. The v3 sample visibly has displayed PTS 3.480 s versus pose PTS 3.360 s; the v4 sample displays matching 4.440 s video/3D PTS and identifies unsupported joints. They are separate live runs at different source moments, not a synchronized accuracy benchmark. The comparison's labels do not imply a speed, accuracy, or native-cadence performance pass.
