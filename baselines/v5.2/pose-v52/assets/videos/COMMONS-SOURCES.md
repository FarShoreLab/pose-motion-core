# v5.1 新输入：来源、许可和真实帧审计

冻结时间：2026-10-10 18:13:35 UTC。媒体字节与 `active-candidates.json` 此后不再修改。

## 适用范围

这三段是重新获取、许可明确的真人运动视频，供后续版本在相同新输入上比较。它们不是历史 Pexels 三原片，不能声称复现历史测试的相同画面、SHA256 或 24/25/30 fps 组合。

实测的是 Commons 已发布原文件的帧率和时间戳；没有独立验证摄像机拍摄帧率或上传前处理过程。本地没有补帧、插值、升帧率或复用程序运行录屏作为输入。

快动作改为开合跳/波比跳，非篮球投篮。该片原生发布分辨率为 640×480，未上采样，不能算原720p。芭蕾源1080p仅空间缩小到720p；深蹲源即720p。

## 首选慢动作：Overhead Kettlebell Squat

- 来源：https://commons.wikimedia.org/wiki/File:Overhead_Kettlebell_Squat.webm
- 作者：Cavemantraining / Taco Fleur。来源页面标为作者自作，日期2020-10-07。
- 许可：CC BY-SA 4.0，https://creativecommons.org/licenses/by-sa/4.0/
- 原文件：`candidates-commons/overhead-kettlebell-squat.webm`，1280×720，r/avg=25/1，385帧。原容器16.067秒含较长音轨；视频PTS为0.043至15.403秒，每帧40ms。
- 正式输入：`candidates-commons/overhead-kettlebell-squat-720p.mp4`，1280×720，25/1 fps，385个不同解码帧，15.400秒。
- 处理：移除音轨、VP9转H264；保留所有原帧顺序，PTS统一减0.043秒，无空间缩放。为避免本机FFmpeg7.1.5把末帧排除在MP4编辑时间段之外，明确设置40ms包时长；最终ffprobe实际解码385帧通过。
- 视觉：一个真人在花园举壶铃和深蹲，全身可见。

## 首选快动作：Jumping jacks and burpees

- 来源：https://commons.wikimedia.org/wiki/File:Jumping_jacks_and_burpees.webm
- 作者：Taco fleur / Cavemantraining。来源页面标为作者自作，日期2017-11-15。
- 许可：CC BY-SA 4.0，https://creativecommons.org/licenses/by-sa/4.0/
- 原文件：`candidates-commons/jumping-jacks-and-burpees.webm`，640×480，r/avg=2997/100，即29.97fps。1356个不同解码帧；容器45.293秒。原视频PTS为0.003至45.215秒，间隔33或34ms。
- 正式输入：`candidates-commons/jumping-jacks-burpees-20s.mp4`。连续选原帧索引0至598（599帧），原PTS0.003至19.956秒；输出PTS0至19.953秒，逐帧统一减0.003秒。末帧显示33ms，总19.986秒。
- 输出ffprobe：r_frame_rate=30000/1001，avg_frame_rate=299500/9993。它们是对保留毫秒PTS序列及19.986秒容器时长的有理数描述；没有改成CFR。app输入fps元数据29.97采用源声明值。
- 处理：连续截取、移除音轨、VP8转H264；无缩放、无插值；保持每个选中源帧的一一索引对应和33/34ms时间间隔。
- 视觉：一个真人正面连续开合跳及俯身波比跳，全身可见；场景边缘器材，不是多人实战。

## 首选挑战动作：Grands battements et pirouettes

- 来源：https://commons.wikimedia.org/wiki/File:Grands_battements_et_pirouettes.ogv
- 作者：Fanny Schertzer（Commons用户Inisheer）；作者自作，2010年1月，Wikimedia CH支持。
- 选择许可：CC BY-SA 3.0，https://creativecommons.org/licenses/by-sa/3.0/ 。来源同时提供其他许可；本交付明确选择3.0。
- 原文件：`candidates-commons/grands-battements-pirouettes.ogv`，1920×1080，25/1fps，434个不同帧；视频17.36秒，容器17.392396秒。
- 正式输入：`candidates-commons/grands-battements-pirouettes-720p.mp4`，1280×720，25/1fps，434个不同帧，17.360秒。
- 处理：Lanczos空间缩小，移除音轨，Theora转H264。全部434帧的PTS原样保留为0至17.32秒，均相隔40ms。
- 视觉：单人芭蕾，完整四肢可见；抬腿、前侧背转身、自遮挡。舞者在宽景中相对较小，非重度多人遮挡。

## 可复现证据

`commons-input-manifest.json`包含原始直接下载URL、页面URL、作者、许可、原文件SHA1与Commons公开SHA1匹配结果、源/派生SHA256、完整ffprobe字段、精确处理命令、帧数及PTS审计。

各片旁的 `.ffprobe.json`、`.frame-pts.json`、`.framemd5`、`.frame-audit.json`、`.source-frame-map.csv`提供可检查证据；原始接触表 `.contact.jpg`仅用于选片。

三正式派生帧分别为385、599、434，全部不同、没有相邻重复，数量与选中源帧相同；源→输出每帧时间戳固定偏移分别为-0.043、-0.003、0秒。这证明本次处理没有增删所选帧或插帧；有损H264与源像素哈希不同，不声称字节或像素无损。

原始媒体SHA1都与Commons页面公布值一致。初次默认urllib请求收到明确要求设置User-Agent的机器人政策提示；按官方User-Agent政策使用真实标识的机器人请求后获得HTTP200，未假冒浏览器或使用凭据。该办法没有用于被拒绝的Pexels。

## 分发署名与许可

媒体及其视频派生仍受各自CC BY-SA许可约束，不因与程序一起打包而变成程序代码许可。请保留作者、来源、许可链接及上述变更说明；对包含这些画面的改编视频、叠加骨架录屏、接触表等，同样保留相应署名和适用的ShareAlike许可。作者不因此认可本项目。

建议随慢动作和快动作录屏附：
“Video by Cavemantraining / Taco Fleur, via Wikimedia Commons, CC BY-SA 4.0. Changes: source video transcoded; audio removed; fast clip trimmed; pose overlays/UI added in test recordings.”

建议随挑战录屏附：
“Video by Fanny Schertzer, supported by Wikimedia CH, via Wikimedia Commons, CC BY-SA 3.0. Changes: downscaled1080p to720p, transcoded, audio removed; pose overlays/UI added in test recordings.”

## 排除和打包

只把manifest三个正式id对应的MP4、其三份源文件及相关审计/来源文档作为这一组正式输入。`basic-single-leg-squat.webm`是真人30fps补充但低分辨率；不替代首选慢动作。`basketball-training-4.ogv`多人实战不合格；`kettlebell-goblet-squat.webm`非首选。

`overhead-kettlebell-squat-720p-fixed.mp4`是中间失败调试文件，不应分发或测试。`candidates-openmmlab`及Google pose_1合成视频不属于此组三真人素材。旧Pexels原片恢复仍受403阻碍；详见 `restoration-report.json`。
