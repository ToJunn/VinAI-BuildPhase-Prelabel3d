# TASKS — Xây dựng web prelabel cuboid 3D với nuScenes và CVAT

## 1. Lệnh giao việc cho Codex

Bạn là kỹ sư triển khai dự án này trong workspace `D:\build-phase`. Đọc toàn bộ tài liệu, kiểm tra code hiện có và thực hiện các task theo thứ tự phụ thuộc. Tự giải quyết lựa chọn triển khai thông thường. Sau mỗi milestone, cập nhật checklist và ghi kết quả chạy thực tế. Không chỉ đưa kế hoạch; phải tạo code, chạy và sửa lỗi trong phạm vi môi trường cho phép. Nếu thiếu GPU, checkpoint hoặc CVAT, hoàn thành phần độc lập và báo rõ phần bị chặn; không giả kết quả thành công.

Mục tiêu: chọn scene nuScenes trên web → chạy model 3D pretrained → xem point cloud và cuboid dự đoán → xuất dữ liệu để sửa trong CVAT.

## 2. Bối cảnh và phạm vi

- Dataset đã được tải và giải nén ở `D:\build-phase\nuscenes`.
- Dự kiến phiên bản `v1.0-mini`; xác nhận từ folder trước khi chạy.
- Máy Windows, RTX 4050 Laptop 6 GB VRAM. Có thể dùng WSL2/Ubuntu cho inference nếu thư viện cần CUDA extensions trên Linux.
- Giao diện và API chạy local. Frontend port 5173; backend port 8000, đổi được bằng cấu hình.
- MVP chạy inference, không huấn luyện, không VLM.
- CVAT là nơi chỉnh sửa annotation. Web MVP chỉ xem, lọc và xuất kết quả; chưa xây đầy đủ bộ công cụ vẽ cuboid.
- Không tải lại dataset, không copy dataset vào source/output, không xóa dữ liệu gốc.
- Không cần tài khoản người dùng, cloud hosting, microservices hoặc Redis/Celery cho MVP một người dùng.
- Model chưa được chốt. Phải chọn một checkpoint nuScenes thực sự có nguồn tải và runtime tương thích; không tự mặc định model Kaggle trước đó đã sẵn sàng.

## 3. Kiến trúc và vai trò

| Thành phần | Công nghệ dự kiến | Vai trò |
|---|---|---|
| Frontend | React + TypeScript + Vite | Chọn scene/frame, tạo job, theo dõi tiến độ, xem và tải kết quả |
| Viewer | Three.js / React Three Fiber | Hiển thị LiDAR và cuboid trong cùng hệ tọa độ |
| API | FastAPI + Pydantic | Kiểm tra request, truy cập dataset, quản lý job, phục vụ dữ liệu |
| Dataset adapter | nuScenes devkit + NumPy | Đọc metadata, liên kết camera/LiDAR, calibration và frame |
| Inference worker | Python riêng, PyTorch và framework phù hợp | Nạp model, xử lý LiDAR, chạy GPU, chuyển prediction về schema chung |
| Job store | SQLite | Lưu cấu hình, trạng thái, tiến độ, lỗi và đường dẫn output |
| Exporter | Python | Chuyển point cloud và prediction sang định dạng CVAT hỗ trợ |
| CVAT | Instance local hiện có | Import, xem và sửa cuboid |

API không import trực tiếp framework inference nặng. Worker chạy bằng subprocess với interpreter cấu hình riêng để tách dependencies và giữ API hoạt động khi model lỗi.

## 4. Cấu trúc thư mục mục tiêu

```text
D:\build-phase\
├── CODEX_TASKS_PRELABEL_3D.md
├── README.md
├── .gitignore
├── .env.example
├── nuscenes/                         # Dataset gốc, chỉ đọc, không commit
│   ├── samples/
│   ├── sweeps/
│   ├── maps/
│   └── v1.0-mini/
├── backend/
│   ├── requirements.txt             # Dependencies API nhẹ, pin phiên bản đã thử
│   ├── app/
│   │   ├── main.py                  # FastAPI, routers, startup/shutdown
│   │   ├── config.py                # Đọc env và resolve đường dẫn
│   │   ├── api/
│   │   │   ├── datasets.py          # Dataset/scene/frame/camera/point cloud
│   │   │   ├── jobs.py              # Submit, status, cancel, retry
│   │   │   ├── predictions.py       # Đọc kết quả theo frame
│   │   │   └── exports.py           # Tạo gói CVAT và tải file
│   │   ├── schemas/                 # Request/response và prediction canonical
│   │   ├── datasets/
│   │   │   └── nuscenes_adapter.py  # Index metadata, thứ tự frame, calibration
│   │   ├── services/
│   │   │   ├── job_service.py       # Điều phối subprocess và trạng thái
│   │   │   ├── prediction_store.py  # Ghi/đọc output atomic
│   │   │   └── export_service.py    # Export đúng prediction được chọn
│   │   ├── exporters/
│   │   │   └── cvat_exporter.py     # PCD + annotation + frame mapping
│   │   └── storage/
│   │       └── database.py          # SQLite và migrations tối thiểu
│   └── tests/                       # Test transform, ordering, jobs, export
├── inference/
│   ├── requirements.txt             # Runtime model riêng, ghi matrix tương thích
│   ├── worker.py                    # CLI nhận job manifest, ghi progress/result
│   ├── model_adapter.py             # Interface chung
│   ├── adapters/                    # Một adapter model thật cho MVP
│   └── configs/                     # Config model và preprocessing tương ứng
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api/                     # Typed API client, xử lý lỗi
│       ├── types/                   # Dataset, job, cuboid, export
│       ├── pages/                   # Dataset, Workspace, Jobs
│       ├── components/
│       │   ├── viewer/              # Point cloud, boxes, axes, camera controls
│       │   ├── camera/              # Camera preview và projection
│       │   └── jobs/                # Progress, error, retry
│       └── styles/                  # Theme và layout
├── scripts/
│   ├── start_backend.ps1
│   ├── start_frontend.ps1
│   ├── setup_inference.sh           # Khi chọn WSL/Linux
│   └── smoke_pipeline.py            # Chạy pipeline một frame không cần web
├── models/                          # Checkpoint ngoài Git
├── runtime/
│   ├── app.db
│   ├── jobs/<job_id>/               # request.json, progress.json, log.txt
│   ├── predictions/<job_id>/        # Một JSON cho mỗi sample_token
│   ├── exports/<export_id>/         # ZIP, manifest, mapping
│   └── cache/                       # Point cloud preview có giới hạn dung lượng
└── docs/
    ├── SETUP.md                     # Windows/WSL, lệnh chạy, troubleshooting
    ├── MODEL_RUNTIME.md             # Model, nguồn checkpoint, version matrix
    ├── COORDINATES.md               # Axis, dimensions, origin, yaw, transforms
    ├── CVAT_IMPORT.md               # Phiên bản CVAT, format và bước import thật
    └── VALIDATION.md                # Kết quả kiểm thử và giới hạn
```

Nếu workspace đã có code, giữ cấu trúc hợp lý hiện có và ghi mapping thay vì tạo project trùng. Thêm dataset, venv, node_modules, checkpoint, runtime và secrets vào `.gitignore`.

## 5. Cấu hình

Tạo `.env.example` với nội dung mẫu; `.env` thật không commit:

```dotenv
DATASET_ROOT=D:/build-phase/nuscenes
NUSCENES_VERSION=v1.0-mini
RUNTIME_ROOT=D:/build-phase/runtime
MODEL_ROOT=D:/build-phase/models
API_HOST=127.0.0.1
API_PORT=8000
FRONTEND_ORIGIN=http://localhost:5173
INFERENCE_PYTHON=
MODEL_CONFIG=
MODEL_CHECKPOINT=
DEVICE=cuda:0
MAX_CONCURRENT_JOBS=1
DEFAULT_SCORE_THRESHOLD=0.3
PREVIEW_MAX_POINTS=100000
CVAT_URL=http://localhost:8080
```

- `INFERENCE_PYTHON`: interpreter thực tế đã được setup, không đoán đường dẫn.
- Nếu API/worker cùng WSL: dùng `/mnt/d/build-phase/...`. Nếu API Windows và worker WSL: xây mapper Windows↔WSL rõ ràng; không truyền nguyên `D:\...` cho Python Linux.
- Frontend dùng `VITE_API_BASE_URL=http://localhost:8000` trong env riêng.
- API và worker phải cùng nhìn thấy manifest/output. Kiểm tra mount bằng đọc/ghi file nhỏ.
- Model config/checkpoint được validate khi submit job; thiếu file trả lỗi cụ thể.
- Chỉ phục vụ file dưới dataset/runtime roots được phép; resolve đường dẫn chống `../` và symlink thoát root.

## 6. Schema dữ liệu và hệ tọa độ bắt buộc

Prediction canonical dưới đây là schema nội bộ, KHÔNG phải file import CVAT:

```json
{
  "schema_version": "1.0",
  "job_id": "job-id",
  "scene_token": "scene-token",
  "sample_token": "sample-token",
  "lidar_sample_data_token": "lidar-token",
  "frame_index": 0,
  "timestamp_us": 0,
  "coordinate_frame": "LIDAR_TOP",
  "units": "meters",
  "box_origin": "geometric_center",
  "axis_convention": "x_right_y_forward_z_up",
  "model": {"name": "verified-model", "checkpoint_sha256": "hash"},
  "boxes": [{
    "id": "frame-local-box-id",
    "label": "car",
    "score": 0.91,
    "center": [1.0, 2.0, 0.5],
    "size_lwh": [4.2, 1.8, 1.6],
    "yaw_rad": 0.3
  }]
}
```

- Xác minh convention `LIDAR_TOP` từ devkit và model, không chỉ tin tên trường.
- Size luôn `[length, width, height]`; nuScenes box và framework có thể dùng thứ tự khác.
- Center luôn tâm hình học; model dùng bottom center phải chuyển trước khi lưu.
- Yaw quanh +Z, radian, chuẩn hóa về `[-pi, pi)`; ghi hướng dương trong docs.
- Model yaw khác quy ước phải có phép chuyển và test. Không suy đoán đầu xe từ hình hộp đối xứng.
- Prediction và PCD phải chung frame LiDAR. Dùng calibration + ego pose để chuyển ground truth từ global về LiDAR khi debug.
- Trường `frame_index` là index trong scene đã chọn; exporter tạo mapping riêng khi xuất subset.
- `id` chỉ là ID mỗi frame; không quảng cáo tracking qua frame khi chưa triển khai.
- Scene traversal theo `sample.next`, kiểm tra timestamp tăng; không dựa vào thứ tự tên file.
- nuScenes LiDAR `.bin` phải đọc theo layout thực tế của devkit; kiểm tra shape trước khi reshape, không mặc định bốn float mỗi point.

## 7. Checklist triển khai theo thứ tự

### T00 — Khảo sát workspace và môi trường

- [x] Đọc AGENTS.md nếu có, liệt kê project hiện có; không ghi đè code người dùng.
- [x] Xác nhận bốn folder dataset và metadata `scene.json`, `sample.json`, `sample_data.json`.
- [x] Ghi Python, Node, GPU driver, CUDA khả dụng và WSL vào `docs/SETUP.md`.
- [x] Chọn Windows hay WSL cho từng thành phần; ghi lý do thực tế.

**Hoàn thành khi:** có cấu hình đường dẫn rõ ràng và lệnh chạy dự kiến; báo thiếu dependencies cụ thể.

### T01 — Dựng API và config

- [x] Tạo skeleton FastAPI, env validation, logging, CORS cho frontend local.
- [x] Health endpoint và SQLite store.
- [x] Startup không cần import/nạp model, không tải checkpoint tự động.

**Hoàn thành khi:** `/api/health` trả trạng thái API và khả năng truy cập dataset; lỗi cấu hình có thông báo dễ hiểu.

### T02 — Đọc dataset thật

- [x] Implement adapter đọc scenes và samples, cache metadata một lần.
- [x] API scenes, frames và camera image theo token.
- [x] API point cloud binary `float32 xyz`, ghi số point và format; giảm mẫu chỉ cho preview.
- [x] Giữ LiDAR đầy đủ cho inference/export, không dùng bản preview.
- [x] Validate sample token thuộc scene; camera timestamp có metadata.

**Hoàn thành khi:** lấy được một frame thật, ảnh camera và LiDAR từ dataset local; không dùng dữ liệu random.

### T03 — Chốt model và chạy inference một frame

- [x] Kiểm tra tài liệu chính thức của framework, model zoo, config và nguồn checkpoint.
- [x] Chọn một model pretrained nuScenes phù hợp VRAM 6 GB, ưu tiên LiDAR-only nếu có runtime đã xác minh.
- [x] Ghi URL nguồn, license, checksum, framework commit/version, Python/PyTorch/CUDA/extensions trong `docs/MODEL_RUNTIME.md`.
- [x] Tách môi trường inference, pin dependencies theo tổ hợp đã chạy được.
- [x] Nạp checkpoint, eval mode, no_grad, batch size 1.
- [x] Chuẩn bị đúng features/sweeps theo config. Không dùng checkpoint 10 sweeps với input 1 sweep mà không đánh giá/ghi rõ khác biệt.
- [x] Transform sweep trước về current LiDAR; time lag đúng đơn vị và thứ tự feature model.
- [x] Chuyển output sang schema canonical, validate finite values/positive sizes/labels/scores.
- [ ] Nếu OOM, giảm cấu hình theo khả năng model và ghi lại; không đổi preprocessing âm thầm.

**Hoàn thành khi:** `scripts/smoke_pipeline.py` chạy một frame thật và lưu prediction hợp lệ, có log model/VRAM/thời gian. Mock adapter chỉ dùng test và phải ghi rõ mock; chưa được tính hoàn thành inference.

### T04 — Xuất CVAT và xác minh sớm

- [ ] Kiểm tra phiên bản CVAT đang dùng và format import cuboid 3D được phiên bản đó hỗ trợ qua docs/source chính thức.
- [ ] Lấy một annotation export mẫu từ CVAT để xác định rotation, size và labels nếu cần.
- [x] Chuyển LiDAR sang PCD đúng chuẩn CVAT hỗ trợ.
- [ ] Xuất annotation bằng format được xác minh; không đổi đuôi JSON nội bộ rồi gọi là CVAT format.
- [x] Tên frame zero-pad: `000000.pcd`, `000001.pcd`, ... và mapping đến sample token.
- [x] Export subset phải remap frame index liên tục từ 0, cùng thứ tự giữa point cloud và annotation.
- [x] Lưu manifest: model hash, dataset version, scene, selected tokens, threshold, labels và convention.
- [ ] Import một frame vào CVAT thực tế, đối chiếu cuboid cùng point cloud; kiểm tra center, kích thước và yaw.

**Hoàn thành khi:** một prediction thật import được vào CVAT. Nếu không có instance truy cập được, hoàn thành exporter/tests và ghi rõ chưa xác minh import thực tế.

### T05 — Worker và job management

- [x] CLI worker nhận manifest, ghi progress và kết quả atomic.
- [x] SQLite states: queued → running → completed/failed/cancelled.
- [x] Chỉ một inference job GPU tại một thời điểm; API không bị block.
- [x] Progress gồm tổng frame, số xử lý, sample hiện tại, elapsed và thông báo.
- [x] Cancel chấm dứt worker process tree, lưu kết quả đã hoàn tất.
- [x] Retry tạo job mới, giữ provenance job cũ, không overwrite kết quả.
- [x] Khi restart, reconcile job running bị mất worker; không để running mãi.
- [x] Job thất bại trả stderr đã lọc thông tin nhạy cảm, không giấu lỗi.

**Hoàn thành khi:** chạy một scene, xem tiến độ; lỗi checkpoint và cancel được phản ánh đúng.

### T06 — Frontend dùng API thật

- [ ] Trang Dataset: root/version/status, scene list, số frame và nút mở workspace.
- [ ] Workspace: scene selector, frame slider/prev/next, camera preview, viewer và danh sách boxes.
- [ ] Panel inference: model khả dụng, range frame, threshold và Run Prelabel.
- [ ] Jobs: progress, trạng thái, error, cancel/retry.
- [ ] Loading/empty/error states rõ ràng; chưa inference phải hiện chưa có prediction.
- [ ] Typed API client và polling có cleanup; không tạo request chồng vô hạn.

**Hoàn thành khi:** người dùng chọn frame thật và submit job trên web, xem kết quả khi hoàn tất.

### T07 — Viewer 3D

- [ ] Render point cloud bằng BufferGeometry, orbit/pan/zoom, reset view, axes và top view.
- [ ] Viewer dùng cùng convention với prediction; Three.js world phải cấu hình hoặc chuyển thống nhất cho Z-up.
- [ ] Cuboid có màu theo class, click chọn, hiển thị score/center/size/yaw.
- [ ] Bộ lọc class/score hoạt động; phân biệt threshold lúc inference và threshold lúc xem/export.
- [ ] Dispose GPU resources khi đổi frame, hủy fetch cũ tránh hiển thị frame trễ.
- [ ] Camera projection là phần bổ sung: dùng intrinsic/extrinsic/ego pose đúng timestamp, lọc điểm sau camera. Không vẽ overlay sai để đẹp giao diện.

**Hoàn thành khi:** LiDAR và prediction khớp không gian, đổi frame không tăng bộ nhớ liên tục.

### T08 — Export trên web

- [ ] Chọn job, subset frame, score threshold và class cần export.
- [ ] Tạo export async nếu nhiều frame; hiển thị tiến độ và link download.
- [ ] ZIP chứa đúng payload mà hướng dẫn CVAT yêu cầu; manifest/mapping phụ không làm hỏng parser.
- [ ] Nếu cần hai ZIP riêng cho data/annotation, UI và docs nêu rõ từng bước.
- [ ] Link mở CVAT; MVP có thể import thủ công, chưa cần tự động tạo task qua API.

**Hoàn thành khi:** từ web tải gói một scene và import được vào CVAT đúng frame/label.

### T09 — Kiểm thử và bàn giao

- [x] Test transforms: center origin, size order, yaw 0/±pi/2, round-trip calibration.
- [x] Test sweep alignment, binary LiDAR parsing, scene ordering và subset mapping.
- [x] Test job fail/cancel/restart và export threshold.
- [x] Chạy frontend typecheck/build, backend tests và pipeline smoke thật nếu runtime có.
- [x] Viết README và scripts chạy, cập nhật `docs/VALIDATION.md` với lệnh/kết quả thực tế.
- [x] Ghi rõ phần chưa kiểm tra do không có GPU/CVAT; không ghi tất cả tests pass khi chưa chạy.

**Hoàn thành khi:** người khác làm theo README có thể chọn scene → chạy model → xem → export/import CVAT.

## 8. API contract đề xuất

| Method | Endpoint | Nội dung |
|---|---|---|
| GET | `/api/health` | API/config/dataset status, không nạp model |
| GET | `/api/dataset` | Root, version, số scenes, khả dụng |
| GET | `/api/scenes` | Danh sách scene có pagination |
| GET | `/api/scenes/{scene_token}/frames` | Sample tokens theo thời gian |
| GET | `/api/frames/{sample_token}` | Metadata LiDAR, camera, calibration |
| GET | `/api/frames/{sample_token}/points` | Binary preview XYZ và point count |
| GET | `/api/frames/{sample_token}/camera/{channel}` | Image từ channel whitelist |
| GET | `/api/models` | Config/checkpoint đã đăng ký, availability |
| POST | `/api/jobs` | Scene/token subset/model/threshold |
| GET | `/api/jobs` | Lịch sử jobs |
| GET | `/api/jobs/{job_id}` | Status/progress/error |
| POST | `/api/jobs/{job_id}/cancel` | Cancel idempotent |
| POST | `/api/jobs/{job_id}/retry` | Tạo job mới |
| GET | `/api/jobs/{job_id}/predictions/{sample_token}` | Canonical boxes |
| POST | `/api/exports` | Job/subset/classes/threshold |
| GET | `/api/exports/{export_id}` | Status và output metadata |
| GET | `/api/exports/{export_id}/download` | ZIP đã hoàn thành |

Request validation: threshold [0,1], frame range không rỗng, token phải thuộc dataset/scene, model phải tồn tại. Trả 4xx cho input sai và trạng thái job rõ ràng cho worker failure.

## 9. Bố cục giao diện

- Sidebar: Dataset, Workspace, Jobs.
- Thanh trên: scene hiện tại, trạng thái dataset/model, Run Prelabel, Export CVAT.
- Giữa: viewer 3D chiếm diện tích chính.
- Bên phải: camera preview và danh sách cuboid; chọn box sẽ highlight viewer.
- Dưới: timeline frame, previous/next, timestamp và job progress.
- Theme tối, chữ dễ đọc, màu class nhất quán; ưu tiên thao tác desktop.
- Ground truth nếu hiển thị phải bật riêng và ghi nhãn Ground truth; không trộn với prediction hoặc export dưới danh nghĩa model output.

## 10. Giới hạn và nguyên tắc nghiệm thu

1. Chưa cần tracking, VLM, training, multi-user hoặc annotation editor đầy đủ.
2. Inference trên CPU không được hứa nhanh; nếu GPU runtime chưa sẵn sàng, báo blocker cụ thể.
3. Không tải checkpoint hoặc framework khổng lồ trước khi kiểm tra dung lượng và tổ hợp runtime.
4. Không sửa dataset gốc; output/cache có quota và có cleanup được người dùng chủ động chọn.
5. Export chỉ dùng prediction thật từ job đã hoàn tất hoặc những frame hoàn tất được chọn rõ ràng.
6. CVAT coordinate format phải dựa trên phiên bản thực tế, có bằng chứng import; schema nội bộ không thay thế việc kiểm chứng.
7. Mỗi milestone báo: file thay đổi, hành vi đã chạy, lệnh kiểm tra, phần còn thiếu.
8. Giữ tài liệu này như checklist sống; cập nhật trạng thái bằng bằng chứng, không đánh dấu theo dự định.

## 11. Milestone ưu tiên

| Milestone | Tasks | Kết quả cần có |
|---|---|---|
| M1 | T00–T02 | API đọc được một frame nuScenes thật |
| M2 | T03–T04 | Model thật → canonical prediction → CVAT một frame |
| M3 | T05–T07 | Web chọn scene, chạy job và xem cuboid |
| M4 | T08–T09 | Export scene, kiểm thử, tài liệu và scripts bàn giao |

Bắt đầu ngay T00–T02; sau đó giải quyết runtime model và CVAT ở M2 trước khi mở rộng giao diện.
## 12. Kết quả triển khai thực tế — 2026-10-12

- M1 / T00–T02: đã chạy API trên dataset thật. Root chính xác `D:/build-phase/nuscenes/v1.0-mini`; xác nhận 10 scenes, 404 LiDAR keyframes và 2.424 ảnh camera. Có `backend/.venv`, `backend/.env`, `frontend/.env` và dependency FE riêng. Source nằm trong workspace hiện tại, không ghi vào thư mục cha hoặc dataset gốc.
- M2: runtime thật đã chạy trong env Linux riêng, PointPillars checkpoint khớp SHA256. Smoke có 18 boxes, khoảng 10,6 giây, peak VRAM 573 MiB. Đã chạy scene 39 frames qua API: 1.412 boxes, peak VRAM khoảng 1,93 GiB. CVAT tại port 8080 chưa phản hồi; chưa thể xác minh phiên bản/import thật. Exporter có PCD, Datumaro 3D, manifest và test subset/threshold; không gọi fixture là prediction thật.
- M3: worker subprocess, SQLite job queue/cancel/retry/restart, typed FE, Workspace/Jobs và viewer Z-up đã được triển khai. API đã xác minh trạng thái queued/running/completed, vẫn trả health trong lúc GPU chạy; cancel chấm dứt process group WSL. Unit tests xác minh thêm lỗi/retry/restart và process con Windows. Không có browser automation session khả dụng nên thao tác viewer/memory/UI chưa được kiểm tra trực tiếp.
- M4: async export scene thật và download bundle 13.825.954 bytes đã chạy thành công; có README, setup/start/smoke scripts và tài liệu. FE typecheck/build qua, npm audit không còn vulnerability; backend 8 tests qua. Live CVAT round-trip vẫn chưa nghiệm thu.
- Điều chỉnh có căn cứ: giữ nguyên raw `LIDAR_TOP` theo trục X phải/Y trước/Z lên; schema khai báo `x_right_y_forward_z_up`, không gắn nhãn ego axes lên sensor points. Xem `docs/COORDINATES.md`.
- Mapping cấu trúc: `backend/app/dataset.py`, `jobs.py`, `exporter.py`, `storage.py`, `schemas.py` gom module MVP; route handlers nằm trong `main.py`. FE pages/panels nằm trong `src/main.tsx`, viewer tách `src/Viewer.tsx` và được lazy-load.
- Checklist UI và live CVAT vẫn để trống vì code/build không thay thế bằng chứng thao tác/import. Kết quả lệnh, hash và giới hạn nằm trong `docs/VALIDATION.md`.
