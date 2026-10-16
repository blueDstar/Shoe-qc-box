from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"README.md"
text=path.read_text(encoding="utf-8")
text=text.replace("Robot, giày, gripper/cổ tay và vùng cảm biến là **DEMO**. Chuyển động robot là quỹ đạo proxy theo X, có xoay/nghiêng cụm giày được giữ liên tục; không có tay robot nhiều khớp hoặc IK.",
"Robot, giày, gripper, camera, đèn và cảm biến bổ sung là **DEMO**, tách khỏi STEP/BOM nguồn. Tay có hai link cứng dài 650 mm, định vị khớp bằng IK hình học và wrist xoay giày; không phải robot hãng hoặc mô hình động lực học đã xác nhận. Gripper giữ giày liên tục qua sáu mặt kiểm tra.")
text=text.replace("## Sáu tab","## Bảy tab")
text=text.replace("| LOG & EXPORT | Timestamp +07:00, event CSV/JSON, state save/load, PNG và MP4 |",
"| LOG & EXPORT | Timestamp +07:00, event CSV/JSON, state save/load, PNG và MP4 |\n| CAMERA QC | Ảnh FRONT/TOP từ scene thật, bảng sáu mặt, pose/thời điểm chụp, lưu PNG + JSON |")
text=text.replace("DEMO faults: DOOR_STALL, SENSOR_NO_OPEN, DOORWAY_BLOCKED, ROBOT_NOT_WITHDRAWN, UNKNOWN_SENSOR, SIMULTANEOUS_REQUESTS.",
"DEMO faults: DOOR_STALL, SENSOR_NO_OPEN, SENSOR_NO_APPROACH, CAMERA_NOT_READY, DOORWAY_BLOCKED, ROBOT_NOT_WITHDRAWN, UNKNOWN_SENSOR, SIMULTANEOUS_REQUESTS.")
text=text.replace("Runtime: **kiểm tra sơ bộ bảo thủ bằng swept AABB**, mỗi bước tối đa 1/120 s, gồm shutter với fixed CAD/DEMO shoe/gripper/wrist, robot proxy với khẩu độ/vỏ/ray, hai robot với nhau và shoe/proxy với chamber.",
"Runtime: **kiểm tra sơ bộ bảo thủ bằng swept AABB và capsule cho link tay**, mỗi bước tối đa 1/120 s. Bao gồm shutter với fixed CAD/giày/gripper/wrist/tay, khẩu độ/vỏ/ray, hai robot, shoe với chamber và phần cứng camera/đèn. Capsule được cắt theo lát X tại khẩu độ và chamber; obstacle dùng segment với box phình theo bán kính và chuyển động. Đó là kiểm tra bảo thủ, không phải collision mesh chính xác hoặc chứng minh an toàn liên tục.")
begin=text.find("Kết quả bản bàn giao:")
end=text.find("\n",begin)
if begin>=0:
    text=text[:begin]+"Kết quả bản cập nhật: **68 test đạt**, hai chu kỳ sáu mặt, 42,4 giây mô phỏng. Video mới `exports/Hilykan_Multiface_QC_720p.mp4`: 1280 × 720 / 30 FPS / 1272 frame / 12 capture pose. Video 1080p trước đó vẫn được giữ như bản trước cập nhật. GUI chi tiết hơn đạt **57,99 FPS** trung bình ở viewport 1335 × 774 trong lần đo riêng, Intel UHD Graphics. Xem `reports/gui_benchmark.json` và `reports/QC_UPDATE_VALIDATION.md`."+text[end:]
text=text.replace("không có articulated arm, IK", "không có robot hãng hoặc IK động lực học đã xác nhận")
text=text.replace("sáu tab và lưu ảnh","bảy tab, kiểm tra hai feed camera và lưu ảnh")
text=text.replace("controllers/            interlock guards, held DEMO body trajectory",
                  "controllers/            interlocks, fixed-link DEMO arm IK, six-face presentation")
text=text.replace("sensors/                auto signals, manual overrides, contradiction checks",
                  "sensors/                measured proximity/clear zones, endpoints, overrides")
text=text.replace("gui/                    six functional PySide6 tabs; QTimer, QThread, QProcess",
                  "gui/                    seven functional PySide6 tabs; QTimer, QThread, QProcess\nqc/                     camera geometry/projection, capture poses, lazy VTK feeds")
section="""## Cảm biến và CAMERA QC mới

Trong SENSOR SIMULATION, nhấn **LEFT Approach** hoặc **RIGHT Approach**: tay đưa giày từ ngoài tới vị trí chờ. Tín hiệu tiếp cận được đo từ bbox của giày/gripper/wrist trong vùng X ngoài ±750 đến ±495 mm, Y±165, Z160..440 mm; không suy ra từ tên trạng thái. Khi phát hiện và bật **Proximity sensor → automatic door request**, coordinator cấp lease rồi mở cửa theo interlock. Hai phía có thể cùng tiếp cận; một phía chờ. Override APPROACH=False hoặc UNKNOWN không được bỏ qua. Manual OPEN vẫn dùng guard cửa hiện có.

Cảm biến endpoint có housing/LED tại vị trí đóng và mở; cảm biến tiếp cận có housing riêng; vùng CLEAR và curtain là tín hiệu/vùng logic DEMO. LED đổi theo tín hiệu thật trong engine. CLEAR bao gồm cả forearm và wrist; không dùng APPROACH để quyết định đóng.

Camera **FRONT**: tâm quang học (0,−235,300) mm, nhìn +Y vào giày. Camera **TOP**: (0,0,507) mm, nhìn xuống −Z. Body, lens, mount và LED nằm trong chamber đã đo; có collision sơ bộ với tay/giày. Không khoét hoặc chỉnh vỏ STEP. Camera vertical FOV mặc định 90°, preview 400 × 300; chỉnh FOV và thời gian xoay/giữ trong SETTINGS khi CLOSED/withdrawn/IDLE.

INSPECT: **INNER → UPPER → OUTER → OUTSOLE → TOE → HEEL → RETURN NEUTRAL**. Mỗi mặt xoay mượt 0,8 s, giữ 0,5 s để capture. Normal của mặt được xác nhận hướng về camera FRONT và shoe bbox nằm trong FOV. Camera TOP ghi góc phụ. Xoay về neutral trước khi rút; các link tay giữ chiều dài 650 mm, gripper luôn theo giày. Nếu rút sớm, kết quả cycle là **INCOMPLETE**, không tự ghi PASS.

Mở **CAMERA QC** để xem hai ảnh render phối cảnh thật. Live preview chạy 5 FPS chỉ khi tab này mở, nên không tăng tải camera ở viewport chính. Chọn dòng trong bảng để xem đúng pose đã chụp, tắt Live; dùng **Save selected capture PNG + JSON** hoặc **Save all QC captures**. Ảnh nằm trong `exports/qc_captures/`; JSON lưu source SHA256, cửa, robot, góc, thời gian, FOV và alignment. Renderer dùng geometry cache, actor riêng; xem lại ảnh không dịch chuyển phiên live. Save-all chia từng capture qua Qt event loop.

**QC PASS/FAIL là kết quả mô phỏng đã chọn**, chưa có thuật toán phát hiện lỗi giày bằng ảnh. Vùng gripper tiếp xúc có thể che một phần ảnh; không tuyên bố kiểm tra hết vùng bị che. Camera và cảm biến chưa kết nối thiết bị thật. Hide camera bodies/FOV và QC cutaway chỉ đổi display; collision và sensor vẫn dùng geometry lắp ráp.

Chạy kiểm chứng ảnh: `.\\.venv\\Scripts\\python.exe tools\\qc_render_check.py`. Bản thử có 12 pose / 24 ảnh cho hai phía; `reports/qc_render_check.json`. Video mặc định GUI vẫn hỗ trợ 1920 × 1080 / 30 FPS, nhưng clip cập nhật bàn giao là 720p. `main.py` và `launch.bat` khởi chạy như trước.

"""
if "## Cảm biến và CAMERA QC mới" not in text:
    text=text.replace("## Video và ảnh",section+"## Video và ảnh")
path.write_text(text,encoding="utf-8")

suite=ET.parse(ROOT/"reports/tests.xml").getroot().find("testsuite")
gui=json.loads((ROOT/"reports/gui_smoke.json").read_text(encoding="utf-8"))
fps=json.loads((ROOT/"reports/gui_benchmark.json").read_text(encoding="utf-8"))
captures=json.loads((ROOT/"reports/qc_render_check.json").read_text(encoding="utf-8"))
video=json.loads((ROOT/"exports/Hilykan_Multiface_QC_720p.verification.json").read_text(encoding="utf-8"))
assert int(suite.get("failures"))==0 and int(suite.get("errors"))==0 and gui["passed"]
lines=["# Kiểm chứng bản cập nhật camera / sensor / robot DEMO", "",
       "Ngày phiên làm việc: 2026-10-10, Asia/Saigon. STEP/BOM nguồn và phạm vi PLATE_AND_BLOCKS giữ nguyên.", "",
       f"- {suite.get('tests')} test đạt, {suite.get('skipped')} skip; gồm regressions cửa, sensor bằng geometry, fixed-link IK, six-face capture, lỗi camera/proximity, pause/restore/recovery và hai video replay frame-by-frame.",
       "- Link tay cố định 650 mm; mesh DEMO nằm trong collision envelopes. Không co/giãn link để giả lập reach. Wrist/gripper/giày kết nối xuyên suốt; quỹ đạo toe→heel chọn nửa vòng trong vùng reach.",
       "- Hai chu kỳ Auto hoàn tất, IDLE, hai cửa 0 mm, không FAULT. Mỗi phía 6 mặt đều alignment cosine=1 tại capture; primary FRONT in-frame.",
       f"- {captures['captures']} pose đã render, {captures['images']} PNG FRONT/TOP thực; kiểm tra hình giày/đế/dây/cổ giày và gripper, không dùng ảnh dựng sẵn.",
       "- GUI smoke: bảy tab, nút OPEN/STOP/slider, Pause, static CAD actors, 12 capture pose, hai feed camera, chọn pose và lưu PNG/JSON.",
       f"- GUI riêng: {fps['mean_gui_fps']:.2f} FPS trung bình tại {fps['viewport_size']}, p95 interval {fps['p95_interval_ms']:.2f} ms; physics step {fps.get('mean_physics_step_ms',0):.3f} ms, scene update {fps.get('mean_scene_update_ms',0):.2f} ms, render {fps.get('mean_render_ms',0):.2f} ms. Không cam kết FPS khi encode/video hay chạy nhiều GUI đồng thời.",
       f"- H.264 mới: {video['width']:.0f} × {video['height']:.0f}, {video['fps']:.0f} FPS, {video['frames']} frame, {video['cycles']} chu kỳ, {video['qc_captures']} capture pose; final LEFT=RIGHT=0 mm. Decode thành công và replay khớp pose/state/sensor/QC từng frame.",
       "- Đã tối ưu: một actor/RGB-cell mesh cho mỗi rigid DEMO role; camera render lười ở tab QC; mapper riêng giữa cửa sổ render; cache sensor theo pose; HUD text cố định kích thước để tránh việc tính lại font mỗi frame.", "",
       "## Giới hạn thực tế", "",
       "- Sensor/camera/light/arm/shoe là DEMO, không có trong BOM STEP. Camera ghi góc nhìn 3D; không có phân loại lỗi ảnh hoặc camera hardware I/O.",
       "- Forearm/camera collision là kiểm tra bảo thủ bbox/capsule/slab, không phải vendor collision model hoặc chứng minh swept mesh liên tục. Không xác nhận robot dynamics, torque, joint limits hay an toàn công nghiệp.",
       "- Gripper có thể che vùng tiếp xúc. PASS/FAIL được chọn cho demo; cycle thiếu mặt báo INCOMPLETE.",
       "- 14 giao cắt P09/P11 nguồn vẫn tồn tại. Chế độ toàn cơ cấu bị khóa, không coi camera bổ sung là sửa được CAD nguồn."]
(ROOT/"reports/QC_UPDATE_VALIDATION.md").write_text("\n".join(lines),encoding="utf-8")
print("QC README / actual validation updated")
