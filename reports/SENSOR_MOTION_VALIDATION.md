# Kiểm chứng cảm biến đỏ / laser / DOOR MOTION

Phiên làm việc: 2026-10-10, Asia/Saigon.

- 73 test đạt, 0 skip; bao gồm trigger distance trước/sau ngưỡng, sensor mount không overlap STEP, notification trước OPEN, state restore và regressions cửa/camera/robot/video.
- GUI thực: laser/housing đỏ hai phía, nhãn signal/range; hai detail renderers đọc mesh cache nguồn; ruler marker=engine.position; static rail matrices giữ nguyên; hai cửa điều khiển độc lập và không mở cùng lúc.
- Có ảnh kiểm chứng trước/sau detection, LEFT mở một phần và RIGHT mở một phần. Framebuffer được resize theo widget/DPI, không dùng ảnh tĩnh làm viewport.
- Viewport tổng thể [1335, 729]: 30.97 FPS trung bình trong phép đo riêng, median 26.39 ms, p95 67.55 ms. Hiệu năng thay đổi theo tải/driver; không giữ tuyên bố 58 FPS của bản trước cho lớp hiển thị mới.
- Main viewport mặc định có laser/red housing/notification; motion aids là tùy chọn. Chi tiết hai cửa chỉ render khi tab mở, giới hạn 30 Hz. Physics vẫn fixed 120 Hz, không đổi profile hoặc logic QC để giả tăng FPS.
- STEP/BOM giữ nguyên; cùng engine và interlocks. Sensor laser là DEMO bounding-volume visualization; dX theo X đến plane ±407 mm, không phải sensor hardware accuracy. Full mechanism vẫn bị khóa bởi P09/P11 source clashes.