# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | NGUYỄN MẠNH HƯNG |
| MSSV            | 2A202601829 |
| Khóa/Lớp        | K3 |
| Vai trò chính   | Coordinator Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Khởi tạo các agent chuyên trách | `src/agents/coordinator.py:9-15`, `CoordinatorAgent.__init__` | Không có tham số ngoài | Instance của Order/Seller, Payment, Delivery, Policy và Verifier Agent | Một phần |
| Điều phối xử lý một case | `src/agents/coordinator.py:17-44`, `CoordinatorAgent.process_case` | `InputCase`, đặc biệt `case_id` và `customer_request.claimed_order_id` | `canonical_json` và `VerifierReceipt` đã được verifier duyệt | Một phần |

Coordinator chỉ chuyển tiếp facts giữa các agent; tổng tiền item/freight từ Order & Seller Agent được truyền sang Payment Agent để đối soát. Kết quả từ ba bước điều tra được đưa vào Policy Agent, sau đó candidate được chuyển sang Verifier Agent. Các agent chuyên trách được import trong coordinator nhưng hiện chưa có file tương ứng trong working tree, nên phần tích hợp chưa thể xác nhận runtime.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thiết kế và chạy 1 luồn riêng biệt toàn bộ repo để so sánh kết quả | Ca nhan | Không ghi nhận để tránh nhận ownership không thực hiện |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Khai báo topology và thứ tự handoff của coordinator | `src/agents/coordinator.py:10-15, 24-39` | Luồng Order/Seller → Payment → Delivery → Policy → Verifier | `nl -ba src/agents/coordinator.py` |
| Chuyển totals sang Payment Agent trước khi reconciliation | `src/agents/coordinator.py:27-30` | `item_total` và `freight_total` được chuyển dưới dạng `float` | Đọc code và kiểm tra compile |
| Chặn candidate không qua verification | `src/agents/coordinator.py:39-44` | Ném `ValueError` khi `receipt.approved == False`; trả JSON canonical khi pass | Đọc code; nhánh reject chưa chạy được trong môi trường hiện tại |

Output cụ thể mà coordinator được thiết kế để tạo là một tuple `(canonical_json, receipt)`. Runner sẽ dùng `canonical_json` để ghi file tương ứng trong `output/` và dùng receipt để xác nhận kết quả. Repo hiện có 50 file trong `output/`, nhưng do coordinator hiện không import được và trace/metadata không nhất quán, chưa đủ bằng chứng để quy các output đó cho lượt chạy hiện tại của phần này.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Coordinator là điểm điều phối một case khiếu nại: nhận input đã parse, lấy đúng `claimed_order_id`, yêu cầu các domain agent thu thập facts, chờ đủ facts để áp policy, rồi chuyển candidate cho verifier trước khi trả kết quả. Nó giúp tách điều tra order/seller, payment, delivery, policy và verification thành các bước có contract riêng.

### Cách triển khai

`process_case` lấy `case_id` và order ID từ `InputCase`, chờ 1 giây để giảm rủi ro rate limit, rồi thực hiện các handoff theo thứ tự. Order & Seller Agent chạy trước để có `item_total_brl` và `freight_total_brl`. Hai giá trị này được đổi sang `float` và truyền cho Payment Agent cùng case/order ID nhằm tính reconciliation với payment. Delivery Agent tiếp tục lấy facts về mốc giao hàng. Khi đã có đủ ba nhóm facts, Policy Agent tạo candidate theo `EC_POLICY_V1`. Verifier trả về `VerifierReceipt` và JSON canonical; coordinator chỉ trả kết quả khi receipt được approved.

Trong code hiện tại, các bước được gọi tuần tự bằng method call trực tiếp. Chưa có việc tạo `A2AEnvelope`, fan-out song song, trace span riêng cho từng agent hoặc repair route như mô tả trong `architecture.md`; đây là khoảng cách tích hợp cần được hoàn thiện trước khi kết luận pipeline đạt đầy đủ kiến trúc mục tiêu.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `InputCase` từ `src/schemas/input.py`; coordinator dùng `case.case_id` và `case.customer_request.claimed_order_id`. |
| Output | Tuple `(canonical_json: str, receipt: VerifierReceipt)` theo contract mà `VerifierAgent.verify` được gọi để trả về. |
| Module phụ thuộc | `src/schemas/input.py`; `src.agents.order_seller`, `payment`, `delivery`, `policy`, `verifier`. |
| Module sử dụng output | `src/runner.py` ghi `canonical_json` vào `output/<case_id>.json`; receipt được dùng để quyết định thành công/thất bại trong coordinator. |
| Điều kiện lỗi cần xử lý | Order không tồn tại, specialist investigation lỗi, policy không match rule, rate limit/API lỗi, candidate không qua verifier hoặc import/dependency bị thiếu. |

### Cách xác minh

```bash
python3 -m py_compile src/agents/coordinator.py
python3 -c 'from src.agents.coordinator import CoordinatorAgent; print(CoordinatorAgent)'
```

- **Kết quả mong đợi:** File compile được và import được `CoordinatorAgent` để có thể chạy runner.
- **Kết quả thực tế:** Compile thành công. Import thất bại với `ModuleNotFoundError: No module named 'pydantic'`; ngoài ra working tree chưa có năm file agent được coordinator import.
- **Artifact/log:** `src/agents/coordinator.py`, `logging/metadata.json`, `logging/trace.jsonl`. Không ghi secret vào báo cáo.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Payment Agent cần `item_total` và `freight_total` để tính tổng kỳ vọng trước khi xác định payment có reconcile hay không.
- **Các phương án đã cân nhắc:** (1) gọi Payment Agent sau Order & Seller Agent và truyền hai totals; (2) fan-out Payment Agent cùng lúc với các specialist khác, sau đó để Payment Agent tự đọc/aggregate dữ liệu nguồn.
- **Phương án đã chọn:** Gọi Order & Seller trước, lấy totals từ fact contract, rồi truyền chúng vào `payment.investigate`.
- **Lý do:** Giảm việc Payment Agent phải đọc thêm dữ liệu ngoài domain, giữ một nguồn tính totals và làm rõ dependency của reconciliation. Trade-off là thời gian xử lý dài hơn và chưa đạt fan-out song song như kiến trúc mục tiêu.
- **Bằng chứng quyết định phù hợp:** `src/agents/coordinator.py:24-30` thể hiện thứ tự gọi và hai tham số totals được truyền sang Payment Agent.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ModuleNotFoundError: No module named 'pydantic'` khi chạy import coordinator.
- **Lệnh hoặc bước tái hiện:** `python3 -c 'from src.agents.coordinator import CoordinatorAgent; print(CoordinatorAgent)'`.
- **Nguyên nhân gốc:** Môi trường hiện tại chưa cài các dependency trong `requirements.txt`. Kiểm tra cây source cũng cho thấy các module `order_seller.py`, `payment.py`, `delivery.py`, `policy.py` và `verifier.py` mà coordinator import chưa tồn tại trong working tree.
- **Cách xử lý:** Đã xác định và ghi nhận blocker; chưa tự ý cài dependency hoặc tạo thay thế cho phần việc của thành viên khác.
- **Cách xác minh sau khi sửa:** Cài dependency đúng môi trường, bổ sung/merge đủ năm agent còn thiếu, sau đó chạy import và `python3 src/runner.py`; kiểm tra đủ 50 output và cùng `run_id` trong trace/metadata.
- **Điều học được:** Compile chỉ kiểm tra syntax, không chứng minh module import được hoặc pipeline chạy end-to-end. Trạng thái artifact phải đối chiếu thêm source, dependency, trace và metadata.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Câu hỏi về Crossref và vector index không khớp với bài lab này. Repo hiện dùng Olist CSV; `DataGateway` đọc `orders`, `order_items`, `order_payments` và `sellers`, sau đó index theo `order_id`. Không thấy vector index hoặc pipeline Crossref trong repo.
2. Evaluation set của bài này là 50 input `EC_001.json` đến `EC_050.json`. Mỗi case cung cấp `claimed_order_id`; output được đối chiếu với các rule, entity, evidence, cause, tiền hoàn và action đúng. Repo không chứa một bộ ground-truth document IDs kiểu retrieval nên không thể báo cáo retrieval/answer-quality metric theo cách của bài Crossref.
3. Quality checks kiểm tra tính đúng của output tại một lượt chạy: schema, entity, evidence, money, policy priority và limits. Freshness monitoring theo dõi dữ liệu/runtime theo thời gian, chẳng hạn manifest hoặc hash dữ liệu; metadata hiện có hash CSV nhưng chưa chứng minh một cơ chế freshness monitoring hoàn chỉnh.
4. Phải dùng cùng test set cho baseline, corrupted và repaired để các thay đổi về metric phản ánh chất lượng của hệ thống chứ không phản ánh khác biệt về mẫu test.
5. Repair chỉ được xem là thành công khi artifact sau sửa được verifier approve, candidate/hash và các kiểm tra liên quan đều pass, rồi bundle đủ 50/50 được promote cùng `run_id`. Điểm cuối hoặc metric nghiệp vụ cần được tính trên cùng 50 case; repo hiện chưa có artifact ground truth/score độc lập để xác nhận điểm đó.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** NGUYỄN MẠNH HƯNG

**Ngày xác nhận:** 05/08/2026
