# Member Role Report - Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung          |
| --------------- | ------------------ |
| Họ và tên       | Sùng A Khua        |
| MSSV            | 2A202601129        |
| Khóa/Lớp        | K3                 |
| Vai trò chính   | Delivery Agent      |
| Ngày hoàn thành | 2026-08-05         |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------- | -------------------- | ---------------- | ------------------ | ----------- |
| Delivery Agent (LLM-formatting layer) | `src/delivery.py` - class `DeliveryAgent`, hàm `investigate()` | `case_id: str`, `claimed_order_id: str` | `DeliveryFacts` (Pydantic model, structured output) | Một phần - phụ thuộc `DataGateway.get_delivery_facts()` và `get_llm()` |

Tôi chỉ nhận ownership cho `src/delivery.py`. File này gọi sang `src/data/gateway.py` (`DataGateway.get_delivery_facts`) để lấy fact thô từ CSV, và `src/schemas/handoff.py` (`DeliveryFacts`) để định nghĩa contract đầu ra

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ---------- | -------------------------------- | -------- |
| Đọc chéo `policy/ec_policy_v1.py` để xác nhận `PolicyEngine.evaluate()` tiêu thụ đúng field `is_delivered_late`, `delivery_classification`, `late_handoff_seller_ids` từ `DeliveryFacts` | Policy Agent | Xác nhận contract field-name khớp giữa hai phía handoff, chưa phát hiện lệch tên field |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| ------------------------ | ------------------------------ | ------------------- | --------------- |
| Viết `DeliveryAgent.investigate()`: gọi `DataGateway.get_delivery_facts()` lấy fact thô, đưa qua LLM chain để ép về schema `DeliveryFacts` | `src/delivery.py:18-25` | Object `DeliveryFacts`  |  |
| Cấu hình retry cho lệnh gọi LLM bằng decorator có sẵn `retry_with_backoff` | `src/delivery.py:6,18`, dựa trên `src/retry_utils.py` | Hành vi retry tối đa 10 lần, delay khởi điểm 30s khi gặp lỗi rate-limit | |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`DeliveryAgent.investigate(case_id, claimed_order_id)` trả về một instance `DeliveryFacts` gồm `delivered_customer_date`, `estimated_delivery_date`, `delivered_carrier_date`, `is_delivered_late`, `late_handoff_item_ids`, `late_handoff_seller_ids`, `delivery_classification`. 

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Delivery Agent phải trả lời câu hỏi: đơn hàng có giao trễ so với cam kết không, và nếu trễ thì trách nhiệm nghiêng về seller (bàn giao trễ cho carrier) hay logistics (carrier nhận đúng hạn nhưng giao khách trễ)? Đây là input bắt buộc để `PolicyEngine` phân biệt hai nhánh `late_delivery_seller` và `late_delivery_logistics` theo đúng thứ tự ưu tiên trong bảng rule EC_POLICY_V1.

### Cách triển khai

`DeliveryAgent.__init__` dựng 3 thành phần: `DataGateway()` (singleton đọc CSV), `get_llm()` (client Gemini qua `langchain_google_genai`), và một `ChatPromptTemplate` 2 message (system + user) nối với `llm.with_structured_output(DeliveryFacts)` để ép output LLM tuân theo đúng Pydantic schema thay vì text tự do.


### Input, output và contract

| Thành phần | Mô tả |
| ------------ | ------- |
| Input | `case_id: str`, `claimed_order_id: str` (tham số hàm `investigate`) |
| Output | `DeliveryFacts` — Pydantic model gồm `delivered_customer_date`, `estimated_delivery_date`, `delivered_carrier_date`, `is_delivered_late: bool`, `late_handoff_item_ids: list[str]`, `late_handoff_seller_ids: list[str]`, `delivery_classification: str` (giá trị `"seller_handoff_late"` / `"logistics_late"` / `""`) |
| Module phụ thuộc | `src/data/gateway.py` (`DataGateway.get_delivery_facts`), `src/schemas/handoff.py` (`DeliveryFacts`), `src/llm_client.py` (`get_llm`), `src/retry_utils.py` (`retry_with_backoff`) |
| Module sử dụng output | `src/policy/ec_policy_v1.py` — `PolicyEngine.evaluate()` đọc trực tiếp `delivery.is_delivered_late`, `delivery.delivery_classification`, `delivery.late_handoff_seller_ids` để chọn giữa `late_delivery_seller` và `late_delivery_logistics` (Priority 3 và 4 trong bảng rule); được gọi bởi agent điều phối (`src/agents/coordinator.py` |
| Điều kiện lỗi cần xử lý | (1) `claimed_order_id` không tồn tại trong `orders_by_id` → `gateway.py` raise `ValueError` trước khi tới được `DeliveryAgent`, tôi chưa thêm try/except riêng ở `delivery.py` nên lỗi này sẽ propagate nguyên văn; (2) LLM trả về output không ép được vào schema `DeliveryFacts` → phụ thuộc hành vi retry/raise mặc định của `with_structured_output` |

### Cách xác minh

```bash
python -c "from src.delivery import DeliveryAgent; a = DeliveryAgent()"
```

- **Kết quả mong đợi:** Khởi tạo `DeliveryAgent` thành công, không lỗi import.
- **Kết quả thực tế:** 
- **Artifact/log:** 

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định phần "xác định late/on-time và seller nào bàn giao trễ" nên nằm ở code thuần hay để LLM tự suy luận trực tiếp từ timestamp thô.
- **Các phương án đã cân nhắc:**
  1. Để `DeliveryAgent` nhận timestamp thô từ CSV rồi yêu cầu LLM tự so sánh ngày và tự phân loại `seller_handoff_late` / `logistics_late`.
  2. Để code thuần (`DataGateway.get_delivery_facts`, ngoài phạm vi sở hữu của tôi nhưng là input trực tiếp) tính toán quyết định trước, `DeliveryAgent` chỉ dùng LLM để format lại đúng schema, với system prompt cấm sửa ngày/classification.
- **Phương án đã chọn:** Phương án 2 — đã được hiện thực trong `src/delivery.py` mà tôi kế thừa và triển khai phần agent.
- **Lý do:** README của lab yêu cầu mỗi agent chỉ dùng model ≤10B parameter và cảnh báo rõ hệ thống phải ưu tiên dữ liệu có thể kiểm chứng, không tự tạo ra sự kiện không tồn tại. So sánh ngày tháng và phân loại seller/logistics là phép toán xác định (deterministic), để LLM tự làm sẽ tạo rủi ro sai lệch không kiểm soát được trên đúng field quyết định `primary_issue`. Giữ phép tính ở code thuần và chỉ dùng LLM cho việc "format/validate schema" giảm rủi ro hallucination xuống gần nhất có thể.
- **Bằng chứng quyết định phù hợp:**

## 6. Một lỗi hoặc blocker đã xử lý

Chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** 
- **Những gì đã loại trừ:** Đã xác nhận `src/delivery.py`, `src/data/gateway.py`, `src/schemas/handoff.py`, `src/llm_client.py`, `src/retry_utils.py` đều tồn tại và không có lỗi cú pháp khi đọc; đã loại trừ khả năng lỗi nằm ở phía các file tôi phụ trách trực tiếp bằng cách đọc lại toàn bộ import chain.
- **Bước tiếp theo:** 
## 7. Hiểu biết về luồng end-to-end

`input/EC_xxx.json` (có `claimed_order_id`) → `DataGateway` tra CSV Olist (orders/items/payments/sellers) → các agent domain (Order & Seller, Payment, Delivery) đóng gói thành `*Facts` và format qua LLM theo schema cố định → `PolicyEngine.evaluate()` áp bảng rule EC_POLICY_V1 theo đúng thứ tự ưu tiên → Verifier kiểm evidence/số tiền/giới hạn → ghi `output/EC_xxx.json`. 

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Sùng A Khua
**Ngày xác nhận:** 2026-08-05
