# Kiến trúc Multi-Agent giải quyết khiếu nại Olist

> Trạng thái: tài liệu thiết kế mục tiêu. Repo đã có README, 9 CSV, 50 input JSON và một scaffold chưa hoàn chỉnh trong `src/`; chưa có đủ Coordinator/specialist/Policy/Verifier/runner, output hay trace/metadata chạy thật.

## 1. Mục tiêu và nguyên tắc

Hệ thống xử lý đúng 50 case `input/EC_001.json` đến `input/EC_050.json`, điều tra order được khai báo trong `customer_request.claimed_order_id` và sinh đúng một output JSON cùng tên trong `output/`.

Các nguyên tắc bất biến:

1. **Facts trước, quyết định sau:** kết luận chỉ dựa trên row tồn tại trong CSV và `EC_POLICY_V1`.
2. **Multi-agent thật:** mỗi agent là một invocation/session riêng, có system prompt, tool ACL, input/output schema và trace span riêng. Không dùng một prompt để giả lập tất cả vai trò.
3. **Deterministic core:** code, không phải model, thực hiện join, cộng tiền, làm tròn, so sánh timestamp, áp priority, dựng ID và validate schema.
4. **Least privilege:** specialist chỉ đọc view dữ liệu cần cho domain của mình. Policy Agent không đọc CSV; Coordinator không tự áp policy.
5. **Independent verification:** Verifier đọc lại facts qua audit API, tự tính lại và chỉ trả verdict; Verifier không được âm thầm sửa candidate.
6. **Transactional batch:** không publish một phần. Output, trace và metadata của cùng `run_id` chỉ được promote khi đủ 50 case đã qua verifier.
7. **Không suy diễn:** không tạo refund transaction, tracking checkpoint theo item, bằng chứng giao sai/giao thiếu hay sự kiện khác không có trong dataset.

## 2. Hiểu dữ liệu và chiến lược truy cập

### 2.1 Inventory đã kiểm tra

| Dataset | Số row | Grain/khóa | Vai trò |
| --- | ---: | --- | --- |
| `olist_orders_dataset.csv` | 99.441 | một row/`order_id` | trạng thái và các mốc thời gian |
| `olist_order_items_dataset.csv` | 112.650 | một row/`order_id + order_item_id` | seller, hạn bàn giao, item price, freight |
| `olist_order_payments_dataset.csv` | 103.886 | một row/`order_id + payment_sequential` | payment type, installment, payment value |
| `olist_sellers_dataset.csv` | 3.095 | một row/`seller_id` | kiểm chứng seller |
| `olist_customers_dataset.csv` | 99.441 | một row/`customer_id` | enrichment khách hàng |
| `olist_products_dataset.csv` | 32.951 | một row/`product_id` | enrichment sản phẩm |
| `olist_order_reviews_dataset.csv` | 99.224 | review row | enrichment; comment có thể chứa newline |
| `olist_geolocation_dataset.csv` | 1.000.163 | nhiều row/ZIP prefix | enrichment; phải aggregate trước khi join |
| `product_category_name_translation.csv` | 71 | category PT -> EN | enrichment |

Critical path của sáu rule chỉ dùng `orders`, `order_items`, `order_payments` và `sellers`. Năm bảng còn lại không tham gia quyết định hay field output hiện tại, nên mặc định không cấp cho agent để giảm nhiễu và prompt injection surface.

50 input hiện tại đã được pre-audit: 50 `case_id` và 50 `claimed_order_id` đều duy nhất, filename khớp case ID, tất cả dùng tiếng Việt và `EC_POLICY_V1`. Khi áp decision table deterministic, phân bố là 8 `canceled_order_paid`, 8 `unavailable_order_paid`, 8 `late_delivery_seller`, 8 `late_delivery_logistics`, 9 `valid_split_payment` và 9 `unsupported_late_claim`. Có 8 case không có item, 4 case nhiều item, 9 case nhiều payment row, không có case nhiều seller; không case nào vượt entity limit 5. `EC_008` đồng thời có status canceled và tín hiệu seller handoff trễ, nên là regression case bắt buộc chứng minh priority 1 thắng rule giao hàng. Các số này là pre-audit để kiểm tra thiết kế, không thay thế trace chạy thật.

### 2.2 Quan hệ dữ liệu

~~~mermaid
erDiagram
    CUSTOMERS ||--|| ORDERS : customer_id
    ORDERS ||--o{ ORDER_ITEMS : order_id
    ORDERS ||--o{ ORDER_PAYMENTS : order_id
    ORDERS ||--o{ ORDER_REVIEWS : order_id
    PRODUCTS ||--o{ ORDER_ITEMS : product_id
    SELLERS ||--o{ ORDER_ITEMS : seller_id
    GEO_ZIP ||--o{ CUSTOMERS : customer_zip_code_prefix
    GEO_ZIP ||--o{ SELLERS : seller_zip_code_prefix
~~~

`customer_id` là định danh khách theo từng order; chỉ dùng `customer_unique_id` nếu cần nhận diện cùng khách qua nhiều order. Bài toán hiện tại lookup bằng `claimed_order_id` nên không cần suy rộng sang các order khác của cùng khách.

`GEO_ZIP` trong sơ đồ là view đã aggregate `geolocation` theo `geolocation_zip_code_prefix`; tuyệt đối không join customer/seller trực tiếp với hơn một triệu geolocation rows.

### 2.3 Data Gateway

Một Data Gateway deterministic là thành phần duy nhất đọc trực tiếp `data/*.csv`. Gateway parse và index một lần khi batch khởi động:

~~~text
orders_by_id
items_by_order_id
payments_by_order_id
sellers_by_id
~~~

Gateway cung cấp các scoped tool/view theo ACL, không trả toàn bộ CSV cho model. Mọi query case bắt buộc có `claimed_order_id`. Seller chỉ được lấy qua `get_sellers_for_order(order_id)` hoặc cặp `order_id + seller_id` đã được kiểm tra seller thuộc item của order đó.

Gateway kiểm tra header, kiểu dữ liệu, duplicate key và child foreign-key reference trước khi xử lý case. Quan hệ con là optional: không yêu cầu mọi order phải có item, payment hoặc review; missing row được biểu diễn rõ trong facts.

Không được join trực tiếp item rows với payment rows. Gateway aggregate độc lập:

~~~text
item_total    = SUM(order_items.price)         GROUP BY order_id
freight_total = SUM(order_items.freight_value) GROUP BY order_id
payment_total = SUM(order_payments.payment_value) GROUP BY order_id
~~~

Sau đó mới hợp nhất ba fact theo `order_id`. Cách này tránh nhân bản tiền khi một order đồng thời có nhiều item và nhiều payment row.

## 3. Topology

~~~mermaid
flowchart LR
    I[50 input JSON] --> PF[Preflight Validator]
    PF --> C[Coordinator Agent]
    PF -->|immutable ValidatedCaseRef| V

    C -->|A2A fan-out| OS[Order & Seller Agent]
    C -->|A2A fan-out| PA[Payment Agent]
    C -->|A2A fan-out| DA[Delivery Agent]

    DG[(Read-only Data Gateway)] --> OS
    DG --> PA
    DG --> DA

    OS -->|OrderSellerFacts| B[Join barrier]
    PA -->|PaymentFacts| B
    DA -->|DeliveryFacts| B

    B -->|DecisionRequest| PO[Policy Agent]
    PO -->|facts| PE[[Deterministic EC_POLICY_V1 Engine]]
    PE -->|authoritative decision| PO
    PO -->|DecisionCandidate| V[Verifier Agent]
    DG -->|Constrained audit API| V

    V -->|approved + candidate hash| W[Staging Output Writer]
    V -->|rejected + errors| C
    W --> RB[(.runs/run_id bundle)]

    C -. event .-> T[Single Trace Writer]
    OS -. event .-> T
    PA -. event .-> T
    DA -. event .-> T
    PO -. event .-> T
    V -. event .-> T
    T --> RB
    MW[Metadata Writer] --> RB
    RB -->|50/50 bundle promotion| PUB[Transactional Publisher]
    PUB --> O[output/EC_001..EC_050.json]
    PUB --> L[logging/trace.jsonl + metadata.json]
~~~

Preflight Validator, Data Gateway, Policy Engine, Output Writer, Trace Writer, Metadata Writer và Publisher là deterministic components, không phải model agent.

## 4. Vai trò và quyền truy cập

| Thành phần | Trách nhiệm | Được đọc | Được ghi | Không được làm |
| --- | --- | --- | --- | --- |
| Preflight Validator | kiểm tra manifest và input contract | `input/*.json` | staging manifest | không gọi model, không sửa input |
| Coordinator Agent | tạo task, fan-out, chờ barrier, route handoff và hợp nhất fact envelopes thành `DecisionRequest` | input đã validate, fact envelopes | gửi A2A message | không đọc CSV, không tự áp policy |
| Order & Seller Agent | status, item/seller, item/freight totals, entity IDs | view `orders(order_id,status)`, `items`, `sellers` | `OrderSellerFacts` | không đọc payment/output |
| Payment Agent | payment rows, payment total, reconciliation | `payments` và derived view `item_total/freight_total` | `PaymentFacts` | không đọc customer message/status |
| Delivery Agent | delivery lateness và seller handoff | view timestamp của `orders` và `items(order_item_id,seller_id,shipping_limit_date)` | `DeliveryFacts` | không đọc giá/payment |
| Policy Agent | gọi Policy Engine và đóng gói authoritative decision thành output candidate | normalized facts và engine result | `DecisionCandidate` | không đọc CSV, không tự chọn/đổi rule, không tạo fact mới |
| Verifier Agent | kiểm tra lại schema, entity, evidence, money, priority và limits | immutable `ValidatedCaseRef`, candidate, raw scoped rows qua audit API | `VerificationReceipt` | không tin order ID từ candidate, không sửa candidate, không ghi output |
| Staging Output Writer | ghi đúng candidate đã duyệt vào run bundle | approved candidate + hash | `.runs/<run_id>/candidate-output/*.json` | không thay đổi JSON đã duyệt, không ghi thẳng `output/` |
| Trace Writer | serialize event theo thứ tự | audit events | `.runs/<run_id>/trace.jsonl` | không tham gia quyết định |
| Metadata Writer | ghi model/framework/runtime và manifest hash của run | runtime facts + model registry | `.runs/<run_id>/metadata.json` | không dùng giá trị tự khai của model |
| Transactional Publisher | promote bundle 50/50 đã validate | staged output, trace, metadata | `output/` và `logging/` | không publish run fail hoặc trộn nhiều `run_id` |

Provider adapter khởi tạo model client và inject client vào agent; agent không được đọc trực tiếp `.env`. Secret chỉ nằm trong `.env` và không được log.

## 5. Contract

### 5.1 Input contract

Preflight phải kiểm tra toàn bộ batch trước khi gọi agent:

- Có đúng 50 file `EC_001.json` đến `EC_050.json`, không thiếu, không trùng và không có JSON lạ.
- JSON parse được và có đủ:
  - `case_id`
  - `opened_at`
  - `customer_request.language`
  - `customer_request.message`
  - `customer_request.claimed_order_id`
  - `policy_version`
- `case_id` khớp tên file.
- `opened_at` là ISO-8601 có timezone; không dùng timestamp này để đổi timezone cho timestamp CSV.
- `claimed_order_id` có format hợp lệ và tồn tại trong `orders`.
- `policy_version == "EC_POLICY_V1"`.
- `message` được coi là untrusted text. Specialist chỉ nhận `case_id` và `claimed_order_id`, không nhận prose này.

Input sai là lỗi preflight, không tạo output phỏng đoán. Batch chỉ bắt đầu sau khi cả 50 input hợp lệ.

Preflight tạo một trust anchor immutable và đăng ký nó theo `trace_id`. Coordinator, Policy và candidate không được thay đổi object này; Verifier nhận bản tham chiếu trực tiếp từ registry:

~~~json
{
  "input_filename": "EC_001.json",
  "expected_case_id": "EC_001",
  "claimed_order_id": "<olist_order_id>",
  "policy_version": "EC_POLICY_V1",
  "input_sha256": "<sha256>"
}
~~~

Verifier dùng `ValidatedCaseRef.claimed_order_id` để gọi audit API và đối chiếu candidate; không dùng order ID do Policy chuyển tiếp làm trust source.

### 5.2 A2A envelope

Mọi request, result và error phải validate cùng một versioned envelope:

~~~json
{
  "schema_version": "a2a.v1",
  "message_id": "<uuid>",
  "trace_id": "<run_id>:EC_001",
  "parent_span_id": "<span_id|null>",
  "idempotency_key": "<run_id>/EC_001/payment.investigate",
  "case_id": "EC_001",
  "claimed_order_id": "<olist_order_id>",
  "policy_version": "EC_POLICY_V1",
  "sender": "coordinator",
  "recipient": "payment_agent",
  "message_type": "payment.investigate.request",
  "attempt": 1,
  "status": "ok",
  "payload": {},
  "evidence_ids": [],
  "warnings": [],
  "error": null
}
~~~

Quy tắc:

- Validate schema ở cả sender và receiver.
- `case_id` và `claimed_order_id` không được thay đổi qua handoff.
- Receiver đối chiếu hai field trên với `ValidatedCaseRef` trong registry.
- `idempotency_key` giữ nguyên khi retry; `attempt` tăng.
- Payload là typed JSON, không trao đổi prose tự do giữa các agent.
- Error dùng `code`, `retryable`, `message` và `details`; không chứa stack trace hoặc secret trong output chấm.

### 5.3 Domain fact contracts

**OrderSellerFacts**

~~~json
{
  "order_status": "delivered",
  "items": [
    {
      "order_item_id": 1,
      "seller_id": "<seller_id>",
      "shipping_limit_date": "2018-01-10 10:00:00",
      "price_brl": "100.00",
      "freight_brl": "15.00"
    }
  ],
  "item_total_brl": "100.00",
  "freight_total_brl": "15.00",
  "seller_ids": ["<seller_id>"],
  "evidence_ids": [
    "order:<order_id>",
    "item:<order_id>:1",
    "seller:<seller_id>"
  ]
}
~~~

**PaymentFacts**

~~~json
{
  "payment_rows": [
    {
      "payment_sequential": 1,
      "payment_value_brl": "115.00"
    }
  ],
  "payment_row_count": 1,
  "payment_total_brl": "115.00",
  "expected_total_brl": "115.00",
  "difference_brl": "0.00",
  "is_reconciled": true,
  "evidence_ids": ["payment:<order_id>:1"]
}
~~~

**DeliveryFacts**

~~~json
{
  "delivered_customer_date": "2018-01-20 10:00:00",
  "estimated_delivery_date": "2018-01-18 00:00:00",
  "delivered_carrier_date": "2018-01-11 10:00:00",
  "is_delivered_late": true,
  "late_handoff_item_ids": ["<order_id>:1"],
  "late_handoff_seller_ids": ["<seller_id>"],
  "delivery_classification": "seller_handoff_late"
}
~~~

Tiền dùng decimal string trong handoff để không mất chính xác; chỉ serialize thành JSON number ở final output.

### 5.4 DecisionCandidate và final output

Policy Agent trả đúng cây output trong README. Không thêm debug field vào candidate. Nguồn của từng field:

| Output field | Nguồn |
| --- | --- |
| `case_id` | input đã validate |
| `assessment.primary_issue` | rule đầu tiên match |
| `assessment.case_status` | `action_required` nếu refund > 0, ngược lại `no_action` |
| `assessment.confidence` | bảng confidence deterministic, luôn trong `[0,1]` |
| `affected_entities.order_ids` | claimed order tồn tại |
| `affected_entities.item_ids` | `order_id:order_item_id` từ item rows |
| `affected_entities.seller_ids` | seller rows liên quan |
| `affected_entities.payment_ids` | `order_id:payment_sequential` từ payment rows |
| `ranked_causes` | mặc định đúng một cause của primary rule, rank = 1 |
| `responsible_parties` | mapping policy và seller vi phạm nếu có |
| `evidence_ids` | chỉ các ID đã resolve được |
| `financial_resolution.*` | totals deterministic, currency luôn `BRL` |
| `recommended_refund_brl` | mapping policy |
| `resolution_actions` | mapping policy |

Semantics của affected entities là thống nhất cho cả sáu issue, không phụ thuộc cách diễn đạt của model:

| Issue | `order_ids` | `item_ids` | `seller_ids` | `payment_ids` |
| --- | --- | --- | --- | --- |
| canceled / unavailable | claimed order | mọi item row hiện có của order | mọi seller gắn với các item hiện có | mọi payment row của order |
| seller-late / logistics-late | claimed order | mọi item row của order | mọi seller gắn với các item | mọi payment row của order |
| valid split payment | claimed order | mọi item row của order | mọi seller gắn với các item | mọi payment row của order |
| unsupported late claim | claimed order | mọi item row của order | mọi seller gắn với các item | mọi payment row của order |

Các tập trên được deduplicate, sort và chỉ sau đó mới giới hạn. `responsible_parties` khác `affected_entities`: với seller-late, chỉ seller vi phạm là responsible; với logistics, party là `LOGISTICS_PROVIDER`; canceled/unavailable là `OLIST_PLATFORM`.

Giới hạn hard-check trước write:

- Tối đa 5 phần tử cho mỗi entity set.
- Tối đa 10 evidence IDs.
- Tối đa 3 ranked causes.
- Tối đa 3 responsible parties.
- Tối đa 5 actions.
- `confidence` trong `[0,1]`.
- Nếu order không có item: `item_ids=[]`, `seller_ids=[]`, `item_total_brl=0.0` và `freight_total_brl=0.0`.

Thiết kế confidence exhaustive vì README chỉ quy định miền giá trị: mọi candidate được publish dùng `0.95` khi predicate của primary rule đầy đủ và Verifier pass. Việc một lower-priority rule cũng match không làm giảm confidence vì ordered policy đã quyết định tie-break. Thiếu required fact không hạ confidence để đoán; case fail với `INCOMPLETE_REQUIRED_FACT` và không được publish.

Confidence là config/versioned code đã commit, không lấy trực tiếp từ lời tự đánh giá của model.

## 6. Luồng handoff cho một case

~~~mermaid
sequenceDiagram
    participant R as Batch Runner
    participant C as Coordinator
    participant O as OrderSeller
    participant P as Payment
    participant D as Delivery
    participant E as Policy
    participant PE as Deterministic Policy Engine
    participant V as Verifier
    participant W as Staging Writer

    R->>C: ValidatedCase
    par independent investigations
        C->>O: order_seller.investigate
        O-->>C: OrderSellerFacts
    and
        C->>P: payment.investigate
        P-->>C: PaymentFacts
    and
        C->>D: delivery.investigate
        D-->>C: DeliveryFacts
    end
    C->>E: DecisionRequest(all facts)
    E->>PE: evaluate typed predicates
    PE-->>E: authoritative PolicyDecision
    E-->>V: DecisionCandidate
    V->>V: recompute + schema/evidence/policy checks
    alt approved
        V-->>W: receipt + candidate_sha256
        W-->>C: output.written
    else rejected
        V-->>C: ValidationErrors(owner, code, path)
        C->>C: route one repair to owning agent
    end
    C-->>R: CaseCompleted
~~~

Các bước:

1. Runner tạo `run_id` và một run bundle mới tại `.runs/<run_id>/`; trace của run này được mở mới, không append run cũ.
2. Preflight validate cả manifest 50 file trước khi xử lý.
3. Coordinator fan-out ba task độc lập và chờ join barrier.
4. Lỗi truy xuất/schema của một domain làm case dừng; giá trị null hợp lệ vẫn được handoff dưới dạng fact thiếu kèm warning.
5. Policy Agent gọi Policy Engine deterministic. Engine đánh giá predicate ba trạng thái theo priority; model chỉ đóng gói authoritative decision.
6. Policy Agent tạo candidate từ engine result và chuyển thẳng cho Verifier.
7. Verifier audit lại dữ liệu, recompute totals/rule và hash canonical JSON.
8. Writer chỉ ghi đúng candidate có hash đã approved vào staging.
9. Metadata Writer chụp model registry, framework, runtime, input/data/output hashes và trạng thái run vào cùng bundle.
10. Khi 50/50 case pass, Publisher validate bundle rồi promote output, trace và metadata của cùng `run_id` theo một transaction có rollback; không cam kết directory rename là atomic trên mọi filesystem.
11. Packaging gate xác nhận `output/` chỉ có đúng 50 JSON cần nộp.

Repair route theo ownership:

| Verification error | Owner nhận repair |
| --- | --- |
| issue/cause/party/refund/action hoặc candidate mapping | Policy Agent |
| order/item/seller fact hoặc evidence nguồn | Order & Seller Agent |
| payment total/reconciliation/payment evidence | Payment Agent |
| timestamp/late-handoff fact | Delivery Agent |
| candidate serialization/hash | Staging Writer |
| raw row, CSV, index hoặc independent recomputation không nhất quán | deterministic failure; không agent nào được sửa |

## 7. Policy engine EC_POLICY_V1

Policy phải là ordered decision table; model không được đổi thứ tự:

| Priority | Primary issue | Điều kiện | Cause | Party | Refund | Action |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `canceled_order_paid` | status = canceled và payment total > 0 | `ORDER_CANCELED_AFTER_PAYMENT` | `platform / OLIST_PLATFORM` | payment total | `issue_full_refund` |
| 2 | `unavailable_order_paid` | status = unavailable và payment total > 0 | `ORDER_UNAVAILABLE_AFTER_PAYMENT` | `platform / OLIST_PLATFORM` | payment total | `issue_full_refund` |
| 3 | `late_delivery_seller` | delivered > estimated và carrier > shipping limit của ít nhất một item | `SELLER_HANDOFF_AFTER_LIMIT` | `seller / violating seller_id` | freight total | `refund_freight` |
| 4 | `late_delivery_logistics` | delivered > estimated và carrier <= shipping limit của các item liên quan | `CARRIER_DELIVERED_AFTER_ESTIMATE` | `logistics_provider / LOGISTICS_PROVIDER` | freight total | `refund_freight` |
| 5 | `valid_split_payment` | payment rows >= 2 và difference <= 0.10 BRL | `MULTIPLE_PAYMENTS_RECONCILED` | rỗng | 0 | `explain_valid_split_payment` |
| 6 | `unsupported_late_claim` | delivered <= estimated và payment reconciled | `DELIVERY_WITHIN_ESTIMATE` | rỗng | 0 | `reject_late_refund` |

Policy Engine là nguồn quyết định authoritative. Mỗi predicate trả một trong ba trạng thái:

- `TRUE`: chọn rule và dừng.
- `FALSE`: đi tiếp rule thấp hơn.
- `UNKNOWN`: dừng với `INCOMPLETE_REQUIRED_FACT`; không được bỏ qua để chọn rule thấp hơn.

Đánh giá conjunction theo short-circuit có chứng cứ. Ví dụ status = delivered làm rule canceled/unavailable `FALSE` dù payment thiếu; status = canceled nhưng payment total chưa biết làm rule 1 `UNKNOWN`. Nếu delivery date/estimated date thiếu sau khi hai rule status đã `FALSE`, rule giao hàng là `UNKNOWN` và không được rơi xuống split-payment. Verifier từ chối candidate nếu engine bỏ qua `TRUE` hoặc `UNKNOWN` của rule priority cao hơn.

### 7.1 Tiền và rounding

- Parse bằng Decimal, không dùng binary float.
- `payment_value` là giá trị cả payment row, không chia cho `payment_installments`.
- Aggregate tất cả rows trước; quantize hai chữ số bằng `ROUND_HALF_UP` tại contract/output boundary.
- Reconciliation:

~~~text
expected_total = round(item_total + freight_total, 2)
payment_total  = round(sum(payment_value), 2)
difference     = abs(payment_total - expected_total)
is_reconciled  = difference <= 0.10
~~~

- Canceled/unavailable hoàn toàn bộ payment.
- Hai rule late delivery hoàn tổng freight của order, không chỉ freight item vi phạm.
- Tất cả số tiền output phải hữu hạn, không âm và có tối đa hai chữ số thập phân.

### 7.2 Timestamp và nhiều seller

- Parse cùng format trong CSV và so sánh giá trị trực tiếp; không chuyển múi giờ.
- `is_delivered_late = delivered_customer_date > estimated_delivery_date`.
- Seller vi phạm nếu ít nhất một item của seller thỏa `delivered_carrier_date > shipping_limit_date`.
- Chỉ seller có item vi phạm xuất hiện trong responsible parties.
- Bộ 50 case chính thức không có tình huống mơ hồ giữa nhiều seller; implementation vẫn deduplicate và sort seller IDs.
- Thiếu timestamp bắt buộc để chứng minh một rule giao hàng trả `INCOMPLETE_REQUIRED_FACT` nếu không có rule priority cao hơn đã match; không mặc định seller hay logistics.

## 8. Entity và evidence

Chỉ cho phép:

~~~text
order:<order_id>
item:<order_id>:<order_item_id>
payment:<order_id>:<payment_sequential>
seller:<seller_id>
policy:<root_cause_code>
~~~

Verifier kiểm tra:

- Regex/format đúng.
- Order/item/payment/seller resolve về row thật.
- Item/payment thuộc đúng `claimed_order_id`.
- Seller đúng với item liên quan.
- Policy evidence thuộc enum root-cause và khớp cause trong candidate.
- Đủ evidence tối thiểu của primary rule theo bảng dưới.
- Không có ID trùng.

| Primary issue | Evidence tối thiểu |
| --- | --- |
| `canceled_order_paid` / `unavailable_order_paid` | order + policy cause + ít nhất một payment row có giá trị dương |
| `late_delivery_seller` | order + policy cause + ít nhất một violating item cho mỗi responsible seller + các seller evidence đó |
| `late_delivery_logistics` | order + policy cause + ít nhất một item có shipping limit được dùng để loại seller-late |
| `valid_split_payment` | order + policy cause + ít nhất hai payment rows + ít nhất một item nếu order có item |
| `unsupported_late_claim` | order + policy cause + ít nhất một payment row và ít nhất một item nếu order có item |

Khi số evidence vượt 10, áp exact ordering rồi lấy 10 ID đầu:

| Issue group | Evidence ordering |
| --- | --- |
| canceled / unavailable | order, policy, payments tăng dần, items tăng dần, sellers từ điển |
| seller-late | order, policy, violating items tăng dần, responsible sellers từ điển, remaining items, payments |
| logistics-late | order, policy, items tăng dần, sellers từ điển, payments |
| valid split | order, policy, payments tăng dần, items tăng dần, sellers từ điển |
| unsupported late | order, policy, items tăng dần, payments tăng dần, sellers từ điển |

`order_item_id` và `payment_sequential` sort số tăng dần; seller ID sort từ điển. Sau đó mới truncate. Financial totals luôn tính trên toàn bộ rows, không chỉ những entity được xuất ra. Việc truncate phải ghi warning vào trace nhưng không tạo ID tổng hợp giả.

## 9. Verifier và publish gates

Verifier từ chối candidate khi có bất kỳ lỗi nào:

- `case_id` không khớp input hoặc filename.
- Thiếu field, sai type/enum, có extra debug field hoặc JSON không hợp lệ.
- Primary issue/cause/party/refund/action không đúng mapping.
- Bỏ qua một rule priority cao hơn có trạng thái `TRUE` hoặc `UNKNOWN`.
- Entity/evidence không tồn tại hoặc không thuộc order.
- Evidence hợp lệ về format nhưng không đủ tập tối thiểu để chứng minh primary rule.
- Tổng tiền khác kết quả recompute.
- `case_status` không tương thích refund.
- `currency != "BRL"`.
- Confidence ngoài `[0,1]`.
- Mảng vượt cardinality limit.
- Rank không bắt đầu từ 1 hoặc không tăng liên tục.
- Có duplicate, NaN, infinity hoặc tiền quá hai chữ số.
- Trường hợp không có item không trả đúng các array/tổng bằng rỗng/0.

Verifier trả receipt, không sửa candidate:

~~~json
{
  "approved": true,
  "candidate_sha256": "<sha256-of-canonical-json>",
  "checks": {
    "schema": "pass",
    "entities": "pass",
    "evidence": "pass",
    "money": "pass",
    "policy_priority": "pass",
    "limits": "pass"
  },
  "errors": []
}
~~~

Verifier lấy raw scoped rows từ audit API và dùng module tính toán độc lập với aggregate path của specialist; audit API không được chỉ trả lại aggregate đã tính sẵn. Staging Writer canonicalize JSON, kiểm tra hash lần cuối và ghi file tạm trong `.runs/<run_id>/candidate-output/`. Không đặt staging, `.gitkeep` hoặc file tạm trong `output/`.

## 10. Lỗi, retry và idempotency

Retry tối đa ba lần với exponential backoff cho lỗi transient:

- timeout;
- provider 429/5xx;
- kết nối tool tạm thời lỗi.

Agent trả JSON sai schema chỉ được một repair attempt với validation errors cụ thể. Không retry lỗi deterministic. Lỗi thiếu timestamp chỉ terminal khi rule được chọn thực sự cần timestamp đó; canceled/unavailable đã đủ status + payment không bị chặn:

- input/policy version sai;
- order không tồn tại;
- duplicate primary key hoặc CSV malformed;
- required timestamp thiếu;
- evidence/entity không tồn tại;
- policy không match.

Error payload:

~~~json
{
  "code": "ORDER_NOT_FOUND",
  "retryable": false,
  "message": "claimed_order_id does not exist",
  "details": {
    "order_id": "<order_id>"
  }
}
~~~

Nếu repair vẫn fail, case fail và batch không publish partial output. Không tạo placeholder hoặc kết luận đoán để đủ số lượng.

## 11. Concurrency, reproducibility và model

- Parse/index dữ liệu một lần, không scan CSV cho từng agent/case.
- Ba specialist trong một case chạy song song.
- Giữa các case dùng bounded concurrency, mặc định 4-8 case tùy VRAM/rate limit.
- Policy và Verifier chạy tuần tự sau join barrier.
- Stable sort mọi entity/evidence và output theo `case_id`; kết quả không phụ thuộc thứ tự coroutine hoàn thành.
- Model temperature mặc định 0 cho fact/decision tasks.
- Mỗi agent dùng model <= 10B parameters.
- Model registry và binding agent -> model là constant trong source/config được commit, không nằm trong `.env`.
- `logging/metadata.json` phải ghi đúng binding, model name, parameter size, framework và runtime thực tế; preflight từ chối model binding >10B.

Deterministic components không cần model và không bị tính là agent dùng model.

## 12. Trace và metadata

### 12.1 Trace

Mỗi run tạo mới `.runs/<run_id>/trace.jsonl`, không append run cũ. Trong run, mọi agent gửi event tới một Trace Writer duy nhất. Chỉ bundle thành công 50/50 mới replace `logging/trace.jsonl`; vì vậy trace, metadata và output chính thức luôn cùng `run_id`. Trace run thất bại giữ trong `.runs/` để debug và không được dùng làm artifact nộp.

~~~json
{
  "timestamp": "2026-08-05T10:15:30.123+07:00",
  "run_id": "<run_id>",
  "trace_id": "<run_id>:EC_001",
  "span_id": "<span_id>",
  "parent_span_id": "<parent_span_id|null>",
  "case_id": "EC_001",
  "agent": "payment_agent",
  "event": "handoff.completed",
  "message_type": "payment.investigate.result",
  "attempt": 1,
  "status": "ok",
  "duration_ms": 18,
  "evidence_ids": ["payment:<order_id>:1"],
  "input_sha256": "<hash>",
  "output_sha256": "<hash>"
}
~~~

Event tối thiểu: `batch.started`, `case.started`, specialist `started/completed`, mỗi handoff, `policy.completed`, `verification.completed`, `output.staged`, `case.completed` và `batch.completed`. Event cuối ghi số `succeeded/failed` thực tế; Publisher chỉ nhận bundle có `succeeded=50, failed=0`.

Không log API key, `.env`, toàn bộ customer message hoặc raw prose của model. Trace chỉ giữ lượt chạy mới nhất.

### 12.2 Metadata

~~~json
{
  "run_id": "<run_id>",
  "status": "succeeded",
  "policy_version": "EC_POLICY_V1",
  "models": {
    "shared_model": {
      "name": "<hard-coded-model-id>",
      "parameter_size_billion": 7
    }
  },
  "agent_models": {
    "coordinator": "shared_model",
    "order_seller": "shared_model",
    "payment": "shared_model",
    "delivery": "shared_model",
    "policy": "shared_model",
    "verifier": "shared_model"
  },
  "agents": [
    "coordinator",
    "order_seller",
    "payment",
    "delivery",
    "policy",
    "verifier"
  ],
  "framework": "<framework>",
  "runtime": {
    "language": "Python",
    "version": "<actual-version>"
  },
  "input_count": 50,
  "output_count": 50,
  "output_manifest_sha256": "<hash>",
  "trace_sha256": "<hash>",
  "data_sha256": {
    "olist_orders_dataset.csv": "<hash>",
    "olist_order_items_dataset.csv": "<hash>",
    "olist_order_payments_dataset.csv": "<hash>",
    "olist_sellers_dataset.csv": "<hash>"
  }
}
~~~

## 13. Cấu trúc source mục tiêu

Scaffold `src/` hiện tại mới có một phần config/schema/data/observability. Khi triển khai tiếp, cần căn chỉnh scaffold với trust anchor, tri-state Policy Engine, independent verifier và transactional run bundle trong tài liệu này.

~~~text
src/
  runner.py
  config.py                    # committed MODEL_REGISTRY + AGENT_MODEL_BINDINGS; no secret
  schemas/
    input.py
    output.py
    handoff.py
    trace.py
  data/
    gateway.py
    indexes.py
  agents/
    coordinator.py
    order_seller.py
    payment.py
    delivery.py
    policy.py
    verifier.py
  policy/
    ec_policy_v1.py
  validation/
    evidence.py
    financials.py
    policy_audit.py             # independent verifier path
    output_validator.py
  observability/
    trace_writer.py
    metadata_writer.py
  publishing/
    bundle_publisher.py
tests/
  unit/
    test_aggregation.py
    test_policy_priority.py
    test_evidence.py
    test_output_schema.py
  integration/
    test_single_case.py
    test_batch_50.py
~~~

Python/Pydantic chỉ là lựa chọn triển khai đề xuất; JSON contracts và quyền truy cập ở tài liệu này không phụ thuộc framework.

## 14. Acceptance checklist

### Input và batch

- [ ] Đúng 50 input, đúng tên và `case_id` khớp filename.
- [ ] `claimed_order_id` tồn tại; `policy_version` là `EC_POLICY_V1`.
- [ ] Không xử lý nếu preflight bất kỳ case nào fail.

### Multi-agent

- [ ] Sáu agent có invocation, prompt, ACL, schema và trace span riêng.
- [ ] Có ba specialist handoff facts, Policy handoff candidate và Verifier handoff receipt.
- [ ] Không có một prompt duy nhất làm toàn bộ pipeline.

### Correctness

- [ ] Aggregate item/payment độc lập trước khi merge.
- [ ] Test đủ sáu rule và các trường hợp nhiều item/payment.
- [ ] Policy Engine deterministic là nguồn quyết định; test priority bằng case đồng thời match nhiều điều kiện và predicate `UNKNOWN`.
- [ ] Decimal/rounding/tolerance và timestamp đúng README.
- [ ] Không suy diễn dữ liệu không tồn tại.

### Output

- [ ] Mỗi input có một output cùng tên và đúng schema.
- [ ] Entity/evidence tồn tại, đúng order, đủ minimum evidence theo issue và không vượt limits.
- [ ] Cause/party/refund/action đúng mapping.
- [ ] Case không item trả arrays rỗng và totals 0.
- [ ] Verifier audit bằng immutable `ValidatedCaseRef` và raw scoped rows, không tin candidate.
- [ ] Chỉ promote bundle output/trace/metadata cùng `run_id` khi verifier pass 50/50.

### Audit và nộp bài

- [ ] `architecture.md` chứa sơ đồ, vai trò, quyền và handoff.
- [ ] `individual_5SoCuoiMHV_HoVaTen.md` được từng thành viên điền đúng phần việc thực tế.
- [ ] `logging/trace.jsonl` là trace thật của run mới nhất.
- [ ] `logging/metadata.json` ghi binding và model <=10B của từng agent, framework, runtime và manifest hash.
- [ ] Secret chỉ ở `.env`, model registry nằm trong source và metadata.
- [ ] Toàn bộ source đã commit và giữ nguyên tên repo nhóm.
- [ ] Zip chỉ chứa `EC_001.json` đến `EC_050.json` trong `output/`; không có source, log, audit hay `.env`.

## 15. Các assumption ngoài README

README chưa định nghĩa các điểm sau; thiết kế này chốt rõ để implementation reproducible:

- Rounding mode: `ROUND_HALF_UP`.
- Confidence: mọi candidate được publish dùng `0.95` sau khi required predicate đầy đủ và Verifier pass.
- Predicate policy dùng ba trạng thái `TRUE/FALSE/UNKNOWN`; `UNKNOWN` dừng priority scan và fail thay vì chọn rule thấp hơn.
- Missing required timestamp/order/policy-no-match làm case fail thay vì tạo primary issue mới.
- Affected entities lấy toàn bộ entity thuộc claimed order; evidence áp minimum và exact ordering tại Mục 8 trước khi truncate.
- `logging/` chứa trace/metadata của bundle 50/50 mới nhất; staging và failed runs nằm ngoài `output/` tại `.runs/`.
- Verifier không tự sửa; tối đa một repair được route về đúng owner.
- Batch promotion có rollback và chỉ chạy khi đủ 50/50; không giả định directory swap atomic trên mọi filesystem.

Các assumption này phải được version hóa trong source và test; thay đổi chúng không được làm thay đổi sáu rule bắt buộc của `EC_POLICY_V1`.

## 16. Traceability với README

| Yêu cầu README | Phần thiết kế đáp ứng |
| --- | --- |
| Dữ liệu, join và cảnh báo cardinality (dòng 15-31) | Mục 2 và 7.1 |
| Input `EC_001..EC_050` và `claimed_order_id` (dòng 33-59) | Mục 5.1 và 6 |
| Priority, refund, party, action và root cause (dòng 61-83) | Mục 7 |
| Evidence formats và existence check (dòng 85-97) | Mục 8 và 9 |
| Output schema, limits và no-item rule (dòng 99-150) | Mục 5.4 và 9 |
| Phân công agent và handoff thật (dòng 152-163) | Mục 3, 4 và 6 |
| 50 output và artifacts audit (dòng 165-187) | Mục 6, 12 và 14 |
| Model <=10B, `.env` và model metadata (dòng 197-202) | Mục 4, 11, 12 và 14 |
