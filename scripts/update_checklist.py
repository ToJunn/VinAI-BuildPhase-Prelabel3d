"""Update only evidence-backed checklist rows; do not mark UI/live CVAT acceptance."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/'CODEX_TASKS_PRELABEL_3D.md'
text=path.read_text(encoding='utf-8')
verified_prefixes=[
    'Đọc AGENTS.md', 'Xác nhận bốn folder', 'Ghi Python, Node', 'Chọn Windows hay WSL',
    'Tạo skeleton FastAPI', 'Health endpoint', 'Startup không cần',
    'Implement adapter', 'API scenes', 'API point cloud', 'Giữ LiDAR đầy đủ', 'Validate sample token',
    'Kiểm tra tài liệu chính thức', 'Ghi URL nguồn', 'Transform sweep trước',
    'Chọn một model pretrained', 'Tách môi trường inference', 'Nạp checkpoint',
    'Chuẩn bị đúng features/sweeps', 'Chuyển output sang schema canonical',
    'Chuyển LiDAR sang PCD',
    'Tên frame zero-pad', 'Export subset phải', 'Lưu manifest',
    'SQLite states', 'Retry tạo job mới', 'Khi restart', 'Job thất bại',
    'CLI worker', 'Chỉ một inference job GPU', 'Progress gồm tổng frame', 'Cancel chấm dứt',
    'Test sweep alignment', 'Test job fail/cancel/restart',
    'Test transforms', 'Chạy frontend typecheck/build', 'Viết README và scripts', 'Ghi rõ phần chưa kiểm tra',
]
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('- [ ] ') and any(line[6:].startswith(prefix) for prefix in verified_prefixes):
        lines[i]=line.replace('- [ ] ','- [x] ',1)
heading='## 12. Kết quả triển khai thực tế'
text='\n'.join(lines)+'\n'
text=text.replace('"axis_convention": "x_forward_y_left_z_up"', '"axis_convention": "x_right_y_forward_z_up"')
if heading in text:text=text.split(heading)[0]
text+=heading+''' — 2026-10-12

- M1 / T00–T02: đã chạy API trên dataset thật. Root chính xác `D:/build-phase/nuscenes/v1.0-mini`; xác nhận 10 scenes, 404 LiDAR keyframes và 2.424 ảnh camera. Có `backend/.venv`, `backend/.env`, `frontend/.env` và dependency FE riêng. Source nằm trong workspace hiện tại, không ghi vào thư mục cha hoặc dataset gốc.
- M2: runtime thật đã chạy trong env Linux riêng, PointPillars checkpoint khớp SHA256. Smoke có 18 boxes, khoảng 10,6 giây, peak VRAM 573 MiB. Đã chạy scene 39 frames qua API: 1.412 boxes, peak VRAM khoảng 1,93 GiB. CVAT tại port 8080 chưa phản hồi; chưa thể xác minh phiên bản/import thật. Exporter có PCD, Datumaro 3D, manifest và test subset/threshold; không gọi fixture là prediction thật.
- M3: worker subprocess, SQLite job queue/cancel/retry/restart, typed FE, Workspace/Jobs và viewer Z-up đã được triển khai. API đã xác minh trạng thái queued/running/completed, vẫn trả health trong lúc GPU chạy; cancel chấm dứt process group WSL. Unit tests xác minh thêm lỗi/retry/restart và process con Windows. Không có browser automation session khả dụng nên thao tác viewer/memory/UI chưa được kiểm tra trực tiếp.
- M4: async export scene thật và download bundle 13.825.954 bytes đã chạy thành công; có README, setup/start/smoke scripts và tài liệu. FE typecheck/build qua, npm audit không còn vulnerability; backend 8 tests qua. Live CVAT round-trip vẫn chưa nghiệm thu.
- Điều chỉnh có căn cứ: giữ nguyên raw `LIDAR_TOP` theo trục X phải/Y trước/Z lên; schema khai báo `x_right_y_forward_z_up`, không gắn nhãn ego axes lên sensor points. Xem `docs/COORDINATES.md`.
- Mapping cấu trúc: `backend/app/dataset.py`, `jobs.py`, `exporter.py`, `storage.py`, `schemas.py` gom module MVP; route handlers nằm trong `main.py`. FE pages/panels nằm trong `src/main.tsx`, viewer tách `src/Viewer.tsx` và được lazy-load.
- Checklist UI và live CVAT vẫn để trống vì code/build không thay thế bằng chứng thao tác/import. Kết quả lệnh, hash và giới hạn nằm trong `docs/VALIDATION.md`.
'''
path.write_text(text,encoding='utf-8')
