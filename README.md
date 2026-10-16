# Hilykan | Shoe QC Box Simulator

Ứng dụng desktop Windows bằng Python/PySide6, dùng hình học **STEP thực tế** của `Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA`. Manual, Auto, Step và xuất video dùng cùng một engine động học và liên động. Không cần SolidWorks khi chạy.

## Phạm vi đã được chọn

**PLATE_AND_BLOCKS**: mô phỏng hai tấm cửa P05, 8 block P08 và hai ty P10R dạng tham số. P09/P11 được ẩn và giữ ở pose nguồn, vì kiểm tra OpenCascade phát hiện giao cắt sẵn có với trụ/ray/dải chắn sáng. Đây là phạm vi kiểm tra cửa đã được người dùng chọn khi khảo sát CAD. Nó chưa xác nhận toàn bộ cơ cấu nâng hạ.

`FULL_ASSEMBLY` hiển thị nguyên lắp ráp, gồm các chi tiết đang giao cắt; lệnh chuyển động bị FAULT và video bị chặn. Phần mềm không sửa offset, kích thước hoặc ghi đè STEP để che lỗi thiết kế.

Robot, giày, gripper, camera, đèn và cảm biến bổ sung là **DEMO**, tách khỏi STEP/BOM nguồn. Tay có hai link cứng dài 650 mm, định vị khớp bằng IK hình học và wrist xoay giày; không phải robot hãng hoặc mô hình động lực học đã xác nhận. Gripper giữ giày liên tục qua sáu mặt kiểm tra.

## Khởi chạy trên máy hiện tại

Mở `launch.bat`, hoặc chạy PowerShell tại `F:\shoeQCbox`:

```powershell
.\.venv\Scripts\python.exe main.py
```

Môi trường `.venv` đã được cài. Cấu hình mặc định gắn xác nhận với SHA256 của assembly đã khảo sát. Thay đổi STEP hoặc cấu hình hành trình sẽ yêu cầu xác nhận lại trong tab CAD & Components.

## Cài trên Windows khác

Python **64 bit 3.9–3.12**. Bản này đã chạy và kiểm tra trên Python 3.9.8, Windows, Intel UHD Graphics. Không dùng Python 3.13 với bộ phiên bản khóa này vì VTK/OCP được khóa theo wheel đã kiểm tra.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe main.py --prepare
.\.venv\Scripts\python.exe main.py
```

Hoặc dùng `setup.bat` rồi `launch.bat`. Giữ thư mục STEP, `model_spec.json` và `BOM.csv` cạnh nhau. `requirements.txt` liệt kê phụ thuộc chính; `requirements-lock.txt` khóa cả phụ thuộc bắc cầu của môi trường kiểm chứng. Cần Internet khi cài package; sau đó chạy offline. FFmpeg H.264 đi kèm wheel `imageio-ffmpeg`.

Nếu CAD nằm nơi khác, đổi CAD directory trong SETTINGS và Reload CAD khi hai cửa đóng/robot đã rút hết. Đổi chất lượng tessellation cũng cần Reload CAD. Nhập STEP chạy ở QThread, không nạp lại mỗi frame.

## Kết quả khảo sát CAD

- 17 STEP: 3 assembly trạng thái và 14 part; thêm 1 SLDASM làm tham chiếu, không dùng làm nguồn hình học.
- Assembly CLOSED có **48 instance**, số lượng khớp tất cả mã BOM; không mất part lặp lại.
- AP214, đơn vị mm, tọa độ tay phải; X vào/ra, Z nâng cửa, gốc X/Y ở tâm hộp, mặt đáy Z=0.
- Vỏ đo được 800 × 520 × 560 mm; toàn cụm 954 × 572 × 890 mm gồm phần cứng bên ngoài.
- P05 đo 4 × 430 × 360 mm; cửa ở X=−407 và +407 mm, hai mặt phẳng YZ song song. Khẩu độ đo từ inner wire P04: 380 × 310 mm.
- Ray dài 820 mm, trụ dài 880 mm. Hai assembly OPEN xác nhận dịch các body cửa +350 mm; ray và thân actuator không dịch.
- Ty thực tế trong STEP: Ø12; đáy Z=363 mm; dài 75 mm ở CLOSED và 425 mm ở OPEN. Viewer dùng đúng đường kính/đáy này và chiều dài `75 + position`. Đây là **body tham số riêng**, không scale các rigid part khác.
- 48 instance có màu STEP. Bộ đọc chuyển màu OpenCascade về sRGB, giữ màu từng face nếu có. Mesh dùng độ lệch tuyến tính 0,15 mm, góc 0,25 rad; BRep gốc được lưu cache.

Chi tiết: `reports/CAD_INSPECTION.md`, `reports/cad_inspection.json`, `reports/collision_preflight.json`, `config/cad_manifest.json`. `make_cad.py` nguồn có chỗ khác STEP hiện tại về ty; phần mềm ưu tiên hình học đo trực tiếp.

## Manual Mode

1. Tab **3D SIMULATION**: OPEN/CLOSE cho mỗi cửa; cửa còn lại phải đóng hoàn toàn và có sensor xác nhận.
2. GO TO hoặc thả slider để đặt vị trí. JOG UP/DOWN dịch mục tiêu 10 mm, vẫn kiểm tra liên động và giới hạn.
3. Speed/Acceleration có hiệu lực với lệnh chuyển động kế tiếp. Profile hình thang hoặc tam giác cho hành trình ngắn.
4. STOP giữ vị trí hiện tại. HOME/RESET yêu cầu đóng về 0 và vẫn bị từ chối nếu vùng cửa chưa trống.
5. Orbit, pan, zoom; góc nhìn Isometric/Front/Top/Left/Right/Fit All. Click component để highlight và xem metadata ở tab CAD.
6. Hide Panels, opacity và Exploded View chỉ thay đổi hiển thị. Collision luôn dùng pose lắp ráp thật.

Hai cửa dùng pose gốc cộng ma trận chuyển động tuyệt đối theo Z. Không cộng dồn dịch chuyển vào vertex. Ray, trụ, khung và actuator body đứng yên. Khi đổi lệnh giữa chuyển động, engine giữ pose rồi lập profile mới; đây là dừng lý tưởng trong mô phỏng, chưa mô hình hóa quán tính/phanh phần cứng.

## Auto và Step Mode

Chọn LEFT, RIGHT hoặc ALTERNATING rồi AUTO START. ALTERNATING mặc định chạy trái rồi phải. Bật Loop để tiếp tục luân phiên. Sim speed chỉ điều chỉnh tốc độ đồng hồ GUI; giới hạn vật lý vẫn dùng mm/s và mm/s².

`REQUEST → CHECK OPPOSITE CLOSED → CHECK CHAMBER → OPEN → WAIT FULL OPEN → INSERT → INSPECT → EXTRACT → WAIT CLEAR → CLOSE → WAIT FULL CLOSED → COMPLETED → IDLE`.

INSERT/INSPECT/EXTRACT giữ cửa mở. Shoe/gripper/wrist phải rút ngoài vùng quét trước khi CLOSE. Yêu cầu đồng thời được xếp FIFO với một chamber lease. Sensor tiếp cận không đủ để cấp phép đóng.

- **PAUSE**: giữ đồng hồ, cửa, pose robot và thời gian trạng thái.
- **RESUME**: tiếp tục trạng thái; lệnh cửa bị Stop sẽ được lập lại từ vị trí đang giữ khi cần.
- **STOP**: giữ toàn bộ pose và chamber lease; dùng RESUME để phục hồi chu trình, không tự đóng cửa khi robot còn trong hộp.
- **STEP/NEXT STATE**: chạy đúng một trạng thái đến điều kiện chuyển bước, rồi Pause. Các bước chuyển động vẫn chạy engine, không nhảy trực tiếp đến pose cuối.
- PASS/FAIL là kết quả QC mô phỏng được chọn trong SETTINGS. FAIL không đồng nghĩa FAULT vận hành.

## Sensor test và Fault Simulation

Auto Sensor Mode tạo endpoint từ vị trí vật lý và CLEAR/occupancy từ body DEMO. Manual test có thể override TRUE/FALSE/UNKNOWN; override không vượt qua collision hoặc xác nhận vật lý.

DEMO faults: DOOR_STALL, SENSOR_NO_OPEN, SENSOR_NO_APPROACH, CAMERA_NOT_READY, DOORWAY_BLOCKED, ROBOT_NOT_WITHDRAWN, UNKNOWN_SENSOR, SIMULTANEOUS_REQUESTS. Stall/sensor không xác nhận/vật cản tồn tại gây timeout tại bước chờ; tín hiệu UNKNOWN, mâu thuẫn hoặc nguy cơ va chạm gây FAULT và dừng body liên quan.

Khắc phục: **Clear DEMO cause → RESET FAULT → RESUME**. Reset giữ pose, không teleport robot hoặc về Home. Nếu robot chưa rút hết, recovery tiếp tục EXTRACT từ pose thực. Withdrawal button chỉ yêu cầu rút trong INSPECT, không ép tín hiệu CLEAR.

Tắt Virtual Robot Demonstration chỉ ẩn asset DEMO; logic robot, vùng chiếm chỗ và liên động vẫn hoạt động trong Auto.

## Tám tab

| Tab | Chức năng |
|---|---|
| 3D SIMULATION | Viewport STEP và sidebar điều khiển có cuộn |
| MOTION ANALYSIS | Position, velocity, acceleration, CLEAR sensor, state theo thời gian; preview profile, CSV |
| CAD & COMPONENTS | Cây instance, source, ID, group, bbox, transform, màu, độ xác nhận; visibility, assignment, manifest export, reload |
| SEQUENCE CONTROL | Sơ đồ FSM, trạng thái hiện tại, điều kiện chuyển, 10 interlock, timeout, Next/Pause/Resume/Stop |
| SETTINGS | CAD path, travel/speed/accel, sensor tolerance, timeout, tessellation, QC result, JSON config |
| LOG & EXPORT | Timestamp +07:00, event CSV/JSON, state save/load, PNG và MP4 |
| CAMERA QC | Ảnh FRONT/TOP từ scene thật, bảng sáu mặt, pose/thời điểm chụp, lưu PNG + JSON |
| DOOR MOTION | Hai viewport CAD gần trái/phải, thước Z 0–350, block moving/fixed rail, tốc độ/hướng/ty, OPEN/CLOSE/STOP chung engine |

Các part cố định đã xác định không được gán vào nhóm cửa. Block phải theo đúng cửa. Gán lại nhóm yêu cầu CLOSED/withdrawn/IDLE và xác nhận lại. Manifest lưu definition mesh và base transform riêng; transform instance chỉ áp dụng một lần. Với CAD khác thiếu tên vai trò, có thể gán nhóm trong cây, nhưng cần bổ sung xác nhận khẩu độ/vùng robot cho thiết kế đó; bản này không tự suy luận động học của một hộp bất kỳ.

## Collision và giới hạn xác nhận

Preflight: swept AABB broad phase, rồi boolean solid-common OpenCascade tại pose cách tối đa 10 mm. Không thấy giao cắt tấm cửa P05 với phần cố định trên các pose này. **14 cặp** bracket/drive link giao cắt với trụ/ray/seal đã được ghi lại; không coi chúng là tiếp xúc lắp ráp hợp lệ. Toàn cơ cấu bị khóa chuyển động; scope được chọn bỏ P09/P11 khỏi mô phỏng.

Runtime: **kiểm tra sơ bộ bảo thủ bằng swept AABB và capsule cho link tay**, mỗi bước tối đa 1/120 s. Bao gồm shutter với fixed CAD/giày/gripper/wrist/tay, khẩu độ/vỏ/ray, hai robot, shoe với chamber và phần cứng camera/đèn. Capsule được cắt theo lát X tại khẩu độ và chamber; obstacle dùng segment với box phình theo bán kính và chuyển động. Đó là kiểm tra bảo thủ, không phải collision mesh chính xác hoặc chứng minh an toàn liên tục. Điểm đầu/cuối body được union để tránh bỏ sót xuyên giữa frame. Các quỹ đạo xoay mẫu nhỏ được chia nhiều pose; đây không phải chứng minh swept-volume liên tục cho mọi quỹ đạo tùy ý. Có thể có cảnh báo bảo thủ.

Chưa xác nhận vendor geometry, liên kết cơ khí, độ cứng, tải, dung sai, phanh chống rơi, tín hiệu phần cứng hoặc an toàn công nghiệp. P09/P11 đang bị loại khỏi chuyển động là giới hạn thực tế cần CAD sửa lỗi trước khi mở rộng scope.

## Cảm biến ngoài cửa và chi tiết linear motion

Hai cảm biến DEMO có housing đỏ và trụ gá riêng ở ngoài cửa: tâm (±520,−320,320) mm. Laser đỏ hiện mặc định, điểm nhận chuyển xanh khi signal APPROACH=True. Đây là chỉ dẫn của vùng phát hiện bbox, không phải mô phỏng quang học/ray tracing hoặc laser phần cứng. Tia hiển thị luôn ở vùng ngoài cửa, không xuyên qua vỏ STEP.

Thanh thông báo đỏ phía trên GUI hiển thị riêng L/R: **đang quét → đã phát hiện tay/giày → yêu cầu mở → đang mở/chờ liên động**. `dX` là khoảng hở theo X từ biên dẫn đầu của bbox cụm giày/gripper tới mặt phẳng cửa X=±407 mm, không phải khoảng cách Euclidean đến sensor head. Ngưỡng mặc định giữ cấu hình cũ: outer X=750, tương đương **343 mm** từ mặt phẳng cửa. Đổi trực tiếp `Trigger gap to door (X)` trong SENSOR SIMULATION khi CLOSED/withdrawn/IDLE; ví dụ đặt 350 mm thì outer X=757. Tín hiệu manual override được ghi TEST INPUT; không dùng nó để bỏ qua interlock. Log có `PROXIMITY_DETECTED` trước lệnh mở.

Mở **DOOR MOTION** hoặc `Door motion detail` để thấy gần hai cụm cửa cùng lúc. Đây là các instance mesh STEP hiện có, không nhập thêm assembly OPEN. Ruler 0–350 mm đo displacement từ CLOSED (center tấm cửa Z=300 mm), marker/trail cập nhật theo engine. Cyan outlines đánh dấu P05/P08; P07 rail, P06 tower và P10 actuator body cố định. Ty P10R hiển thị chiều dài 75 + position mm theo STEP đã đo. P09/P11 vẫn bị loại vì lỗi CAD nguồn. Header hiển thị position/target, velocity, acceleration, direction, remaining travel và rod length. OPEN/CLOSE/STOP tại tab này dùng chung guard và controller với sidebar.

Viewport gần có orbit/pan/zoom, chỉ cập nhật khi tab mở, khoảng 30 Hz. Hai framebuffer được cập nhật theo kích thước widget và DPI Windows. Trên viewport chính: `Focus LEFT/RIGHT` phóng gần một bên; `Travel rulers / moving carriage outlines` bật lớp motion aids nếu cần. Lớp này mặc định tắt ở cảnh tổng thể để giảm tải; DOOR MOTION luôn có thước và highlight. Các overlay và sensor stand không sửa file STEP/BOM. Camera/giày/robot/QC được giữ nguyên từ bản cập nhật trước.

Kiểm chứng bổ sung: `reports/SENSOR_MOTION_VALIDATION.md`, `reports/sensor_motion_check.json`, ảnh `sensor_laser_detected.png`, `door_motion_left_opening.png`, `door_motion_right_opening.png`. Chạy `.\.venv\Scripts\python.exe tools\sensor_motion_check.py` để kiểm tra lại GUI thật.

## Cảm biến và CAMERA QC mới

Trong SENSOR SIMULATION, nhấn **LEFT Approach** hoặc **RIGHT Approach**: tay đưa giày từ ngoài tới vị trí chờ. Tín hiệu tiếp cận được đo từ bbox của giày/gripper/wrist trong vùng X ngoài ±750 đến ±495 mm, Y±165, Z160..440 mm; không suy ra từ tên trạng thái. Khi phát hiện và bật **Proximity sensor → automatic door request**, coordinator cấp lease rồi mở cửa theo interlock. Hai phía có thể cùng tiếp cận; một phía chờ. Override APPROACH=False hoặc UNKNOWN không được bỏ qua. Manual OPEN vẫn dùng guard cửa hiện có.

Cảm biến endpoint có housing/LED tại vị trí đóng và mở; cảm biến tiếp cận có housing riêng; vùng CLEAR và curtain là tín hiệu/vùng logic DEMO. LED đổi theo tín hiệu thật trong engine. CLEAR bao gồm cả forearm và wrist; không dùng APPROACH để quyết định đóng.

Camera **FRONT**: tâm quang học (0,−235,300) mm, nhìn +Y vào giày. Camera **TOP**: (0,0,507) mm, nhìn xuống −Z. Body, lens, mount và LED nằm trong chamber đã đo; có collision sơ bộ với tay/giày. Không khoét hoặc chỉnh vỏ STEP. Camera vertical FOV mặc định 90°, preview 400 × 300; chỉnh FOV và thời gian xoay/giữ trong SETTINGS khi CLOSED/withdrawn/IDLE.

INSPECT: **INNER → UPPER → OUTER → OUTSOLE → TOE → HEEL → RETURN NEUTRAL**. Mỗi mặt xoay mượt 0,8 s, giữ 0,5 s để capture. Normal của mặt được xác nhận hướng về camera FRONT và shoe bbox nằm trong FOV. Camera TOP ghi góc phụ. Xoay về neutral trước khi rút; các link tay giữ chiều dài 650 mm, gripper luôn theo giày. Nếu rút sớm, kết quả cycle là **INCOMPLETE**, không tự ghi PASS.

Mở **CAMERA QC** để xem hai ảnh render phối cảnh thật. Live preview chạy 5 FPS chỉ khi tab này mở, nên không tăng tải camera ở viewport chính. Chọn dòng trong bảng để xem đúng pose đã chụp, tắt Live; dùng **Save selected capture PNG + JSON** hoặc **Save all QC captures**. Ảnh nằm trong `exports/qc_captures/`; JSON lưu source SHA256, cửa, robot, góc, thời gian, FOV và alignment. Renderer dùng geometry cache, actor riêng; xem lại ảnh không dịch chuyển phiên live. Save-all chia từng capture qua Qt event loop.

**QC PASS/FAIL là kết quả mô phỏng đã chọn**, chưa có thuật toán phát hiện lỗi giày bằng ảnh. Vùng gripper tiếp xúc có thể che một phần ảnh; không tuyên bố kiểm tra hết vùng bị che. Camera và cảm biến chưa kết nối thiết bị thật. Hide camera bodies/FOV và QC cutaway chỉ đổi display; collision và sensor vẫn dùng geometry lắp ráp.

Chạy kiểm chứng ảnh: `.\.venv\Scripts\python.exe tools\qc_render_check.py`. Bản thử có 12 pose / 24 ảnh cho hai phía; `reports/qc_render_check.json`. Video mặc định GUI vẫn hỗ trợ 1920 × 1080 / 30 FPS, nhưng clip cập nhật bàn giao là 720p. `main.py` và `launch.bat` khởi chạy như trước.

## Video và ảnh

LOG & EXPORT: mặc định **1920 × 1080, 30 FPS, MP4/H.264**, hai chu kỳ luân phiên. Fixed hoặc Orbit Camera; Motion Overlay bật/tắt; Hide UI xuất viewport sạch, bỏ chọn để có sidebar trạng thái được render từ cùng frame.

Exporter chạy process riêng, dùng cùng engine từ trạng thái CLOSED ban đầu, bước `1/FPS` chia thành `1/120 s`. Tốc độ máy không đổi thời gian mô phỏng. Cấu hình chuyển động, scope và kết quả QC được dùng chung; manual sensor overrides của phiên live không được đưa vào video Auto mới. Auto Sensor Mode phải bật. Video dùng shell opacity 0,35 để thấy kiểm tra bên trong; hình học không đổi.

Mỗi MP4 có `.frames.jsonl`, `.events.json`, `.verification.json`. Frame trace lưu thời gian, cửa, robot, sensor, lease và FSM. File `.partial.mp4` không được đổi tên thành kết quả hoàn tất nếu FAULT/cancel/timeout. Encoder được kiểm tra bằng đọc frame và metadata OpenCV sau khi hoàn tất.

```powershell
.\.venv\Scripts\python.exe main.py --export-video exports\Hilykan_QC_Alternating_1080p.mp4
```

Capture 3D PNG chụp framebuffer VTK thật. `QWidget.grab()` trên Windows bỏ qua native OpenGL surface; các ảnh minh họa cửa sổ trong smoke test ghép **framebuffer thật** vào đúng vùng Qt chỉ để tài liệu. Viewport ứng dụng vẫn là 3D tương tác.

## Lưu và phục hồi

Save simulation state ghi JSON gồm thời gian, pose, target, robot, sensor, queue, chamber lease, FSM và FAULT. Load kiểm tra source SHA256, giới hạn cửa, hai cửa cùng mở, sensor và collision, rồi nạp ở trạng thái Pause. RESUME là thao tác rõ ràng trước khi chuyển động. Motion của cửa được lập lại từ pose đang giữ khi phục hồi; đây không phải lưu state một PLC thật.

Config mặc định: `config/default.json`; cấu hình người dùng: `config/user.json` nếu có. Cấu hình user được ưu tiên. Log live: `logs/session.jsonl`; đóng cửa sổ lưu `logs/last_state.json`. CSV dùng UTF-8 BOM để đọc trong Excel.

## Kiểm tra lại

```powershell
.\.venv\Scripts\python.exe main.py --inspect
.\.venv\Scripts\python.exe main.py --headless-cycle
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports\tests.xml
.\.venv\Scripts\python.exe main.py --smoke-test
.\.venv\Scripts\python.exe tools\render_benchmark.py
```

Smoke test mở cửa sổ thực, click nút bằng QtTest, thả slider, chạy hai chu kỳ, kiểm tra Pause và ma trận actor static, render bảy tab, kiểm tra hai feed camera và lưu ảnh. Không thay CAD bằng fixture tưởng tượng. Test CAD đọc các STEP và mesh của bộ dữ liệu thực, so checksum nguồn sau mô phỏng.

Kết quả kiểm chứng và phần chưa đạt được ghi trong `reports/VALIDATION.md`. FPS phụ thuộc GPU, driver, độ phân giải và opacity; không coi tốc độ encoder là tốc độ viewport. Không khẳng định 30–60 FPS nếu benchmark trên máy hiện tại chưa đạt.

Kết quả bản cập nhật camera: **68 test đạt**, hai chu kỳ sáu mặt, 42,4 giây mô phỏng. Video mới `exports/Hilykan_Multiface_QC_720p.mp4`: 1280 × 720 / 30 FPS / 1272 frame / 12 capture pose. Video 1080p trước đó vẫn được giữ như bản trước cập nhật. GUI chi tiết hơn đạt **57,99 FPS** trung bình ở viewport 1335 × 774 trong lần đo riêng, Intel UHD Graphics. Xem `reports/gui_benchmark.json` và `reports/QC_UPDATE_VALIDATION.md`.

## Kiến trúc

```text
main.py                 CLI / Qt entry
cad_import/             STEPCAF/XDE, tessellation, SHA256 mesh/BRep cache
cad_manifest/           scan, BOM match, đo bbox/wire, CLOSED/OPEN comparisons
scene3d/                immutable meshes, actor matrices, camera, DEMO overlays
motion/                 analytical trapezoid/triangle planner
controllers/            interlocks, fixed-link DEMO arm IK, six-face presentation
sensors/                measured proximity/clear zones, endpoints, overrides
state_machine/          FIFO dual-side sequence and step/pause/recovery
simulation/             shared fixed-step engine, state serialization
collision/              CAD boolean preflight and runtime swept AABB
gui/                    seven functional PySide6 tabs; QTimer, QThread, QProcess
qc/                     camera geometry/projection, capture poses, lazy VTK feeds
export/                 fixed-time VTK capture, FFmpeg, trace and verification
config/                 validated JSON settings and measured component manifest
logs/                   append-only events and state
tests/                  motion, source CAD, interlocks, FSM, recovery, video trace
tools/                  import utility, GUI smoke, renderer diagnostics
```

Qt GUI không dùng `time.sleep()`. Physics cố định 120 Hz; QTimer yêu cầu render khoảng 60 Hz khi máy đủ nhanh, không thay đổi profile để giả đạt FPS. Scene chỉ cập nhật ma trận actor cần thay đổi; source vertex không bị tích lũy dịch chuyển.

Tài liệu thư viện dùng khi chọn bộ phiên bản: [OCP 7.7.2 / wheel Windows](https://pypi.org/project/cadquery-ocp/7.7.2/), [PySide6 6.8.3](https://pypi.org/project/PySide6/6.8.3/), [PyVistaQt và lựa chọn binding](https://qt.pyvista.org/usage.html).
