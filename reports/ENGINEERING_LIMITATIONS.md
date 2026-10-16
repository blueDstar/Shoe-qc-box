# CAD Rev A — các giao cắt cơ cấu nguồn

STEP được giữ nguyên. Đã kiểm tra Boolean solid-common sau broad phase tại pose từ 0 đến 350 mm, bước 10 mm.
Tấm cửa P05 không có penetration với fixed geometry tại các pose được kiểm tra. Các giao cắt dưới đây không được tự công nhận là tiếp xúc lắp ráp hợp lệ.

| Moving source | Fixed source | Pose đầu/cuối mm | Thể tích min/max mm³ |
|---|---|---|---|
| BRACKET_L_F_1 | TOWER_L_F | 0 / 350 | 711.035 / 711.035 |
| BRACKET_L_F_2 | TOWER_L_F | 0 / 350 | 711.035 / 711.035 |
| BRACKET_L_B_1 | TOWER_L_B | 0 / 350 | 711.035 / 711.035 |
| BRACKET_L_B_2 | TOWER_L_B | 0 / 350 | 711.035 / 711.035 |
| DRIVE_LINK_L | TOWER_L_B | 0 / 350 | 2496.000 / 2496.000 |
| DRIVE_LINK_L | RAIL_L_B | 0 / 350 | 170.384 / 216.000 |
| DRIVE_LINK_L | SEAL_VERT_L_202 | 0 / 60 | 144.000 / 288.000 |
| BRACKET_R_F_1 | TOWER_R_F | 0 / 350 | 735.523 / 735.523 |
| BRACKET_R_F_2 | TOWER_R_F | 0 / 350 | 735.523 / 735.523 |
| BRACKET_R_B_1 | TOWER_R_B | 0 / 350 | 735.523 / 735.523 |
| BRACKET_R_B_2 | TOWER_R_B | 0 / 350 | 735.523 / 735.523 |
| DRIVE_LINK_R | TOWER_R_B | 0 / 350 | 2496.000 / 2496.000 |
| DRIVE_LINK_R | RAIL_R_B | 0 / 350 | 170.384 / 216.000 |
| DRIVE_LINK_R | SEAL_VERT_R_202 | 0 / 60 | 144.000 / 288.000 |

Scope người dùng đã chọn: tấm cửa + block + ty tham số. P09/P11 ẩn và giữ pose nguồn; không dùng animation xuyên những part này để giả lập cơ cấu hợp lệ.
Full assembly có thể xem ở CLOSED, nhưng chuyển động/video bị chặn. CAD sửa lỗi phải được nhập lại và kiểm tra trước khi xác nhận toàn cơ cấu.