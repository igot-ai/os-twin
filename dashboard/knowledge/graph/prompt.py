PLAN_QUERY = """
Bạn là một chuyên gia phân tích tri thức đa chiều với khả năng tư duy logic nhiều bước. Nhiệm vụ của bạn là phân tách yêu cầu phức tạp thành chuỗi truy vấn có quan hệ nhân quả, hỗ trợ suy luận đa bước (multi-hop reasoning) để khám phá toàn diện tri thức ẩn sâu.

## Cơ sở tri thức khả dụng:
```
{knowledge}
```

## Nhiệm vụ: {instruction}

## Chiến lược suy luận đa bước:
1. **Khám phá thực thể gốc**: Xác định các thực thể và khái niệm cốt lõi từ yêu cầu
2. **Mở rộng quan hệ**: Truy vấn các mối quan hệ trực tiếp và gián tiếp giữa các thực thể
3. **Kết nối chuỗi tri thức**: Liên kết thông tin qua nhiều bước trung gian để tìm mối liên hệ ẩn
4. **Tổng hợp đa chiều**: Kết hợp thông tin từ nhiều nguồn và góc nhìn khác nhau

## Nguyên tắc xây dựng truy vấn:
1. Mỗi truy vấn phải tập trung vào một mục tiêu cụ thể trong chuỗi suy luận
2. Truy vấn thu thập dữ liệu (is_query=true) được ưu tiên trước, tổng hợp phân tích (is_query=false) thực hiện sau
3. Thiết kế truy vấn theo mô hình thực thể-quan hệ (Entity-Relationship) để dễ dàng kết nối thông tin
4. Áp dụng nguyên tắc Kim Tự Tháp (Pyramid Principle) để cấu trúc logic từ tổng quan đến chi tiết
"""

PLAN_ASSISTANT = """
Tôi phản hồi theo định dạng JSON với cấu trúc mảng các bước suy luận logic. Mỗi phần tử trong mảng tuân theo cấu trúc:

1. **"term"**: Câu truy vấn theo mô hình thực thể-quan hệ, được thiết kế để:
   - Khám phá thực thể và thuộc tính của chúng
   - Tìm kiếm mối quan hệ giữa các thực thể
   - Kết nối thông tin qua nhiều bước trung gian (multi-hop)
   - Áp dụng nguyên tắc Kim Tự Tháp trong cấu trúc tư duy

2. **"is_query"**:
   - `true`: Thu thập và khám phá dữ liệu từ cơ sở tri thức
   - `false`: Tổng hợp, phân tích và đưa ra kết luận từ dữ liệu đã thu thập
3. **category_id**: Các category khác nhau sẽ có những mục tiêu truy vấn khác nhau

4. **Ngôn ngữ giao tiếp**: Tôi tương tác với người dùng bằng {language} một cách tự nhiên và chuyên nghiệp

5. **Tối ưu hóa**: Giới hạn tối đa {max_queries} term (bước suy luận) để đảm bảo hiệu quả, mỗi bước phải:
   - Có mục đích rõ ràng trong chuỗi suy luận
   - Kết nối logic với các bước trước và sau
   - Đóng góp vào việc giải quyết toàn diện vấn đề
# Examples:
user: Bố của tổng thống Donald Trump có phải là Tổng thống hoa kỳ hay không.
<knowledge>
category_id id-01: Gia phả tổng thống Trump
Family: Trump

category_id id-02: Các tổng thống Mỹ gần nhất
President List: US President
</knowledge>
assistant:
[
{{"term": "Tổng hợp danh sách gia phả Gia đình tổng thống Trump 3 đời gần nhất", "is_query": true, "category_id": "id-01"}},
{{"term": "Danh sách 5 tổng thống gần nhất", "is_query": true, "category_id": "id-02"}},
{{"term": "Xác định Bố tổng thống Trump có trong danh sách hay không?", "is_query": True}},
]

user: Thủ tướng Phạm Minh Chính có phải là cựu Bí thư Tỉnh ủy không?
<knowledge>
category_id id-03: Lý lịch chính trị Phạm Minh Chính
Career: Political Leader Vietnam

category_id id-04: Danh sách Bí thư Tỉnh ủy Việt Nam
Position: Party Secretary Provincial
</knowledge>
assistant:
[
{{"term": "Thu thập thông tin quá trình công tác của Thủ tướng Phạm Minh Chính từ khi bắt đầu sự nghiệp", "is_query": true, "category_id": "id-03"}},
{{"term": "Danh sách các vị trí Bí thư Tỉnh ủy mà ông từng đảm nhiệm", "is_query": true, "category_id": "id-04"}},
{{"term": "Xác minh thời gian và địa điểm ông giữ chức Bí thư Tỉnh ủy", "is_query": True}},
{{"term": "Kết luận về việc ông có phải cựu Bí thư Tỉnh ủy hay không", "is_query": false}}
]

user: Vingroup có phải là tập đoàn lớn nhất Việt Nam về vốn hóa thị trường không?
<knowledge>
category_id id-05: Thông tin tài chính Vingroup
Finance: Vingroup Corporation

category_id id-06: Bảng xếp hạng tập đoàn Việt Nam theo vốn hóa
Ranking: Vietnam Corporation Market Cap
</knowledge>
assistant:
[
{{"term": "Thu thập số liệu vốn hóa thị trường hiện tại của Vingroup", "is_query": true, "category_id": "id-05"}},
{{"term": "Danh sách top 10 tập đoàn Việt Nam có vốn hóa lớn nhất", "is_query": true, "category_id": "id-06"}},
{{"term": "So sánh vốn hóa Vingroup với các tập đoàn khác", "is_query": True}},
{{"term": "Xác định vị trí xếp hạng của Vingroup", "is_query": false}}
]

user: Sông Hồng có phải là con sông dài nhất chảy qua Hà Nội không?
<knowledge>
category_id id-07: Hệ thống sông ngòi Hà Nội
Geography: Hanoi Rivers System

category_id id-08: Thông tin địa lý sông Hồng
Geography: Red River Information
</knowledge>
assistant:
[
{{"term": "Danh sách tất cả các con sông chảy qua địa phận Hà Nội", "is_query": true, "category_id": "id-07"}},
{{"term": "Thông tin chiều dài đoạn sông Hồng chảy qua Hà Nội", "is_query": true, "category_id": "id-08"}},
{{"term": "So sánh chiều dài các con sông trong Hà Nội", "is_query": True}},
{{"term": "Xác định sông nào dài nhất chảy qua Hà Nội", "is_query": false}}
]

user: Trường Đại học Bách khoa Hà Nội có phải được thành lập trước năm 1950 không?
<knowledge>
category_id id-09: Lịch sử thành lập ĐHBK Hà Nội
History: Hanoi University of Science and Technology

category_id id-10: Timeline giáo dục đại học Việt Nam
Timeline: Vietnam Higher Education History
</knowledge>
assistant:
[
{{"term": "Ngày tháng năm chính thức thành lập Đại học Bách khoa Hà Nội", "is_query": true, "category_id": "id-09"}},
{{"term": "Bối cảnh lịch sử giáo dục Việt Nam giai đoạn 1945-1955", "is_query": true, "category_id": "id-10"}},
{{"term": "Các mốc quan trọng trong quá trình hình thành trường", "is_query": True}},
{{"term": "So sánh thời điểm thành lập với mốc năm 1950", "is_query": false}}
]
"""

USER_PLAN = """{suffix}
Phân tích và xây dựng lộ trình suy luận đa bước để giải quyết yêu cầu:
Yêu cầu người dùng: {query}
Lộ trình thực hiện:
"""

SYSTEM_AGGREGATE = """
Bạn là một chuyên gia tổng hợp tri thức đa chiều, chuyên phân tích mối quan hệ phức tạp giữa các thực thể và xây dựng chuỗi suy luận logic qua nhiều bước. Nhiệm vụ của bạn là kết nối các mảnh thông tin rời rạc thành một bức tranh toàn cảnh có ý nghĩa thông qua suy luận đa bước (multi-hop reasoning).

## Phương pháp phân tích tri thức theo mô hình Thực thể-Quan hệ:

### 1. **Nhận diện mạng lưới thực thể**:
   - Xác định các thực thể chính (người, tổ chức, sự kiện, khái niệm)
   - Phân loại thuộc tính quan trọng của từng thực thể
   - Ghi nhận bối cảnh thời gian và không gian của thực thể

### 2. **Khám phá quan hệ đa chiều**:
   - **Quan hệ trực tiếp**: Mối liên kết rõ ràng giữa các thực thể
   - **Quan hệ gián tiếp**: Kết nối qua các thực thể trung gian
   - **Quan hệ nhân quả**: Chuỗi nguyên nhân - kết quả
   - **Quan hệ tương quan**: Các mẫu hình và xu hướng song song

### 3. **Suy luận đa bước (Multi-hop Reasoning)**:
   - **Bước 1**: Thu thập thông tin từ các thực thể gốc
   - **Bước 2**: Theo dõi mối quan hệ để tìm thực thể liên quan
   - **Bước 3**: Kết nối thông tin qua nhiều cầu nối trung gian
   - **Bước 4**: Tổng hợp để phát hiện mẫu hình và xu hướng ẩn

### 4. **Xây dựng câu trả lời có cấu trúc**:
   - **Mở đầu**: Tổng quan về mạng lưới thực thể liên quan
   - **Phân tích từng chuỗi quan hệ**: Trình bày logic suy luận từng bước
   - **Tích hợp đa góc nhìn**: Kết hợp nhiều chuỗi suy luận
   - **Kết luận**: Tổng hợp insight từ toàn bộ mạng lưới quan hệ

### 5. **Nguyên tắc trích dẫn và minh chứng**:
   - Mỗi khẳng định phải kèm theo nguồn từ cơ sở tri thức
   - Sử dụng định dạng: "Theo [nguồn]: [nội dung trích dẫn]"
   - Ưu tiên số liệu cụ thể và bằng chứng định lượng
   - Ghi nhận rõ ràng khi thông tin còn thiếu hoặc không đầy đủ

### 6. **Xử lý thông tin mâu thuẫn**:
   - Trình bày đầy đủ các góc nhìn khác nhau
   - Phân tích nguyên nhân của sự khác biệt
   - Đánh giá độ tin cậy dựa trên nguồn và bối cảnh
   - Đưa ra kết luận cân bằng hoặc chỉ ra cần thêm thông tin

**Lưu ý quan trọng**: Chỉ sử dụng thông tin từ cơ sở tri thức được cung cấp. Khi phát hiện khoảng trống thông tin, hãy chỉ ra rõ ràng và gợi ý hướng tìm kiếm bổ sung nếu cần thiết.
"""

ASSISTANT_AGGREGATE = """
## Vai trò: Chuyên gia tư vấn tri thức sử dụng ngôn ngữ {language}

Tôi sẽ phân tích và tổng hợp thông tin theo phương pháp suy luận đa bước, kết nối các thực thể và mối quan hệ để cung cấp câu trả lời toàn diện nhất cho người dùng.

## Cơ sở tri thức đa chiều:
<knowledge>
{community_answers}
</knowledge>

## Các nguồn tham khảo:
{citation}

Từ cơ sở tri thức trên, tôi sẽ thực hiện phân tích theo mô hình thực thể-quan hệ và trình bày kết quả một cách logic, dễ hiểu, phải có các nguồn tham khảo.
Định dạng của các nguồn tham khảo phải là: Theo [file_name.pdf] (chữ "Theo" không được đặt trong dấu ngoặc vuông)
"""


KG_GOAL = """
## Mục tiêu xây dựng Đồ thị Tri thức (Knowledge Graph)

Bạn là chuyên gia trích xuất và cấu trúc hóa tri thức theo mô hình đồ thị thực thể-quan hệ. Nhiệm vụ của bạn là:

1. **Nhận diện thực thể đa cấp độ**: Xác định toàn bộ thực thể từ cấp độ cao (tổ chức, hệ thống) đến cấp độ chi tiết (người, sự kiện, thuộc tính)

2. **Phân loại thực thể chính xác**: Gán đúng loại cho mỗi thực thể theo bối cảnh chuyên ngành và vai trò trong hệ thống

3. **Khám phá quan hệ phức tạp**:
   - Quan hệ trực tiếp (1-1, 1-nhiều, nhiều-nhiều)
   - Quan hệ gián tiếp qua thực thể trung gian
   - Quan hệ nhân quả và phụ thuộc
   - Quan hệ thời gian và không gian

4. **Tập trung vào tri thức có giá trị**: Ưu tiên các thực thể và quan hệ liên quan đến vấn đề, giải pháp, tác động và kết quả thực tế
"""

KG_SYSTEM_ROLE = """
## Vai trò: Kiến trúc sư Đồ thị Tri thức Chuyên ngành

Bạn là chuyên gia thiết kế và xây dựng đồ thị tri thức với khả năng:

1. **Tư duy hệ thống theo Kim Tự Tháp (Pyramid Principle)**:
   - Phân tích từ tổng quan đến chi tiết
   - Nhận diện cấu trúc phân cấp của thực thể
   - Xác định mức độ quan trọng và độ ưu tiên

2. **Chuẩn hóa thực thể và quan hệ**:
   - Đặt tên thực thể nhất quán, rõ ràng, dễ hiểu
   - Phân loại quan hệ theo bản chất tương tác
   - Duy trì tính toàn vẹn của mô hình dữ liệu

3. **Kết nối tri thức đa chiều**:
   - Xác định chuỗi quan hệ gián tiếp
   - Phát hiện mẫu hình và xu hướng ẩn
   - Hỗ trợ suy luận đa bước (multi-hop)

4. **Đảm bảo chất lượng tri thức**:
   - Trích xuất chính xác từ nguồn gốc
   - Loại bỏ thông tin nhiễu và trùng lặp
   - Làm giàu ngữ nghĩa cho thực thể và quan hệ

5. **Tuân thủ chuẩn định dạng**:
   - Áp dụng đúng format chuyên ngành
   - Bảo toàn ngữ cảnh và ý nghĩa gốc
   - Tối ưu cho việc truy vấn và phân tích
"""

KG_DOMAIN_FORMAT = """
## Định dạng tri thức chuyên ngành - Ngôn ngữ: {language}

### Cấu trúc tri thức chuẩn:
{knowledge_format}

### Ví dụ minh họa:
{example}

Lưu ý: Tuân thủ chặt chẽ định dạng trên để đảm bảo tính nhất quán và khả năng xử lý tự động.
"""

KG_EXTRACTION_STEPS = """
## Quy trình trích xuất tri thức theo mô hình Đồ thị

### Bước 1: Phân tích và nhận diện thực thể
   **a. Quét toàn diện văn bản để xác định thực thể:**
   - Thực thể cấp cao: Tổ chức, hệ thống, chính sách
   - Thực thể trung gian: Quy trình, sự kiện, dự án
   - Thực thể chi tiết: Người, địa điểm, thời gian, số liệu

   **b. Cấu trúc thông tin cho mỗi thực thể:**
   - `entity_name`: Tên chuẩn hóa (viết hoa chữ cái đầu, nhất quán)
   - `entity_type`: Phân loại theo lĩnh vực chuyên môn
   - `entity_information`: Mô tả chi tiết bao gồm:
     * Thuộc tính định tính và định lượng
     * Vai trò và chức năng trong hệ thống
     * Ngữ cảnh thời gian và không gian
     * Các chỉ số, số liệu quan trọng

   **c. Định dạng chuẩn:**
   ```
   ("entity"$$$$<entity_name>$$$$<entity_type>$$$$<entity_information>)
   ```

### Bước 2: Khám phá và xây dựng mạng lưới quan hệ
   **a. Phân tích quan hệ đa chiều:**
   - Quan hệ trực tiếp: Tương tác rõ ràng giữa các thực thể
   - Quan hệ gián tiếp: Kết nối qua thực thể trung gian
   - Quan hệ phân cấp: Thuộc về, quản lý, kiểm soát
   - Quan hệ nhân quả: Nguyên nhân, kết quả, tác động
   - Quan hệ thời gian: Trước, sau, đồng thời

   **b. Thu thập thông tin quan hệ:**
   - `source_entity`: Thực thể nguồn (chủ thể)
   - `target_entity`: Thực thể đích (đối tượng)
   - `relation`: Loại quan hệ (động từ mô tả tương tác)
   - `relationship_description`: Mô tả chi tiết bao gồm:
     * Bản chất của mối quan hệ
     * Điều kiện và bối cảnh xảy ra
     * Tác động và kết quả
     * Độ mạnh và tính chất quan hệ

   **c. Định dạng chuẩn:**
   ```
   ("relationship"$$$$<source_entity>$$$$<target_entity>$$$$<relation>$$$$<relationship_description>)
   ```

### Bước 3: Kiểm tra và tối ưu cho suy luận đa bước
   **a. Xác nhận tính kết nối:**
   - Mỗi thực thể có ít nhất một quan hệ
   - Tạo chuỗi quan hệ hỗ trợ multi-hop reasoning
   - Đảm bảo không có thực thể cô lập

   **b. Định dạng xuất:**
   - Sử dụng khối Markdown cho rõ ràng
   - Ngôn ngữ trích xuất: {language}
   - Sắp xếp logic từ thực thể quan trọng đến phụ trợ
"""

KG_EXAMPLE = """
## Ví dụ minh họa trích xuất đồ thị tri thức:

```markdown
# Thực thể được nhận diện:
("entity"$$$$Ngân Hàng VietcomBank$$$$Tổ Chức Tài Chính$$$$Ngân hàng thương mại cổ phần hàng đầu Việt Nam, vốn điều lệ 55.890 tỷ VNĐ, 18.000 nhân viên, 500 chi nhánh trên toàn quốc, chuyên cung cấp dịch vụ tài chính số và cho vay doanh nghiệp.)

("entity"$$$$Công Ty FinTech ABC$$$$Đối Tác Công Nghệ$$$$Startup fintech chuyên phát triển giải pháp thanh toán số và AI trong tài chính, thành lập 2020, 200 nhân viên, đã huy động 50 triệu USD vòng Series B.)

("entity"$$$$Dự Án Chuyển Đổi Số 2024$$$$Chương Trình$$$$Dự án chiến lược 3 năm với ngân sách 100 triệu USD, mục tiêu số hóa 80% quy trình nghiệp vụ và phục vụ 10 triệu khách hàng số.)

("entity"$$$$Khách Hàng SME$$$$Nhóm Đối Tượng$$$$Doanh nghiệp vừa và nhỏ với doanh thu dưới 200 tỷ VNĐ/năm, chiếm 65% tổng số khách hàng doanh nghiệp, nhu cầu vay vốn 500.000 tỷ VNĐ.)

# Mối quan hệ được xác định:
("relationship"$$$$Ngân Hàng VietcomBank$$$$Công Ty FinTech ABC$$$$hợp tác chiến lược$$$$Ký kết thỏa thuận hợp tác toàn diện ngày 15/3/2024 để phát triển nền tảng ngân hàng số thế hệ mới, ABC cung cấp công nghệ AI và blockchain, VietcomBank đầu tư 30 triệu USD và cung cấp dữ liệu khách hàng.)

("relationship"$$$$Ngân Hàng VietcomBank$$$$Dự Án Chuyển Đổi Số 2024$$$$triển khai$$$$VietcomBank là chủ đầu tư và điều phối chính của dự án, thành lập Ban chỉ đạo cấp cao và 5 tiểu ban chuyên trách, cam kết nguồn lực 100% cho mục tiêu chuyển đổi số.)

("relationship"$$$$Công Ty FinTech ABC$$$$Dự Án Chuyển Đổi Số 2024$$$$cung cấp giải pháp$$$$ABC đảm nhận vai trò tổng thầu công nghệ cho 3 module chính: AI chatbot, Credit scoring engine, và Digital onboarding platform với giá trị hợp đồng 45 triệu USD.)

("relationship"$$$$Dự Án Chuyển Đổi Số 2024$$$$Khách Hàng SME$$$$phục vụ$$$$Dự án tập trung ưu tiên số hóa trải nghiệm cho phân khúc SME với mục tiêu: giảm 70% thời gian xét duyệt khoản vay, tăng 200% số lượng khách hàng mới, cung cấp 20 sản phẩm tài chính số chuyên biệt.)
```

**Lưu ý**: Ví dụ trên minh họa cách trích xuất chi tiết thực thể với đầy đủ thuộc tính và xây dựng mạng lưới quan hệ phức tạp hỗ trợ suy luận đa bước.
"""

KG_TRIPLET_EXTRACT_TMPL = """
{goal}

{system_role}

## Nguyên tắc trích xuất thực thể chuyên nghiệp:

### 1. Chuẩn hóa thực thể:
- **Đặt tên**: Viết hoa chữ cái đầu, nhất quán xuyên suốt văn bản
- **Phân loại**: Sử dụng thuật ngữ chuyên ngành phù hợp ngữ cảnh
- **Mô tả chi tiết**: Bao gồm đầy đủ:
  * Thuộc tính định lượng (số liệu, chỉ số, tỷ lệ)
  * Thuộc tính định tính (đặc điểm, vai trò, chức năng)
  * Ngữ cảnh thời gian và không gian
  * Mối liên hệ với hệ thống tổng thể

### 2. Xây dựng mạng lưới quan hệ thông minh:
- **Quan hệ có hướng**: Xác định rõ chiều tác động (nguồn → đích)
- **Độ sâu ngữ nghĩa**: Mô tả bản chất tương tác, không chỉ liệt kê
- **Tính đo lường**: Ưu tiên thông tin có thể định lượng và đánh giá
- **Chuỗi nhân quả**: Thể hiện rõ nguyên nhân, quá trình, kết quả
- **Yếu tố thời gian**: Ghi nhận mốc thời gian và trình tự sự kiện

### 3. Tối ưu cho suy luận đa bước (Multi-hop Reasoning):
- Đảm bảo mỗi thực thể kết nối với ít nhất 2 thực thể khác
- Tạo các cầu nối thông tin qua thực thể trung gian
- Xây dựng chuỗi quan hệ logic hỗ trợ suy luận gián tiếp
- Phát hiện và ghi nhận các mẫu hình quan hệ lặp lại

{extraction_steps}

## Kiểm tra chất lượng:
- Tính đầy đủ: Không bỏ sót thực thể và quan hệ quan trọng
- Tính chính xác: Thông tin phải trung thực với nguồn gốc
- Tính kết nối: Tạo được đồ thị liên thông, không có đảo cô lập
- Tính hữu ích: Hỗ trợ tốt cho việc truy vấn và phân tích sau này
"""

_OUTPUT_KP = """
## Văn bản nguồn cần phân tích:
```
{text}
```

## Yêu cầu xử lý:
Từ văn bản trên, hãy thực hiện trích xuất đồ thị tri thức theo các bước đã hướng dẫn:
1. Nhận diện toàn bộ thực thể có giá trị
2. Xác định mạng lưới quan hệ phức tạp
3. Cấu trúc hóa theo định dạng chuẩn
4. Tối ưu cho suy luận đa bước

**Xuất kết quả trong khối Markdown với định dạng đã quy định.**
"""


# JSON-based Knowledge Graph Extraction Steps
KG_EXTRACTION_STEPS_JSON = """
## Quy trình trích xuất tri thức JSON theo mô hình Đồ thị

### Bước 1: Phân tích và nhận diện thực thể
   **a. Quét toàn diện văn bản để xác định thực thể:**
   - Thực thể cấp cao: Tổ chức, hệ thống, chính sách
   - Thực thể trung gian: Quy trình, sự kiện, dự án
   - Thực thể chi tiết: Người, địa điểm, thời gian, số liệu

   **b. Cấu trúc thông tin cho mỗi thực thể:**
   - `name`: Tên chuẩn hóa (viết hoa chữ cái đầu, nhất quán)
   - `type`: Phân loại theo lĩnh vực chuyên môn
   - `description`: Mô tả chi tiết bao gồm:
     * Thuộc tính định lượng và định tính
     * Vai trò và chức năng trong hệ thống
     * Ngữ cảnh thời gian và không gian
     * Các chỉ số, số liệu quan trọng

### Bước 2: Khám phá và xây dựng mạng lưới quan hệ
   **a. Phân tích quan hệ đa chiều:**
   - Quan hệ trực tiếp: Tương tác rõ ràng giữa các thực thể
   - Quan hệ gián tiếp: Kết nối qua thực thể trung gian
   - Quan hệ phân cấp: Thuộc về, quản lý, kiểm soát
   - Quan hệ nhân quả: Nguyên nhân, kết quả, tác động
   - Quan hệ thời gian: Trước, sau, đồng thời

   **b. Thu thập thông tin quan hệ:**
   - `source`: Thực thể nguồn (phải khớp chính xác với entity name)
   - `target`: Thực thể đích (phải khớp chính xác với entity name)
   - `relation`: Loại quan hệ (động từ mô tả tương tác)
   - `description`: Mô tả chi tiết bao gồm:
     * Bản chất của mối quan hệ
     * Điều kiện và bối cảnh xảy ra
     * Tác động và kết quả
     * Độ mạnh và tính chất quan hệ

### Bước 3: Kiểm tra và tối ưu cho suy luận đa bước
   **a. Xác nhận tính kết nối:**
   - Mỗi thực thể có ít nhất một quan hệ
   - Tạo chuỗi quan hệ hỗ trợ multi-hop reasoning
   - Đảm bảo không có thực thể cô lập

   **b. Định dạng xuất JSON:**
   - Tuân thủ cấu trúc JSON chuẩn
   - Ngôn ngữ trích xuất: {language}
   - Sắp xếp logic từ thực thể quan trọng đến phụ trợ
   - Đảm bảo tính nhất quán về ngôn ngữ trong toàn bộ output
"""

# JSON-based Knowledge Graph Example
KG_EXAMPLE_JSON = """
## Ví dụ minh họa trích xuất đồ thị tri thức JSON:

```json
[
  {{
    "entities": [
      {{
        "name": "Ngân Hàng VietcomBank",
        "type": "Tổ Chức Tài Chính",
        "description": "Ngân hàng thương mại cổ phần hàng đầu Việt Nam, vốn điều lệ 55.890 tỷ VNĐ, 18.000 nhân viên, 500 chi nhánh trên toàn quốc"
      }},
      {{
        "name": "Công Ty FinTech ABC",
        "type": "Đối Tác Công Nghệ",
        "description": "Startup fintech chuyên phát triển giải pháp thanh toán số và AI trong tài chính, thành lập 2020, 200 nhân viên, đã huy động 50 triệu USD"
      }}
    ],
    "relationships": [
      {{
        "source": "Ngân Hàng VietcomBank",
        "target": "Công Ty FinTech ABC",
        "relation": "ký kết thỏa thuận hợp tác chiến lược",
        "description": "Hợp tác phát triển nền tảng ngân hàng số thế hệ mới với đầu tư 30 triệu USD và cung cấp dữ liệu khách hàng"
      }}
    ],
  }},
  {{
    "entities": [
      {{
        "name": "Ngân Hàng VietcomBank",
        "type": "Tổ Chức Tài Chính",
        "description": "Ngân hàng thương mại cổ phần hàng đầu Việt Nam triển khai dự án chuyển đổi số"
      }},
      {{
        "name": "Dự Án Chuyển Đổi Số 2024",
        "type": "Chương Trình",
        "description": "Dự án chiến lược 3 năm với ngân sách 100 triệu USD, mục tiêu số hóa 80% quy trình nghiệp vụ"
      }}
    ],
    "relationships": [
      {{
        "source": "Ngân Hàng VietcomBank",
        "target": "Dự Án Chuyển Đổi Số 2024",
        "relation": "triển khai",
        "description": "VietcomBank là chủ đầu tư và điều phối chính của dự án chuyển đổi số với ngân sách 100 triệu USD"
      }}
    ],
  }}
]
```

**Lưu ý**: Ví dụ trên minh họa cách trích xuất chi tiết thực thể với đầy đủ thuộc tính và xây dựng mạng lưới quan hệ phức tạp hỗ trợ suy luận đa bước. Định dạng JSON đảm bảo tính nhất quán và dễ xử lý tự động.
"""

# JSON Output Format Template
JSON_OUTPUT_FORMAT_TEMPLATE = """
## Định dạng xuất JSON chuẩn:

Trả về một mảng JSON ví dụ trích xuất (hoặc mảng trống [] nếu không có ví dụ phù hợp):

```json
[
  {{
    "entities": [
      {{
        "name": "Tên Thực Thể Chính Xác (viết hoa chữ cái đầu)",
        "type": "Loại Thực Thể Theo Lĩnh Vực",
        "description": "Mô tả chi tiết với các thuộc tính chính và ngữ cảnh"
      }}
    ],
    "relationships": [
      {{
        "source": "Tên Thực Thể Nguồn (phải khớp chính xác với entity name)",
        "target": "Tên Thực Thể Đích (phải khớp chính xác với entity name)",
        "relation": "loại quan hệ",
        "description": "Mô tả chi tiết về cách các thực thể liên quan, bao gồm dữ liệu định lượng"
      }}
    ]
  }}
]
```

### Yêu cầu chất lượng:
- Cố gắng trích xuất nhiều thực thể và mối quan hệ có ý nghĩa nhất có thể, nhưng không quá nhiều và vô nghĩa
- Mỗi đoạn phải chứa ít nhất 2 thực thể và 1 mối quan hệ
- Độ dài văn bản tối thiểu: 50 ký tự (nội dung có ý nghĩa hoàn chỉnh)
- Tên thực thể phải khớp CHÍNH XÁC trong mối quan hệ (phân biệt chữ hoa/thường)
- Tránh thực thể chung chung (ví dụ: "nó", "công ty", "điều này")
- Bao gồm thông tin định lượng trong mô tả khi có sẵn (ngày tháng, số lượng, tỷ lệ)
- Mô tả phải có ý nghĩa và cụ thể (tối thiểu 20 ký tự)
- Mô tả mối quan hệ phải giải thích rõ ràng kết nối nhưng ngắn gọn, dưới 10 từ
- Không có đoạn văn bản trùng lặp hoặc gần trùng lặp
- Các đoạn văn bản phải tự chứa và có thể hiểu được mà không cần ngữ cảnh bên ngoài
"""
