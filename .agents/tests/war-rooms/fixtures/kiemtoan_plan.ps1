# Fixture v2 — KiemToan Plan v3.0 (final version with ## EPIC headers)
# This matches the exact indentation/style in the production plan:
# - ## EPIC-001: (level 2, colon separator)
# - #### Mục tiêu (level 4)
# - ### Tasks (level 3)
# - ### Definition of Done (level 3, no checkbox format for DoD items in EPIC-001/002)

$Script:Epic001_TaskDescription = @"
Roles: @engineer

#### Mục tiêu
Biến 820 tệp thô thành kho tài liệu có cấu trúc với bảng ``documents`` đầy đủ metadata, đồng thời trích xuất "Fact" pháp lý từ văn bản.

### Tasks

- [ ] **TASK-1.1 — Scanner đệ quy + deduplication**
  - Quét toàn bộ ``/audit-docs``, tính SHA256, bỏ qua ``~$...`` (Word temp files), xử lý riêng ``.jpg`` (OCR optional).
  - **Gotcha đã phát hiện:** Nhánh ``Các đơn vị gửi về`` và ``Các đơn vị gửi về-1`` có ~95% trùng file — dedup bằng SHA256, giữ bản mới nhất theo ``mtime``.
  - Output: Bảng ``documents`` với ≥ 95% coverage.

- [ ] **TASK-1.2 — Phân loại 4 nhóm SAV**
  - ``01-muc-tieu/``: QĐ 749, QĐ 942, NQ57, NQ66, NQ68, NĐ 118/2025, KH số hóa, Chiến lược CĐS (QĐ 4220), Chiến lược dữ liệu (QĐ 4221).
  - ``02-doi-tuong/``: Tất cả tài liệu thuộc ``Cung cấp dữ liệu KT/`` và ``Các đơn vị gửi về/``.
  - ``03-co-quan/``: QĐ thành lập BCĐ 934, QĐ tiểu ban (1100, 1208, 1327), QĐ phân công, KH công tác hàng năm các Cục.
  - ``04-tham-chieu/``: Bộ tài liệu ``Tài liệu kiểm chứng/`` + ``PL03.x/`` + ``Tài liệu kiểm chứng phòng HTS/``.

- [ ] **TASK-1.3 — Ánh xạ sang Phụ lục SAV**
  - PL01 (Kế hoạch): KHCT 2024/2025 các Cục, KH CĐS 2024, KH BCĐ 934.
  - PL02 (Dự án/KH): File Excel ``Phu luc kiem toan...`` của 15+ đơn vị.
  - PL03 (Ngân sách): ``Phu luc kiem toan CNTT 2024-2025 NSSNTSC.xlsx`` của Vụ KHTC.
  - PL04 (Hợp đồng CNTT): Tách từ các Phụ lục của Cục HTQT, TDTT, Điện ảnh, NTBD, PTTH, VHCS, TTCS.
  - PL05 (Nhân sự): Lấy từ báo cáo CCHC + phụ lục các đơn vị.
  - PL06 (ATTT): ``Tài liệu kiểm chứng phòng HTS/`` (10 báo cáo giám sát 2025, QĐ 3907, QĐ 104, QĐ 30).

- [ ] **TASK-1.4 — LLM Fact Extraction (chunking 3-1)**
  - Chiến lược: đọc cụm 3 trang, overlap 1 trang.
  - Extract 4 loại fact: ``muc_tieu``, ``tieu_chi``, ``nghia_vu``, ``chi_so``.
  - Mọi fact phải có ``(source_doc_id, page_number, paragraph_reference)``.
  - **Tập văn bản ưu tiên extract trước** (vì chứa target KPI định lượng):
    1. QĐ 749 + Phụ lục 2 KHUNG BÁO CÁO 749.
    2. QĐ 1973 + QĐ 2251 (Danh mục DVCTT toàn trình).
    3. QĐ 4220 (Chiến lược CĐS) + QĐ 4221 (Chiến lược dữ liệu).
    4. KH CĐS 2024 + KH BCĐ 934 + 3 PL (CCHC, KHCN, CĐS).
    5. BC CCHC 2024 + BC CCHC 2025.

- [ ] **TASK-1.5 — Cross-reference matrix**
  - QĐ 44 (15/1/2025) **replaces** QĐ 503 (9/4/2024) + QĐ 1264 (26/7/2024) → Cục XBI.
  - QĐ 4589 **replaces** QĐ tái cấu trúc QT cũ → Văn phòng Bộ.
  - QĐ 2551 (DVCTT 2025) **replaces** QĐ 1973 (DVCTT 2024).
  - QĐ 4508 **implements** NQ66.7 (thay TPHS bằng dữ liệu).

- [ ] **TASK-1.6 — Capability Map**
  - Tối thiểu 10 năng lực cốt lõi × 15 đơn vị.
  - Ví dụ năng lực: ``Cung cấp DVCTT toàn trình``, ``Kết nối CSDL chuyên ngành``, ``Số hóa hồ sơ``, ``Thanh toán trực tuyến``, ``An toàn thông tin``, ``Quy trình nội bộ``, ``Báo cáo CCHC``, ``Kiểm soát TTHC``, ``Đào tạo CNTT``, ``Đồng bộ DVCQG``.

### Definition of Done
- 100% tài liệu phân loại vào 4 nhóm SAV.
- Bảng ``facts`` có ≥ 500 fact với source coordinates.
- Cross-reference matrix có ≥ 30 quan hệ ``replaces/amends``.
- Capability map phủ 15 đơn vị × 10 năng lực = 150 mapping entries.
- Coverage chunking ≥ 95% số trang.
"@

$Script:Epic001_DoD = @(
    "100% tài liệu phân loại vào 4 nhóm SAV",
    "Bảng facts có ≥ 500 fact với source coordinates",
    "Cross-reference matrix có ≥ 30 quan hệ replaces/amends",
    "Capability map phủ 15 đơn vị × 10 năng lực",
    "Coverage chunking ≥ 95% số trang"
)

$Script:Epic002_TaskDescription = @"
Roles: @engineer
depends_on: [EPIC-001]
#### Mục tiêu
Xây ETL pipeline idempotent biến các file Excel lộn xộn từ các Cục thành dữ liệu chuẩn hóa trong SQLite, sẵn sàng đối chiếu với Fact từ EPIC-001.
Xác định cây thư mục bằng command ``tree .`` để xác định các nhóm dữ liệu cần quét
#### Kho dữ liệu định lượng đích danh cần ingest

| Nguồn file | Bảng đích | Ưu tiên | Ghi chú xử lý |
|---|---|---|---|
| ``*.xlsx`` | ``pl02_plans`` + KPI | **P0** | **Gold standard** — đối chiếu tỷ lệ đồng bộ DVCQG |
| ``Phu luc kiem toan cua Trung tâm CĐS 2026.xlsx`` | Tổng hợp | P0 | Master consolidation file |

### Tasks

- [ ] **TASK-2.1 — File Discovery & Classifier**
  ``python
  for root, dirs, files in os.walk("/audit-docs"):
      for f in files:
          if f.startswith("~$"): continue
          if f.endswith((".xlsx", ".xls", ".csv")):
              classify_to_appendix(f)
  ``

- [ ] **TASK-2.2 — Schema Inference & Column Mapping**
  - Mỗi đơn vị dùng template khác nhau → build ``column_mapping.yaml`` per-unit.
  - Chuẩn hóa header Tiếng Việt (có dấu, không dấu, viết tắt) về canonical names.

- [ ] **TASK-2.3 — Data Validators**
  - **Completeness**: trường bắt buộc (``unit``, ``date``, ``value``) ≥ 95%.
  - **Consistency**: đối chiếu tổng phụ lục ↔ báo cáo CCHC.
  - **Accuracy**: giá trị trong [min, max] hợp lý (VD: tỷ lệ ∈ [0, 100]).
  - **Timeliness**: file có ``date_issued`` trong hoặc trước Audit Period.
  - File lỗi → đẩy vào ``exception_report`` table, hiển thị Dashboard View 5.

- [ ] **TASK-2.4 — Merge-cell & Multi-header Excel handler**
  - Dùng ``openpyxl`` với ``merged_cells`` unmerge trước khi đọc.
  - Với file có 2–3 dòng header (ví dụ Phụ lục NTBD, KHTC), flatten bằng concat ``_``.

- [ ] **TASK-2.5 — Idempotent ETL**
  - Upsert theo ``(source_file_sha256, source_row)`` → chạy lại không sinh duplicate.
  - Ghi log vào ``etl_runs`` table với ``start_ts``, ``end_ts``, ``rows_inserted``, ``rows_skipped``, ``errors``.

- [ ] **TASK-2.6 — 10 KPI Views**

### Definition of Done
- Pipeline idempotent — chạy 3 lần ra cùng kết quả.
- Data Quality Score ≥ 90% cho trường bắt buộc.
- Mọi row có ``(source_file, source_row, ingested_at)``.
- ≥ 10 KPI views hoạt động với dữ liệu 2024–2025.
- ``exception_report`` liệt kê rõ file lỗi + lý do để Kiểm toán viên yêu cầu bổ sung.
"@

$Script:Epic002_DoD = @(
    "Pipeline idempotent — chạy 3 lần ra cùng kết quả",
    "Data Quality Score ≥ 90% cho trường bắt buộc",
    "Mọi row có (source_file, source_row, ingested_at)",
    "≥ 10 KPI views hoạt động với dữ liệu 2024-2025"
)

$Script:Epic003_TaskDescription = @"
Roles: @engineer, @audit
depends_on: [EPIC-001, EPIC-002]

### Tasks

- [ ] **TASK-3.1 — Ma trận đánh giá tuân thủ**
  Công thức đèn giao thông:
  GREEN  ← có Fact định lượng + có Document minh chứng + giá trị thực tế ≥ target
  YELLOW ← có Fact nhưng thiếu một trong: document gốc / số liệu thực tế / trong Audit Period
  RED    ← không có Fact hoặc giá trị < ngưỡng tối thiểu hoặc hoàn toàn trống dữ liệu

- [ ] **TASK-3.2 — Time Period Filter bắt buộc**
  - Default: ``01/03/2025 – 31/12/2025``.
  - Filter áp lên mọi view; data ngoài period hiển thị xám mờ + badge "Outside audit period".

- [ ] **TASK-3.3 — 5 Dashboard Views**
  1. **Overview** — Ma trận đèn giao thông 15 đơn vị × 10 năng lực.
  2. **Drill-down by Unit** — Chọn Cục XBI → xem tất cả Fact, Document, KPI của Cục.
  3. **Drill-down by Criteria (SAV)** — Chọn PL03 → xem ngân sách của toàn Bộ.
  4. **Timeline** — Trục thời gian: QĐ ban hành, CV phản hồi, báo cáo định kỳ.
  5. **Exception Report** — Danh sách file lỗi, đơn vị chưa nộp, Fact thiếu minh chứng.

- [ ] **TASK-3.4 — Click-to-Source drill-down**
  - Mọi data point → click mở PDF/Excel gốc tại chính xác ``page_number`` / ``source_row``.
  - Frontend: dùng PDF.js với anchor ``#page=N``; Excel hiển thị qua SheetJS với highlight row.

- [ ] **TASK-3.5 — Justification Form (Immutable)**
  - Trigger khi Kiểm toán viên click RED/YELLOW cell.
  - Lưu vào ``justifications`` table với ``user_id``, ``timestamp``, không cho UPDATE/DELETE (DB trigger enforce).
  - Hiển thị lịch sử justifications trong expandable panel.

- [ ] **TASK-3.6 — Export Engine (Config-driven)**
  - PDF: ReportLab + template YAML cho từng Phụ lục SAV.
  - Excel: openpyxl, giữ nguyên layout Phụ lục (merge cell, styling).
  - Diff tool: so sánh output với template SAV gốc → phải khớp 100%.

- [ ] **TASK-3.7 — RBAC**
  - ``Auditor``: view + thêm justification.
  - ``Reviewer``: view + approve/reject justification.
  - ``Admin``: full + quản lý user.

- [ ] **TASK-3.8 — End-to-End Test**
  - Input: thư mục mock ``/audit-docs-test/`` với 20 tệp.
  - Expected: Dashboard render đúng, export PDF khớp template, drill-down trỏ đúng file.

### Definition of Done
- [ ] 100% data point có drill-down đến source.
- [ ] Export PDF/Excel khớp 95% qua các file đã duyệt

### Acceptance Criteria
- [ ] Đảm bảo dữ liệu của các cục có tồn tại ít nhất 1 hoặc nhiều các báo cáo về năng lực
- [ ] Xác định được các dashboard về dữ liệu năng lực
"@

$Script:Epic003_DoD = @(
    "100% data point có drill-down đến source",
    "Export PDF/Excel khớp 95% qua các file đã duyệt"
)
$Script:Epic003_AC = @(
    "Đảm bảo dữ liệu của các cục có tồn tại ít nhất 1 hoặc nhiều các báo cáo về năng lực",
    "Xác định được các dashboard về dữ liệu năng lực"
)
