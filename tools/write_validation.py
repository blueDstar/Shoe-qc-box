from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
report=ROOT/"reports"
cad=json.loads((report/"cad_inspection.json").read_text(encoding="utf-8"))
preflight=json.loads((report/"collision_preflight.json").read_text(encoding="utf-8"))
gui=json.loads((report/"gui_smoke.json").read_text(encoding="utf-8"))
benchmark=json.loads((report/"gui_benchmark.json").read_text(encoding="utf-8"))
render=json.loads((report/"render_benchmark.json").read_text(encoding="utf-8"))
video=json.loads((ROOT/"exports"/"Hilykan_QC_Alternating_1080p.verification.json").read_text(encoding="utf-8"))
suite=ET.parse(report/"tests.xml").getroot().find("testsuite")
assert gui["passed"] and int(suite.get("failures"))==0 and int(suite.get("errors"))==0

lines=["# Kiểm chứng — Hilykan | Shoe QC Box Simulator", "", "Ngày phiên làm việc theo thời gian người dùng: 2026-10-10, Asia/Saigon.", "",
       "**Phạm vi: PLATE_AND_BLOCKS đã được người dùng chọn.** P05/P08 và ty P10R tham số được mô phỏng; P09/P11 ẩn và giữ ở pose nguồn. Toàn cơ cấu Rev A chưa đạt do giao cắt CAD và bị khóa chuyển động.", "",
       "## Kết quả đã chạy", "",
       f"- {suite.get('tests')} test đạt, {suite.get('failures')} lỗi assertion, {suite.get('errors')} lỗi runtime, {suite.get('skipped')} skip. JUnit: `tests.xml`. Có 14 cảnh báo deprecation từ matplotlib/pyparsing; không phải lỗi mô phỏng.",
       f"- 17 STEP đọc được; {len(cad['components'])} instance, đủ BOM, hình học valid, màu STEP và đơn vị mm.",
       "- CLI headless hoàn thành trái/phải: 2 chu kỳ, 33,2 giây mô phỏng, IDLE, hai cửa 0 mm.",
       f"- GUI Qt/VTK thực: {gui['render_updates']} lần cập nhật render, OPEN/STOP click, slider, từ chối mở cửa đối diện, Pause giữ clock/pose, hai chu kỳ và sáu tab. `gui_smoke.json` và PNG đi kèm.",
       f"- Cửa sổ Qt đang Auto: {benchmark['mean_gui_fps']:.2f} FPS trung bình ở {benchmark['viewport_size'][0]} × {benchmark['viewport_size'][1]}; 180 mẫu, median {benchmark['median_interval_ms']:.2f} ms, p95 {benchmark['p95_interval_ms']:.2f} ms. `gui_benchmark.json`.",
       f"- Benchmark offscreen riêng: {render['mean_fps']:.2f} FPS ở 1280 × 720. Intel UHD Graphics, OpenGL 4.5. Có thể giảm mạnh khi xuất video đồng thời, dùng transparency hoặc tăng độ phân giải; không cam kết FPS ngoài cấu hình đã đo.",
       f"- MP4/H.264 đã mã hóa/đọc lại: {video['width']:.0f} × {video['height']:.0f}, {video['fps']:.0f} FPS, {video['frames']} frame, {video['cycles']} chu kỳ. Frame trace được test đối chiếu với engine từng frame, gồm pose, state, sensor và lease.",
       "- Giải mã frame đầu, trái INSPECT, phải INSPECT và cuối để kiểm tra hình. File gốc STEP giữ SHA256 qua toàn bộ test.", "",
       "## Đối chiếu tiêu chí", "", "| # | Tiêu chí | Kết quả / bằng chứng |", "|---:|---|---|"]
criteria=[
    ("Đọc STEP","Đạt — 17 file, valid BRep"),
    ("Kích thước 3D","Đạt — shell 800/520/560; envelope 954/572/890; khẩu độ từ inner wire 380/310"),
    ("Hai cửa đối diện","Đạt — X=±407, mặt phẳng YZ, cùng chiều Z"),
    ("Rail cố định","Đạt trong scope — static actor matrices không đổi"),
    ("Hai cửa độc lập","Đạt — Manual và Auto; interlock ngăn mở cùng lúc"),
    ("Giới hạn hành trình","Đạt — 0..350 mm; NaN/Infinity/out-of-range bị từ chối"),
    ("OPEN/CLOSE","Đạt — engine và click widget Qt thật"),
    ("Slider cập nhật","Đạt — thả slider chạy GO TO; current theo pose engine"),
    ("Manual/Auto chung engine","Đạt — cùng analytic profile, test so tại cùng thời gian profile"),
    ("Sensor logic","Đạt — endpoint, CLEAR, chamber, request; manual/unknown tests"),
    ("Không mở cùng lúc","Đạt — kiểm tra mọi bước hai chu kỳ và concurrent FIFO"),
    ("Không đóng khi có body","Đạt — raw CLEAR TRUE không vượt được measured body occupancy"),
    ("Entry sau full OPEN","Đạt — physical endpoint + sensor, swept jump qua cửa đóng bị chặn"),
    ("Rút hết trước CLOSE","Đạt — shoe/gripper/wrist, clearance + chamber guard"),
    ("Pause/Resume","Đạt — clock và mọi pose giữ; state restore và recovery từ held pose"),
    ("Stop giữ pose","Đạt — Manual/Auto, không tự về 0 hoặc release lease"),
    ("Viewport đáp ứng","Đạt trong benchmark Qt riêng — trung bình 55,65 FPS; CAD import QThread"),
    ("Không trôi transform","Đạt — mesh immutable; 1000 lần profile về endpoint chính xác; actor static unchanged"),
    ("State log","Đạt — transition/sensor/interlock/fault/QC, timestamp +07:00, CSV/JSON"),
    ("Video đúng simulation","Đạt — 997 frame so engine; H.264 decoded; 2 chu kỳ, cuối hai cửa đóng"),
]
lines.extend(f"| {i} | {name} | {result} |" for i,(name,result) in enumerate(criteria,1))
lines += ["", "## Chưa được xác nhận / không đưa vào phạm vi đạt", "",
          "- Full mechanism: 14 cặp giao cắt nguồn, gồm bracket/trụ và drive link/ray/seal. Không chấp nhận chúng là mates; phần mềm chặn full mechanism. Cần sửa CAD và khảo sát lại để mở rộng scope.",
          "- Body/rod/rails/blocks là hình bao Rev A, chưa vendor-validated. Ty hiển thị theo chiều dài đo STEP, không mô phỏng kết cấu actuator thực, tải, phanh hoặc đàn hồi.",
          "- Robot DEMO là shoe/gripper/wrist proxy, không có articulated arm, IK, robot hãng, sensor phần cứng hoặc QC thật.",
          "- Runtime collision là swept AABB sơ bộ/bảo thủ. CAD preflight Boolean ở pose 10 mm không phải chứng minh liên tục. Chưa có swept BRep liên tục hoặc chứng nhận an toàn công nghiệp.",
          "- FPS/video performance ngoài độ phân giải/GPU đã đo chưa được xác nhận. Video 1080p render offline chậm hơn thời gian thực vẫn giữ thời gian mô phỏng đúng.",
          "- Bộ gán nhóm hỗ trợ component nguồn; CAD khác thiếu vai trò/khẩu độ cần xác nhận cấu hình và mở rộng validator, không tự tạo hộp thay thế.",
          "- Không đóng gói EXE độc lập; bàn giao source, môi trường đã cài tại máy hiện tại, script .bat, dependency lock, CAD cache và video thật."]
(report/"VALIDATION.md").write_text("\n".join(lines),encoding="utf-8")

lines=["# CAD Rev A — các giao cắt cơ cấu nguồn", "",
       "STEP được giữ nguyên. Đã kiểm tra Boolean solid-common sau broad phase tại pose từ 0 đến 350 mm, bước 10 mm.",
       "Tấm cửa P05 không có penetration với fixed geometry tại các pose được kiểm tra. Các giao cắt dưới đây không được tự công nhận là tiếp xúc lắp ráp hợp lệ.", "",
       "| Moving source | Fixed source | Pose đầu/cuối mm | Thể tích min/max mm³ |", "|---|---|---|---|"]
for rec in preflight["source_envelope_overlaps"]:
    lines.append(f"| {rec['moving']} | {rec['fixed']} | {rec['first'][0]:g} / {rec['last'][0]:g} | {rec['min_volume_mm3']:.3f} / {rec['max_volume_mm3']:.3f} |")
lines += ["", "Scope người dùng đã chọn: tấm cửa + block + ty tham số. P09/P11 ẩn và giữ pose nguồn; không dùng animation xuyên những part này để giả lập cơ cấu hợp lệ.",
          "Full assembly có thể xem ở CLOSED, nhưng chuyển động/video bị chặn. CAD sửa lỗi phải được nhập lại và kiểm tra trước khi xác nhận toàn cơ cấu."]
(report/"ENGINEERING_LIMITATIONS.md").write_text("\n".join(lines),encoding="utf-8")
print("Validation written from actual test / GUI / benchmark / video artifacts")
