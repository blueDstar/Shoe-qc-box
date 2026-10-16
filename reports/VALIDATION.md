**Bản cập nhật hiện tại:** xem [QC_UPDATE_VALIDATION.md](QC_UPDATE_VALIDATION.md). Phần dưới lưu kết quả bản trước khi bổ sung camera / sensor / tay chi tiết.

# Kiểm chứng — Hilykan | Shoe QC Box Simulator

Ngày phiên làm việc theo thời gian người dùng: 2026-10-10, Asia/Saigon.

**Phạm vi: PLATE_AND_BLOCKS đã được người dùng chọn.** P05/P08 và ty P10R tham số được mô phỏng; P09/P11 ẩn và giữ ở pose nguồn. Toàn cơ cấu Rev A chưa đạt do giao cắt CAD và bị khóa chuyển động.

## Kết quả đã chạy

- 52 test đạt, 0 lỗi assertion, 0 lỗi runtime, 0 skip. JUnit: `tests.xml`. Có 14 cảnh báo deprecation từ matplotlib/pyparsing; không phải lỗi mô phỏng.
- 17 STEP đọc được; 48 instance, đủ BOM, hình học valid, màu STEP và đơn vị mm.
- CLI headless hoàn thành trái/phải: 2 chu kỳ, 33,2 giây mô phỏng, IDLE, hai cửa 0 mm.
- GUI Qt/VTK thực: 498 lần cập nhật render, OPEN/STOP click, slider, từ chối mở cửa đối diện, Pause giữ clock/pose, hai chu kỳ và sáu tab. `gui_smoke.json` và PNG đi kèm.
- Cửa sổ Qt đang Auto: 55.65 FPS trung bình ở 1335 × 774; 180 mẫu, median 16.42 ms, p95 27.72 ms. `gui_benchmark.json`.
- Benchmark offscreen riêng: 90.10 FPS ở 1280 × 720. Intel UHD Graphics, OpenGL 4.5. Có thể giảm mạnh khi xuất video đồng thời, dùng transparency hoặc tăng độ phân giải; không cam kết FPS ngoài cấu hình đã đo.
- MP4/H.264 đã mã hóa/đọc lại: 1920 × 1080, 30 FPS, 997 frame, 2 chu kỳ. Frame trace được test đối chiếu với engine từng frame, gồm pose, state, sensor và lease.
- Giải mã frame đầu, trái INSPECT, phải INSPECT và cuối để kiểm tra hình. File gốc STEP giữ SHA256 qua toàn bộ test.

## Đối chiếu tiêu chí

| # | Tiêu chí | Kết quả / bằng chứng |
|---:|---|---|
| 1 | Đọc STEP | Đạt — 17 file, valid BRep |
| 2 | Kích thước 3D | Đạt — shell 800/520/560; envelope 954/572/890; khẩu độ từ inner wire 380/310 |
| 3 | Hai cửa đối diện | Đạt — X=±407, mặt phẳng YZ, cùng chiều Z |
| 4 | Rail cố định | Đạt trong scope — static actor matrices không đổi |
| 5 | Hai cửa độc lập | Đạt — Manual và Auto; interlock ngăn mở cùng lúc |
| 6 | Giới hạn hành trình | Đạt — 0..350 mm; NaN/Infinity/out-of-range bị từ chối |
| 7 | OPEN/CLOSE | Đạt — engine và click widget Qt thật |
| 8 | Slider cập nhật | Đạt — thả slider chạy GO TO; current theo pose engine |
| 9 | Manual/Auto chung engine | Đạt — cùng analytic profile, test so tại cùng thời gian profile |
| 10 | Sensor logic | Đạt — endpoint, CLEAR, chamber, request; manual/unknown tests |
| 11 | Không mở cùng lúc | Đạt — kiểm tra mọi bước hai chu kỳ và concurrent FIFO |
| 12 | Không đóng khi có body | Đạt — raw CLEAR TRUE không vượt được measured body occupancy |
| 13 | Entry sau full OPEN | Đạt — physical endpoint + sensor, swept jump qua cửa đóng bị chặn |
| 14 | Rút hết trước CLOSE | Đạt — shoe/gripper/wrist, clearance + chamber guard |
| 15 | Pause/Resume | Đạt — clock và mọi pose giữ; state restore và recovery từ held pose |
| 16 | Stop giữ pose | Đạt — Manual/Auto, không tự về 0 hoặc release lease |
| 17 | Viewport đáp ứng | Đạt trong benchmark Qt riêng — trung bình 55,65 FPS; CAD import QThread |
| 18 | Không trôi transform | Đạt — mesh immutable; 1000 lần profile về endpoint chính xác; actor static unchanged |
| 19 | State log | Đạt — transition/sensor/interlock/fault/QC, timestamp +07:00, CSV/JSON |
| 20 | Video đúng simulation | Đạt — 997 frame so engine; H.264 decoded; 2 chu kỳ, cuối hai cửa đóng |

## Chưa được xác nhận / không đưa vào phạm vi đạt

- Full mechanism: 14 cặp giao cắt nguồn, gồm bracket/trụ và drive link/ray/seal. Không chấp nhận chúng là mates; phần mềm chặn full mechanism. Cần sửa CAD và khảo sát lại để mở rộng scope.
- Body/rod/rails/blocks là hình bao Rev A, chưa vendor-validated. Ty hiển thị theo chiều dài đo STEP, không mô phỏng kết cấu actuator thực, tải, phanh hoặc đàn hồi.
- Robot DEMO là shoe/gripper/wrist proxy, không có articulated arm, IK, robot hãng, sensor phần cứng hoặc QC thật.
- Runtime collision là swept AABB sơ bộ/bảo thủ. CAD preflight Boolean ở pose 10 mm không phải chứng minh liên tục. Chưa có swept BRep liên tục hoặc chứng nhận an toàn công nghiệp.
- FPS/video performance ngoài độ phân giải/GPU đã đo chưa được xác nhận. Video 1080p render offline chậm hơn thời gian thực vẫn giữ thời gian mô phỏng đúng.
- Bộ gán nhóm hỗ trợ component nguồn; CAD khác thiếu vai trò/khẩu độ cần xác nhận cấu hình và mở rộng validator, không tự tạo hộp thay thế.
- Không đóng gói EXE độc lập; bàn giao source, môi trường đã cài tại máy hiện tại, script .bat, dependency lock, CAD cache và video thật.