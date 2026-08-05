# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Đàm Vinh Quang |
| MSSV            | 2A202601255 |
| Khóa/Lớp        | K3           |
| Vai trò chính   | Order-Seller Agent |
| Ngày hoàn thành | 2026-08-05   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái                            |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Order & Seller Agent | `src/agents/order_seller.py` | `case_id`, `claimed_order_id`, Database Facts | `OrderSellerFacts` (JSON Schema) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính



## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng logic trích xuất Fact | `order_seller.py` | OrderSellerFacts chứa đúng item/freight totals và seller_ids | So khớp kết quả tính toán với CSV |


Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh: Trích xuất thông tin đơn hàng và người bán từ các file olist_orders_dataset.csv, olist_order_items_dataset.csv và olist_sellers_dataset.csv.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. **OrderSellerAgent** cần phải xử lý facts thô từ Database Gateway, tính đúng tổng tiền item/freight, nếu trích xuất thiếu seller thì Policy Agent sẽ phân xử sai.

### Cách triển khai
- **OrderSeller Agent**: Truy vấn `DataGateway` lấy raw fact. Dùng `ChatPromptTemplate` kết hợp `llm.with_structured_output(OrderSellerFacts)` để ép LLM trả về chính xác object JSON chứa mảng items và totals.

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | Dữ liệu thô từ CSV (Gateway) |
| Output                  | `OrderSellerFacts` |
| Module phụ thuộc        | Data Gateway            |
| Module sử dụng output   | Coordinator Agent|
| Điều kiện lỗi cần xử lý | LLM gặp sai sót trong khi trích xuất thông tin |

### Cách xác minh

```bash
python src/runner.py
```

- **Kết quả mong đợi:** OrderSeller trả đúng tổng tiền. Tổng kết 50/50 case pass.
- **Kết quả thực tế:** 50/50 case success, output JSON không chứa lỗi schema, không bị vượt limit entities.
- **Artifact/log:** `logging/trace.jsonl` ghi nhận event của `order_seller`.

## 5. Một quyết định kỹ thuật quan trọng



## 6. Một lỗi hoặc blocker đã xử lý



## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn về luồng hệ thống Multi-Agent A2A:

Chương trình nhận input từ dữ liệu các khiếu nại -> Coordicator Agent tiếp nhận thông tin và điều phối các Agent Order-Seller, Payment và Delivery thực hiện nhiệm vụ (xác minh từ bộ dữ liệu) -> sau khi tổng hợp đủ thông tin, Coornitor gọi và truyền thông tin tới Policy Agent, agent này dựa vào thông tin nhận được và chính sách hiện có và đưa ra quyết định -> Verify Agent sẽ đánh giá quyết định đó và thực hiện trả ra kết quả theo đúng quy chuẩn hoặc yêu cầu thực hiện lại nếu chưa đáp ứng hoặc sai.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đàm Vinh Quang  
**Ngày xác nhận:** 2026-08-05
