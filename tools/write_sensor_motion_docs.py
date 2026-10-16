from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
readme=ROOT/"README.md"
text=readme.read_text(encoding="utf-8")
text=text.replace("## Bảy tab","## Tám tab")
row="| CAMERA QC | Ảnh FRONT/TOP từ scene thật, bảng sáu mặt, pose/thời điểm chụp, lưu PNG + JSON |"
text=text.replace(row,row+"\n| DOOR MOTION | Hai viewport CAD gần trái/phải, thước Z 0–350, block moving/fixed rail, tốc độ/hướng/ty, OPEN/CLOSE/STOP chung engine |")
section="""## Cảm biến ngoài cửa và chi tiết linear motion

Hai cảm biến DEMO có housing đỏ và trụ gá riêng ở ngoài cửa: tâm (±520,−320,320) mm. Laser đỏ hiện mặc định, điểm nhận chuyển xanh khi signal APPROACH=True. Đây là chỉ dẫn của vùng phát hiện bbox, không phải mô phỏng quang học/ray tracing hoặc laser phần cứng. Tia hiển thị luôn ở vùng ngoài cửa, không xuyên qua vỏ STEP.

Thanh thông báo đỏ phía trên GUI hiển thị riêng L/R: **đang quét → đã phát hiện tay/giày → yêu cầu mở → đang mở/chờ liên động**. `dX` là khoảng hở theo X từ biên dẫn đầu của bbox cụm giày/gripper tới mặt phẳng cửa X=±407 mm, không phải khoảng cách Euclidean đến sensor head. Ngưỡng mặc định giữ cấu hình cũ: outer X=750, tương đương **343 mm** từ mặt phẳng cửa. Đổi trực tiếp `Trigger gap to door (X)` trong SENSOR SIMULATION khi CLOSED/withdrawn/IDLE; ví dụ đặt 350 mm thì outer X=757. Tín hiệu manual override được ghi TEST INPUT; không dùng nó để bỏ qua interlock. Log có `PROXIMITY_DETECTED` trước lệnh mở.

Mở **DOOR MOTION** hoặc `Door motion detail` để thấy gần hai cụm cửa cùng lúc. Đây là các instance mesh STEP hiện có, không nhập thêm assembly OPEN. Ruler 0–350 mm đo displacement từ CLOSED (center tấm cửa Z=300 mm), marker/trail cập nhật theo engine. Cyan outlines đánh dấu P05/P08; P07 rail, P06 tower và P10 actuator body cố định. Ty P10R hiển thị chiều dài 75 + position mm theo STEP đã đo. P09/P11 vẫn bị loại vì lỗi CAD nguồn. Header hiển thị position/target, velocity, acceleration, direction, remaining travel và rod length. OPEN/CLOSE/STOP tại tab này dùng chung guard và controller với sidebar.

Viewport gần có orbit/pan/zoom, chỉ cập nhật khi tab mở, khoảng 30 Hz. Hai framebuffer được cập nhật theo kích thước widget và DPI Windows. Trên viewport chính: `Focus LEFT/RIGHT` phóng gần một bên; `Travel rulers / moving carriage outlines` bật lớp motion aids nếu cần. Lớp này mặc định tắt ở cảnh tổng thể để giảm tải; DOOR MOTION luôn có thước và highlight. Các overlay và sensor stand không sửa file STEP/BOM. Camera/giày/robot/QC được giữ nguyên từ bản cập nhật trước.

Kiểm chứng bổ sung: `reports/SENSOR_MOTION_VALIDATION.md`, `reports/sensor_motion_check.json`, ảnh `sensor_laser_detected.png`, `door_motion_left_opening.png`, `door_motion_right_opening.png`. Chạy `.\\.venv\\Scripts\\python.exe tools\\sensor_motion_check.py` để kiểm tra lại GUI thật.

"""
if "## Cảm biến ngoài cửa và chi tiết linear motion" not in text:
    text=text.replace("## Cảm biến và CAMERA QC mới",section+"## Cảm biến và CAMERA QC mới")
text=text.replace("Kết quả bản cập nhật: **68 test đạt**","Kết quả bản cập nhật camera: **68 test đạt**")
readme.write_text(text,encoding="utf-8")

result=json.loads((ROOT/"reports/sensor_motion_check.json").read_text(encoding="utf-8"))
fps=json.loads((ROOT/"reports/gui_benchmark.json").read_text(encoding="utf-8"))
suite=ET.parse(ROOT/"reports/tests.xml").getroot().find("testsuite")
assert result["passed"] and int(suite.get("failures"))==0 and int(suite.get("errors"))==0
report=["# Kiểm chứng cảm biến đỏ / laser / DOOR MOTION", "", "Phiên làm việc: 2026-10-10, Asia/Saigon.", "",
        f"- {suite.get('tests')} test đạt, {suite.get('skipped')} skip; bao gồm trigger distance trước/sau ngưỡng, sensor mount không overlap STEP, notification trước OPEN, state restore và regressions cửa/camera/robot/video.",
        "- GUI thực: laser/housing đỏ hai phía, nhãn signal/range; hai detail renderers đọc mesh cache nguồn; ruler marker=engine.position; static rail matrices giữ nguyên; hai cửa điều khiển độc lập và không mở cùng lúc.",
        "- Có ảnh kiểm chứng trước/sau detection, LEFT mở một phần và RIGHT mở một phần. Framebuffer được resize theo widget/DPI, không dùng ảnh tĩnh làm viewport.",
        f"- Viewport tổng thể {fps['viewport_size']}: {fps['mean_gui_fps']:.2f} FPS trung bình trong phép đo riêng, median {fps['median_interval_ms']:.2f} ms, p95 {fps['p95_interval_ms']:.2f} ms. Hiệu năng thay đổi theo tải/driver; không giữ tuyên bố 58 FPS của bản trước cho lớp hiển thị mới.",
        "- Main viewport mặc định có laser/red housing/notification; motion aids là tùy chọn. Chi tiết hai cửa chỉ render khi tab mở, giới hạn 30 Hz. Physics vẫn fixed 120 Hz, không đổi profile hoặc logic QC để giả tăng FPS.",
        "- STEP/BOM giữ nguyên; cùng engine và interlocks. Sensor laser là DEMO bounding-volume visualization; dX theo X đến plane ±407 mm, không phải sensor hardware accuracy. Full mechanism vẫn bị khóa bởi P09/P11 source clashes."]
(ROOT/"reports/SENSOR_MOTION_VALIDATION.md").write_text("\n".join(report),encoding="utf-8")
print("Sensor / motion documentation written from actual checks")
