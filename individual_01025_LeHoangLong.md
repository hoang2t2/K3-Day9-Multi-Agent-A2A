# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Lê Hoàng Long  |
| MSSV            | 2A202601025      |
| Khóa/Lớp        | [K3/D303]         |
| Vai trò chính   | Payment Agent — đối soát thanh toán    |
| Ngày hoàn thành | [2026-08-05] |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Payment Agent | `src/agents/payment_agent.py` → `PaymentAgent.investigate()` | `case_id`, `claimed_order_id`, `item_total`, `freight_total` từ Order Agent | `PaymentFacts` bàn giao cho Coordinator | Hoàn thành |
| Truy vấn dữ liệu thanh toán | `src/data/gateway.py` → `get_payment_facts()` | `order_id`, `item_total`, `freight_total` | Raw payment rows và kết quả đối soát | Hoàn thành |
| Cơ chế retry khi rate limit | `src/retry_utils.py` → `retry_with_backoff` | Lời gọi LLM bị 429 | Lời gọi thành công sau backoff | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Thống nhất schema `PaymentFacts` | `src/schemas/handoff.py` — Policy Agent | Contract cố định giữa Payment và Policy, không đổi sau khi chốt |
| Debug lỗi rate limit toàn pipeline | Toàn nhóm | Áp dụng `retry_with_backoff` cho các agent khác |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ---------------- | ------------- |
| Xây Payment Agent nhận facts và ép về schema qua `with_structured_output` | `src/agents/payment_agent.py` | 50 bản ghi `PaymentFacts` trong `trace.jsonl` | Đếm dòng agent `payment` trong `trace.jsonl` |
| Tách phép tính tiền khỏi LLM, đưa vào gateway | `src/data/gateway.py` | Số liệu tài chính chính xác 2 chữ số | Điểm hạng mục Tài chính trên leaderboard |
| Xử lý rate limit bằng exponential backoff | `src/retry_utils.py` | Pipeline chạy hết 50 case không đứt | Log chạy full, không có exception |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

[Mô tả artifact, metric, report hoặc kết quả tích hợp.]

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Payment Agent xác định tổng số tiền khách đã thanh toán cho một order và kiểm tra số tiền đó có khớp với tổng giá trị hàng cộng phí vận chuyển hay không. Kết quả này là đầu vào bắt buộc cho ba nhánh trong EC_POLICY_V1: điều kiện `payment > 0` của `canceled_order_paid` và `unavailable_order_paid`, và điều kiện đối soát của `valid_split_payment` (từ 2 payment row, chênh lệch không quá 0.10 BRL). Nếu agent này sai, cả phân loại lẫn số tiền hoàn đều sai theo.

### Cách triển khai

Agent không giao phép tính cho LLM. `DataGateway.get_payment_facts()` truy vấn bảng `order_payments` theo `order_id`, cộng `payment_value` của từng row để ra `payment_total`, rồi so với `item_total + freight_total` nhận từ Order Agent để tính chênh lệch và cờ đối soát.

LLM chỉ nhận facts đã tính sẵn dưới dạng JSON và chuyển thành đối tượng `PaymentFacts` thông qua `with_structured_output()`. System prompt ràng buộc rõ: không được sửa số tiền hoặc ID, chỉ định dạng lại theo schema. Cách này giữ LLM thật sự tham gia pipeline nhưng không để nó chạm vào con số.

Một ràng buộc về thứ tự: agent này không chạy song song được với Order Agent, vì `item_total` và `freight_total` là tham số bắt buộc. Coordinator phải gọi Order Agent trước, lấy hai giá trị đó rồi mới gọi Payment Agent.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `case_id: str`, `claimed_order_id: str`, `item_total: float`, `freight_total: float` |
| Output | `PaymentFacts` — Pydantic model gồm danh sách payment rows, tổng thanh toán, chênh lệch và cờ đối soát |
| Module phụ thuộc | `src/data/gateway.py`, `src/llm_client.py`, `src/retry_utils.py`, `src/schemas/handoff.py` |
| Module sử dụng output | Coordinator, sau đó Policy Agent dùng để áp EC_POLICY_V1 |
| Điều kiện lỗi cần xử lý | Order không có payment row; provider trả 429 rate limit; LLM sinh output không khớp schema |

### Cách xác minh

```bash
[điền lệnh thật đã chạy, ví dụ: python -m src.main]
```

- **Kết quả mong đợi:** 50 bản ghi agent `payment` trong `trace.jsonl`, mọi giá trị tiền làm tròn 2 chữ số, `payment_total` khớp tổng cộng từ CSV.
- **Kết quả thực tế:** [điền số liệu thật.]
- **Artifact/log:** `trace.jsonl`, `output/EC_*.json` — không chứa secret.



## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Đề yêu cầu mỗi agent dùng model tối đa 10B tham số, trong khi hạng mục Financial resolution chiếm 20% điểm và ngưỡng đối soát chỉ 0.10 BRL. Cần quyết định LLM đóng vai trò gì trong Payment Agent.
- **Các phương án đã cân nhắc:** (1) Đưa toàn bộ payment rows vào prompt, để model tự cộng và tự kết luận đối soát. (2) Gateway tính bằng Python, LLM chỉ nhận facts và ép về schema qua `with_structured_output`.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Sai số cộng dồn của model 8B không chấp nhận được ở ngưỡng 0.10 BRL — lệch 0.01 là đổi nhánh rule, kéo theo sai cả `primary_issue`, `root_cause` và số tiền hoàn. Đổi lại, agent mất khả năng suy luận tự do trên dữ liệu thô, nhưng đó không phải yêu cầu của bài. `with_structured_output` còn loại bỏ hoàn toàn lỗi parse JSON thủ công.
- **Bằng chứng quyết định phù hợp:** [điền — ví dụ điểm hạng mục Tài chính trên leaderboard, hoặc số case có chênh lệch tính sai bằng 0.]
## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** [điền lỗi thật đã gặp, che toàn bộ secret.]
- **Lệnh hoặc bước tái hiện:** [điền lệnh.]
- **Nguyên nhân gốc:** Kiến trúc multi-agent nhân số lời gọi API lên theo số agent — 50 case nhân số agent vượt hạn mức request mỗi phút của free tier, khiến provider trả 429 và pipeline dừng giữa chừng.
- **Cách xử lý:** Bọc `investigate()` bằng decorator `@retry_with_backoff(max_retries=10, initial_delay=30)`, thử lại tối đa 10 lần với delay khởi điểm 30 giây và tăng dần theo backoff.
- **Cách xác minh sau khi sửa:** [điền — chạy full 50 case, đếm số bản ghi trong trace.]
- **Điều học được:** Retry policy phải thiết kế từ đầu trong hệ multi-agent, không phải vá sau. Đánh đổi là thời gian chạy full pipeline tăng đáng kể khi bị throttle, nên cần tính vào ngân sách thời gian của buổi thi.

Nếu chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** [Module/artifact.]
- **Những gì đã loại trừ:** [Các giả thuyết đã kiểm tra.]
- **Bước tiếp theo:** [Hành động có thể kiểm chứng.]

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

[Viết câu trả lời tại đây.]
**Câu trả lời:**



**1. Luồng dữ liệu.** Không có Crossref hay vector index. Dữ liệu là 9 file CSV tĩnh của Olist, truy xuất bằng join theo khóa chính chứ không qua tìm kiếm ngữ nghĩa. Luồng thực tế: `input/EC_XXX.json` cung cấp `claimed_order_id` → `DataGateway` join `orders`, `order_items`, `order_payments` theo `order_id` → mỗi agent domain trích facts trong phạm vi được cấp quyền → handoff cho Policy Agent dưới dạng Pydantic model có schema cố định.

**2. Đo chất lượng.** Không có evaluation set hay ground-truth document ID. Thay vào đó, mỗi case được chấm theo 6 hạng mục có trọng số: primary issue và confidence 20%, affected entities 20%, root cause và responsible parties 15%, evidence IDs 15%, financial resolution 20%, resolution actions 10%. Điểm cuối là trung bình 50 case. Vai trò tương đương ground truth là chính dữ liệu CSV — evidence ID nào không dựng được từ CSV bị tính là false positive.

**3. Kiểm tra chất lượng.** Không có freshness monitoring vì dữ liệu tĩnh, không cập nhật theo thời gian. Kiểm tra chất lượng trong lab này là kiểm tra tính hợp lệ và nhất quán, thực hiện ở Verifier Agent: evidence ID phải dựng được từ CSV, mọi số tiền làm tròn 2 chữ số, giới hạn số lượng ID cho mỗi entity set, và tính nhất quán giữa `primary_issue`, `root_cause`, `resolution_actions` với `case_status`.

**4. Tính tái lập.** Không có bộ ba baseline/corrupted/repaired. Nguyên tắc tương đương là mọi thay đổi trong pipeline đều được đánh giá trên cùng 50 case đầu vào, để chênh lệch điểm phản ánh đúng thay đổi trong logic chứ không phải khác biệt dữ liệu. Nhờ vậy mới so sánh được, chẳng hạn, tác động của việc chuyển phép tính tiền từ LLM sang Python.

**5. Xác minh kết quả.** Không có khái niệm repair. Kết quả được xác minh qua ba artifact: `output/` chứa đúng 50 file JSON đúng schema, `trace.jsonl` ghi lại từng lượt gọi agent để đối chiếu kết luận với dữ liệu đã dùng, và điểm trên hệ thống chấm theo 6 hạng mục trọng số ở trên.


## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ x ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ x ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ x ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ x ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ x ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Hoàng Long
**Ngày xác nhận:** [2026-08-05]
