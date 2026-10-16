# Kiểm chứng bản cập nhật camera / sensor / robot DEMO

Ngày phiên làm việc: 2026-10-10, Asia/Saigon. STEP/BOM nguồn và phạm vi PLATE_AND_BLOCKS giữ nguyên.

- 68 test đạt, 0 skip; gồm regressions cửa, sensor bằng geometry, fixed-link IK, six-face capture, lỗi camera/proximity, pause/restore/recovery và hai video replay frame-by-frame.
- Link tay cố định 650 mm; mesh DEMO nằm trong collision envelopes. Không co/giãn link để giả lập reach. Wrist/gripper/giày kết nối xuyên suốt; quỹ đạo toe→heel chọn nửa vòng trong vùng reach.
- Hai chu kỳ Auto hoàn tất, IDLE, hai cửa 0 mm, không FAULT. Mỗi phía 6 mặt đều alignment cosine=1 tại capture; primary FRONT in-frame.
- 12 pose đã render, 24 PNG FRONT/TOP thực; kiểm tra hình giày/đế/dây/cổ giày và gripper, không dùng ảnh dựng sẵn.
- GUI smoke: bảy tab, nút OPEN/STOP/slider, Pause, static CAD actors, 12 capture pose, hai feed camera, chọn pose và lưu PNG/JSON.
- GUI riêng: 57.99 FPS trung bình tại [1335, 774], p95 interval 22.00 ms; physics step 0.620 ms, scene update 2.35 ms, render 9.35 ms. Không cam kết FPS khi encode/video hay chạy nhiều GUI đồng thời.
- H.264 mới: 1280 × 720, 30 FPS, 1272 frame, 2 chu kỳ, 12 capture pose; final LEFT=RIGHT=0 mm. Decode thành công và replay khớp pose/state/sensor/QC từng frame.
- Đã tối ưu: một actor/RGB-cell mesh cho mỗi rigid DEMO role; camera render lười ở tab QC; mapper riêng giữa cửa sổ render; cache sensor theo pose; HUD text cố định kích thước để tránh việc tính lại font mỗi frame.

## Giới hạn thực tế

- Sensor/camera/light/arm/shoe là DEMO, không có trong BOM STEP. Camera ghi góc nhìn 3D; không có phân loại lỗi ảnh hoặc camera hardware I/O.
- Forearm/camera collision là kiểm tra bảo thủ bbox/capsule/slab, không phải vendor collision model hoặc chứng minh swept mesh liên tục. Không xác nhận robot dynamics, torque, joint limits hay an toàn công nghiệp.
- Gripper có thể che vùng tiếp xúc. PASS/FAIL được chọn cho demo; cycle thiếu mặt báo INCOMPLETE.
- 14 giao cắt P09/P11 nguồn vẫn tồn tại. Chế độ toàn cơ cấu bị khóa, không coi camera bổ sung là sửa được CAD nguồn.