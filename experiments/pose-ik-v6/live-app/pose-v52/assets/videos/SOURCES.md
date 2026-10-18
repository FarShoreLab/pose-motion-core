# Motion test footage sources

Three individually downloaded Pexels clips for the real-time skeleton demonstration. All three MP4s are original provider bytes. No frames were inserted, repeated, interpolated or rate-converted; no speed change or crop/trim was applied. The source interval is the whole video in every case.

## Formal inputs

### Slow full-body squats
- File: `slow-squats-24fps.mp4`
- Source: [Woman Doing Squats](https://www.pexels.com/video/woman-doing-squats-4838220/)
- Creator: [Anna Shvets](https://www.pexels.com/@shvetsa/)
- Exact downloaded rendition: https://videos.pexels.com/video-files/4838220/4838220-hd_720_1280_24fps.mp4
- 720 × 1280; native 24/1 fps; 12.666667 seconds; 304 video frames
- Whole source interval: 0–12.666667 seconds. Source website rounds duration to 13 seconds.
- SHA-256: `731c7d6c294c84e883de499bbbd4ce0bdeb6fcdd68d55845334c05db7c5f9c91`
- Decoded-frame audit: 304 unique hashes / 304 frames; 0 adjacent exact duplicates; strictly increasing timestamps.
- Visual review: A single woman performs controlled squats facing three-quarter toward camera. Full head, hands and both feet stay in frame in inspected samples. A resistance band is visible above knees; her hands overlap during squats. Even indoor background.

### Basketball shot
- File: `fast-basketball-25fps.mp4`
- Source: [Man Shooting a Basketball](https://www.pexels.com/video/man-shooting-a-basketball-4964842/)
- Creator: [olia danilevich](https://www.pexels.com/@olia-danilevich/)
- Exact downloaded rendition: https://videos.pexels.com/video-files/4964842/4964842-hd_720_1280_25fps.mp4
- 720 × 1280; native 25/1 fps; 7.2 seconds; 180 video frames
- Whole source interval: 0–7.2 seconds. Source website rounds duration to 7 seconds.
- SHA-256: `bdcb5739052f6af48963d82ee4add3d0d438334d34052f62705b54f72c065d94`
- Decoded-frame audit: 180 unique hashes / 180 frames; 0 adjacent exact duplicates; strictly increasing timestamps.
- Visual review: A single man performs a basketball shot, viewed from behind/slightly to the side. Full body remains visible; both hands and ball overlap near the upper torso and above the head. This is a moderately fast natural shot, not an extreme-motion or frontal test.

### Full-body turns and self-occlusion
- File: `challenge-turn-30fps.mp4`
- Source: [Man Dancing On the Street](https://www.pexels.com/video/man-dancing-on-the-street-8928136/)
- Creator: [RDNE Stock project](https://www.pexels.com/@rdne/)
- Exact downloaded rendition: https://videos.pexels.com/video-files/8928136/8928136-hd_1280_720_30fps.mp4
- 1280 × 720; native 30/1 fps; 15.666667 seconds; 470 video frames
- Whole source interval: 0–15.666667 seconds. Source website rounds duration to 16 seconds.
- SHA-256: `cdf33018bc3c0fb2e36deb34f3673ce5222da3529a6924d73765ed622867ef49`
- Decoded-frame audit: 470 unique hashes / 470 frames; 0 adjacent exact duplicates; strictly increasing timestamps.
- Visual review: A single man street-dances with fast footwork, hops, repeated front/side/back turns and limb self-occlusion. Full body is visible in a dense contact sheet sampled every0.5seconds. Subject is smaller in frame than in the portrait clips; outdoor shadows and body yaw add difficulty.

## Permission scope

The current [Pexels License](https://www.pexels.com/license/) permits free use and modification subject to restrictions. Attribution is appreciated but not required. These clips are credited above. The [Pexels Terms](https://www.pexels.com/terms-of-service/) were checked on 8 October 2026; the page is dated 15 November 2024. Downloading/using the content is subject to those terms.

Use these as embedded inputs in the pose demonstration. Do not distribute these substantially unmodified MP4s as a standalone stock-video bundle. Do not imply that the depicted people endorse the project, make offensive claims about them, or assert exclusive ownership. Additional third-party rights may apply; Pexels does not warrant all releases. This collection does not assert permission for AI training or biometric identification.

## What this verifies

`manifest.json` records sources, exact download URLs, source/output duration, original frame rate, dimensions, hashes and audit results. `../video-provenance/*-ffprobe.json` and `*.framemd5` contain the full technical evidence. Timestamps are native source presentation timestamps; fractional values in the manifest are rounded to six decimals by ffprobe.

This proves that the input is genuine 24/25/30-fps video with distinct decoded frames. It does not prove that inference kept up in a given browser. Runtime reports must independently measure processed video timestamps, inference rate, end-to-end wall time, dropped/held frames and actual throughput. A nominal display refresh rate alone is not inference throughput.

The basketball clip is a rear-view, moderately fast shot; it is not a hard extreme-speed benchmark. The dance clip supplies faster footwork, body turns and self-occlusion. The separate 5-fps Google squat is a smoke-test only and is not part of this formal three-clip set.
