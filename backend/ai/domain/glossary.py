"""
DataTrust OS: Centralized Business & Technical Domain Glossary
Source of Truth for terminology, definitions, and concepts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import difflib
import re
import unicodedata


def normalize_text_for_lookup(text: str) -> str:
    """Removes diacritics, punctuation, extra spaces and converts to lowercase for resilient lookup."""
    if not text:
        return ""
    text = text.lower().strip()
    # NFKD normalization to strip accents
    nfkd = unicodedata.normalize('NFKD', text)
    unaccented = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Punctuation to space
    cleaned = re.sub(r'[^\w\s]', ' ', unaccented)
    return " ".join(cleaned.split())


@dataclass(frozen=True)
class GlossaryTerm:
    term_id: str
    name_vi: str
    name_en: str
    category: str
    definition_vi: str
    definition_en: str
    aliases: List[str] = field(default_factory=list)
    details_vi: str = ""
    details_en: str = ""


# -----------------------------------------------------------------------------
# Canonical Glossary Definitions
# -----------------------------------------------------------------------------
GLOSSARY_REGISTRY: Dict[str, GlossaryTerm] = {
    "detector_levels": GlossaryTerm(
        term_id="detector_levels",
        name_vi="Bộ kiểm định kỹ thuật L1–L4",
        name_en="L1–L4 Technical Detector Suite",
        category="Detector Suite",
        definition_vi=(
            "L1–L4 là bốn cấp kiểm định kỹ thuật của Lane A: L1 kiểm tra schema, kiểu dữ liệu, null, "
            "giới hạn vật lý và bất biến xác định; L2 phát hiện bất thường và trôi dạt thống kê theo ngữ cảnh; "
            "L3 kiểm tra quan hệ đa biến và liên thực thể; L4 phát hiện điểm thay đổi và dịch chuyển chế độ theo thời gian."
        ),
        definition_en=(
            "The four Lane A technical validation levels: L1 deterministic schema and invariant checks; "
            "L2 contextual statistical anomaly and drift detection; L3 multivariate and cross-entity relational checks; "
            "and L4 temporal change-point and regime-shift detection."
        ),
        aliases=["l1-l4", "l1–l4", "l1 đến l4", "l1 tới l4", "l1 to l4", "các tầng l1 l2 l3 l4"],
        details_vi="Bản ghi được đánh giá qua bộ kiểm định phù hợp với cấu hình dataset trước khi Lane C hợp nhất kết quả định tuyến.",
        details_en="Records are evaluated by the configured detector suite before Lane C merges routing verdicts.",
    ),
    "silver": GlossaryTerm(
        term_id="silver",
        name_vi="Bản ghi Silver (Dữ liệu đạt chuẩn)",
        name_en="Silver Record (Clean Data)",
        category="Medallion Architecture",
        definition_vi="Bản ghi đã vượt qua toàn bộ các phép kiểm tra kỹ thuật Lane A (L1–L4), chính sách tuân thủ Lane B và các bước Data Treatment bắt buộc, đủ điều kiện chuyển tiếp sang tầng lưu trữ / tiêu thụ tiếp theo.",
        definition_en="A record that has passed all Lane A technical checks (L1–L4), Lane B compliance policies, and mandatory data treatment, qualified for downstream promotion.",
        aliases=[
            "silver", "bản ghi silver", "dữ liệu silver", "dữ liệu sạch", "bản ghi sạch",
            "dòng sạch", "clean data", "clean record", "silver record", "đạt chuẩn", "pass"
        ],
        details_vi="Số lượng bản ghi Silver (`silver_count`) được lưu trữ chính thức trong bảng `orchestration.pipeline_runs` và là chỉ số cốt lõi phản ánh tỷ lệ dữ liệu sạch của một lần chạy kiểm toán.",
        details_en="Silver count (`silver_count`) is officially stored in `orchestration.pipeline_runs` and represents the primary metric of clean data yield in an audit run."
    ),
    "bronze": GlossaryTerm(
        term_id="bronze",
        name_vi="Tầng Bronze (Dữ liệu thô)",
        name_en="Bronze Layer (Raw Ingestion)",
        category="Medallion Architecture",
        definition_vi="Tầng dữ liệu thô ban đầu được nạp trực tiếp từ các nguồn dữ liệu tác nghiệp (Data Source), giữ nguyên định dạng gốc và chưa qua thẩm định chất lượng hoặc tuân thủ.",
        definition_en="The raw ingestion layer holding source records in their original state before any quality validation or compliance enforcement.",
        aliases=["bronze", "tầng bronze", "dữ liệu bronze", "raw data", "dữ liệu thô", "bronze layer"],
        details_vi="Tầng Bronze là đầu vào của DataTrust Pipeline để quét các quy tắc kỹ thuật L1–L4 và chính sách Lane B.",
        details_en="Bronze data is the entry point for DataTrust pipelines to execute L1-L4 checks and Lane B policies."
    ),
    "gold": GlossaryTerm(
        term_id="gold",
        name_vi="Tầng Gold (Dữ liệu tổng hợp cao cấp)",
        name_en="Gold Layer (Aggregated & Certified)",
        category="Medallion Architecture",
        definition_vi="Tầng dữ liệu đã được làm sạch, tổng hợp theo mô hình kinh doanh và được chứng thực toàn vẹn bằng chữ ký kiểm toán (Evidence Hash), sẵn sàng phục vụ báo cáo BI và AI phân tích.",
        definition_en="The aggregated, business-level curated layer certified with cryptographic audit evidence, ready for BI and downstream analytics.",
        aliases=["gold", "tầng gold", "dữ liệu gold", "gold layer", "certified data"],
        details_vi="Dữ liệu tầng Gold luôn đi kèm bằng chứng kiểm toán độc lập và tem dấu thời gian đảm bảo tính bất biến.",
        details_en="Gold data is always backed by independent cryptographic evidence and immutable audit trails."
    ),
    "lane_a": GlossaryTerm(
        term_id="lane_a",
        name_vi="Làn A: Kiểm soát Kỹ thuật & Độ tin cậy (Lane A)",
        name_en="Lane A: Technical Reliability & Quality Control",
        category="Governance Lanes",
        definition_vi="Làn kiểm soát chuyên sâu về tính đúng đắn kỹ thuật và độ tin cậy dữ liệu, bao gồm chuỗi 4 cấp độ kiểm định từ L1 đến L4.",
        definition_en="The governance lane dedicated to technical correctness and data reliability, comprising the 4-tier L1–L4 validation suite.",
        aliases=["lane a", "làn a", "lane_a", "kiểm soát kỹ thuật", "technical lane"],
        details_vi="Lane A đảm bảo schema, kiểu dữ liệu, phân phối thống kê, quan hệ khóa ngoại và tính ổn định chuỗi thời gian của tập dữ liệu.",
        details_en="Lane A validates schema, datatypes, statistical distribution, foreign keys, and temporal stability."
    ),
    "lane_b": GlossaryTerm(
        term_id="lane_b",
        name_vi="Làn B: Tuân thủ Chính sách & Pháp lý (Lane B)",
        name_en="Lane B: Regulatory Compliance & Legal Governance",
        category="Governance Lanes",
        definition_vi="Làn kiểm soát độc lập về tuân thủ chính sách bảo vệ dữ liệu và khung pháp lý (như Luật 91, Nghị định 13, GDPR, CCPA, SOX-404).",
        definition_en="The independent governance lane enforcing regulatory compliance and data protection frameworks (such as Law 91, Decree 13, GDPR, CCPA, SOX-404).",
        aliases=["lane b", "làn b", "lane_b", "tuân thủ pháp lý", "compliance lane", "chính sách pháp lý"],
        details_vi="Lane B kiểm tra dữ liệu nhạy cảm, quyền riêng tư, phân loại PII và tính hợp lệ của việc thu thập/xử lý dữ liệu.",
        details_en="Lane B checks sensitive data, privacy mandates, PII classification, and lawful processing basis."
    ),
    "l1": GlossaryTerm(
        term_id="l1",
        name_vi="Cấp độ L1: Ràng buộc xác định & Schema (L1)",
        name_en="Level L1: Deterministic Technical Rules & Schema",
        category="Detector Suite",
        definition_vi="Cấp độ kiểm định kỹ thuật cơ sở bao gồm: cấu trúc schema, kiểu dữ liệu, trường bắt buộc (null check), giới hạn vật lý (range check, regex format) và các bất biến xác định (deterministic invariants).",
        definition_en="Baseline deterministic checks comprising schema structure, data types, null constraints, physical range bounds, format regex, and deterministic invariants.",
        aliases=[
            "l1", "lớp l1", "cấp độ l1", "level 1", "level l1", "l1 rules",
            "ràng buộc cứng", "schema check", "null check", "bất biến xác định"
        ],
        details_vi="Khi bản ghi vi phạm L1, nó sẽ bị chuyển ngay vào trạng thái Cách ly (Quarantine) do không đạt chuẩn kỹ thuật tối thiểu.",
        details_en="Records violating L1 are immediately routed to Quarantine as they fail baseline structural criteria."
    ),
    "l2": GlossaryTerm(
        term_id="l2",
        name_vi="Cấp độ L2: Bất thường & Trôi dạt Thống kê theo Ngữ cảnh (L2)",
        name_en="Level L2: Contextual Statistical Anomaly & Drift",
        category="Detector Suite",
        definition_vi="Cấp độ kiểm tra các dấu hiệu bất thường và trôi dạt phân phối thống kê theo ngữ cảnh (distribution drift, Z-Score, IQR, Isolation Forest, trôi phân phối cột so với đường chuẩn lịch sử).",
        definition_en="Checks detecting contextual statistical anomalies and distribution drifts against historical baselines (Z-Score, IQR, Isolation Forest, column distribution shifts).",
        aliases=[
            "l2", "lớp l2", "cấp độ l2", "level 2", "level l2", "l2 rules",
            "trôi ngắt ngữ cảnh", "trôi dạt thống kê", "bất thường thống kê", "statistical drift"
        ],
        details_vi="L2 phát hiện các sai lệch phân phối dữ liệu dù bản ghi có thể vẫn thỏa mãn các điều kiện kỹ thuật L1 đơn thuần.",
        details_en="L2 identifies distribution deviations even when records technically satisfy L1 range limits."
    ),
    "l3": GlossaryTerm(
        term_id="l3",
        name_vi="Cấp độ L3: Quan hệ Đa biến & Liên Thực thể (L3)",
        name_en="Level L3: Multivariate & Cross-Entity Relational Integrity",
        category="Detector Suite",
        definition_vi="Cấp độ kiểm tra tính toàn vẹn quan hệ đa biến, ràng buộc liên thực thể và sai số quan hệ giữa nhiều cột hoặc giữa các bảng/hệ thống tác nghiệp.",
        definition_en="Checks validating multivariate consistency, cross-entity relational constraints, and referential integrity across multiple columns or disparate tables.",
        aliases=[
            "l3", "lớp l3", "cấp độ l3", "level 3", "level l3", "l3 rules",
            "liên thực thể", "quan hệ đa biến", "toàn vẹn quan hệ", "cross-entity"
        ],
        details_vi="Ví dụ L3: Kiểm tra mối quan hệ logic giữa thời lượng chuyến xe, quãng đường di chuyển và tổng cước phí phát sinh.",
        details_en="Example L3: Validating multivariate logic between trip duration, distance, and total computed fare."
    ),
    "l4": GlossaryTerm(
        term_id="l4",
        name_vi="Cấp độ L4: Điểm Thay đổi & Dịch chuyển Chế độ Thời gian (L4)",
        name_en="Level L4: Temporal Regime Shifts & Change Points",
        category="Detector Suite",
        definition_vi="Cấp độ phát hiện các điểm thay đổi cấu trúc và sự dịch chuyển chế độ hoạt động theo chuỗi thời gian (sử dụng thuật toán PELT changepoints, phát hiện xu hướng dài hạn và phân kỳ chu kỳ).",
        definition_en="Advanced temporal surveillance detecting structural change points and operating regime shifts over time series (using PELT algorithms, long-term trend analysis, and cyclical divergence).",
        aliases=[
            "l4", "lớp l4", "cấp độ l4", "level 4", "level l4", "l4 rules",
            "dịch chuyển chế độ", "điểm thay đổi thời gian", "thời gian", "changepoint", "regime shift", "pelt"
        ],
        details_vi="L4 giúp kiểm toán viên phát hiện sớm các sự cố mang tính hệ thống kéo dài hoặc thay đổi cấu trúc hành vi mà các phép kiểm tra theo lô ngắn hạn bỏ sót.",
        details_en="L4 enables auditors to identify systemic regime shifts that batch-level short-window tests miss."
    ),
    "finding": GlossaryTerm(
        term_id="finding",
        name_vi="Bản ghi Phát hiện Vi phạm (Finding)",
        name_en="Audit Finding (Violation)",
        category="Audit Findings & Warnings",
        definition_vi="Bản ghi ghi nhận một vi phạm quy tắc kiểm toán hoặc chính sách tuân thủ đã được xác nhận trong quá trình thực thi, khiến dữ liệu bị chuyển vào trạng thái Cách ly (Quarantine).",
        definition_en="A formal record of a confirmed audit rule or policy violation during pipeline execution, resulting in affected records being routed to Quarantine.",
        aliases=["finding", "phát hiện", "vi phạm", "lỗi vi phạm", "violation", "findings"],
        details_vi="Mỗi Finding chứa mã quy tắc vi phạm, số lượng bản ghi bị ảnh hưởng, lý do vi phạm, làn thất bại (Failure Lane) và căn cứ pháp lý liên quan.",
        details_en="Each Finding includes rule ID, affected record count, failure reason, failure lane, and legal reference."
    ),
    "warning": GlossaryTerm(
        term_id="warning",
        name_vi="Bản ghi Cảnh báo (Warning)",
        name_en="Audit Warning (Non-blocking Anomaly Signal)",
        category="Audit Findings & Warnings",
        definition_vi="Bản ghi cảnh báo ghi nhận các dấu hiệu bất thường thống kê hoặc trôi dạt số liệu (L2–L4) để kiểm toán viên giám sát, không chặn luồng bản ghi và không đưa bản ghi vào cách ly.",
        definition_en="A non-blocking notification of a statistical anomaly or drift signal (L2–L4) flagged for auditor review without halting pipeline flow or quarantining records.",
        aliases=["warning", "cảnh báo", "dị thường", "dấu hiệu nghi ngờ", "anomaly signal", "warnings"],
        details_vi="Warning được trình bày theo cấu trúc hai lớp: Giải thích Nghiệp vụ (Business Explanation) và Thông số Kỹ thuật mở rộng (Technical Details).",
        details_en="Warnings are presented in a two-layer structure: default Business Explanation and collapsible Technical Details."
    ),
    "quarantine": GlossaryTerm(
        term_id="quarantine",
        name_vi="Khu vực Cách ly (Quarantine)",
        name_en="Quarantine Isolation Store",
        category="Data Protection & Remediation",
        definition_vi="Khu vực lưu trữ cô lập an toàn các bản ghi dữ liệu không đạt chuẩn kiểm toán kỹ thuật hoặc vi phạm chính sách pháp lý, nhằm bảo vệ tầng dữ liệu Silver khỏi bị nhiễm bẩn.",
        definition_en="The secure isolated storage holding records that failed technical audit or regulatory compliance rules, safeguarding the Silver layer against contamination.",
        aliases=["quarantine", "cách ly", "bản ghi cách ly", "vùng cách ly", "quarantine store"],
        details_vi="Các bản ghi trong Quarantine có thể được phân tích nguyên nhân gốc rễ (RCA) và khắc phục qua các quy tắc xử lý (Data Treatment Rules).",
        details_en="Quarantined records can undergo root cause analysis (RCA) and remediation via Data Treatment Rules."
    ),
    "hitl": GlossaryTerm(
        term_id="hitl",
        name_vi="Cơ chế Phê duyệt Con người (Human-In-The-Loop - HITL)",
        name_en="Human-In-The-Loop (HITL) Governance",
        category="Governance & Governance Protocols",
        definition_vi="Cơ chế kiểm soát bắt buộc phải có sự thẩm định và phê duyệt rõ ràng của người có thẩm quyền (Auditor / Admin) trước khi áp dụng các đề xuất quy tắc khắc phục (Treatment Rules) hoặc thực thi các thao tác nhạy cảm.",
        definition_en="Mandatory governance safeguard requiring explicit review and approval by authorized personnel (Auditor/Admin) before activating proposed treatment rules or executing privileged operations.",
        aliases=["hitl", "human in the loop", "phê duyệt người dùng", "phê duyệt thủ công", "kiểm soát con người"],
        details_vi="HITL đảm bảo AI chỉ đóng vai trò phân tích và đề xuất giải pháp, quyền quyết định tối hậu thuộc về kiểm toán viên con người.",
        details_en="HITL guarantees AI remains an advisory partner while final decision authority rests with human auditors."
    ),
    "data_treatment": GlossaryTerm(
        term_id="data_treatment",
        name_vi="Quy tắc Khắc phục Dữ liệu (Data Treatment Rule)",
        name_en="Data Treatment Rule (Remediation)",
        category="Data Protection & Remediation",
        definition_vi="Quy tắc chuẩn hóa hoặc biến đổi dữ liệu (như che mờ PII `mask_phone`, băm dữ liệu `hash_sha256`, làm tròn số `round_decimal`) nhằm sửa chữa các vi phạm để đưa bản ghi về trạng thái hợp lệ.",
        definition_en="Standardization or transformation rule (e.g., masking PII `mask_phone`, hashing `hash_sha256`, rounding `round_decimal`) designed to remediate violations and restore records to valid standing.",
        aliases=["data treatment", "treatment rule", "quy tắc xử lý", "quy tắc khắc phục", "treatment", "remediation rule"],
        details_vi="Mọi quy tắc Data Treatment mới được sinh ra từ AI đều trải qua bước chạy thử nghiệm (Dry-Run Microbenchmark) trước khi đưa vào hàng đợi phê duyệt HITL.",
        details_en="All new AI-proposed treatment rules undergo simulated Dry-Run microbenchmarks before entering the HITL queue."
    ),
    "sod": GlossaryTerm(
        term_id="sod",
        name_vi="Phân tách Trách nhiệm (Segregation of Duties - SoD)",
        name_en="Segregation of Duties (SoD / RACIX)",
        category="Access Control & ITGC",
        definition_vi="Nguyên tắc kiểm soát nội bộ và quản trị CNTT (ITGC) nhằm đảm bảo không có bất kỳ cá nhân nào nắm giữ các quyền hạn mâu thuẫn (như vừa khởi tạo vừa phê duyệt, hoặc vừa lập trình vừa kiểm toán hệ thống).",
        definition_en="Internal control and ITGC governance principle ensuring no single individual holds conflicting authorities (such as initiating and approving, or developing and auditing).",
        aliases=["sod", "segregation of duties", "phân tách trách nhiệm", "phân quyền sod", "racix", "ma trận sod"],
        details_vi="Hệ thống DataTrust quản lý SoD thông qua ma trận RACIX 14 vai trò ITGC và quy trình xét duyệt phiếu ủy quyền/xung đột lợi ích độc lập.",
        details_en="DataTrust governs SoD via a 14-role RACIX ITGC matrix and independent conflict approval workflows."
    )
}


# -----------------------------------------------------------------------------
# Lookup & Matching Helpers
# -----------------------------------------------------------------------------
def lookup_glossary_term(query: str) -> Optional[GlossaryTerm]:
    """
    Looks up a glossary term by exact ID, normalized alias, or keyword match.
    """
    if not query:
        return None
    
    clean_q = normalize_text_for_lookup(query)
    if not clean_q:
        return None

    # 1. Direct ID match
    if clean_q in GLOSSARY_REGISTRY:
        return GLOSSARY_REGISTRY[clean_q]

    # 2. Exact match against aliases
    for term in GLOSSARY_REGISTRY.values():
        for alias in term.aliases:
            if clean_q == normalize_text_for_lookup(alias):
                return term

    # 3. Substring match on aliases (longest alias match wins)
    best_term = None
    best_len = 0
    for term in GLOSSARY_REGISTRY.values():
        for alias in term.aliases:
            norm_alias = normalize_text_for_lookup(alias)
            if norm_alias and norm_alias in clean_q and len(norm_alias) > best_len:
                best_term = term
                best_len = len(norm_alias)

    return best_term


def suggest_closest_terms(query: str, limit: int = 3) -> List[GlossaryTerm]:
    """
    Finds closest terms in the glossary using string similarity matching.
    """
    if not query:
        return []
    clean_q = normalize_text_for_lookup(query)
    
    scored: List[tuple[float, GlossaryTerm]] = []
    seen_ids = set()

    for term in GLOSSARY_REGISTRY.values():
        # Score against term name and aliases
        candidates = [term.name_vi, term.name_en, term.term_id] + term.aliases
        best_score = 0.0
        for cand in candidates:
            norm_cand = normalize_text_for_lookup(cand)
            score = difflib.SequenceMatcher(None, clean_q, norm_cand).ratio()
            if score > best_score:
                best_score = score
        
        if best_score >= 0.35 and term.term_id not in seen_ids:
            scored.append((best_score, term))
            seen_ids.add(term.term_id)

    scored.sort(key=lambda x: x[0], reverse=True)
    return [term for _, term in scored[:limit]]


def get_all_terms() -> List[GlossaryTerm]:
    """Returns all available glossary terms."""
    return list(GLOSSARY_REGISTRY.values())


def format_term_response(term: GlossaryTerm) -> str:
    """Formats a canonical glossary term response in consistent markdown."""
    resp = (
        f"📖 **Định nghĩa Thuật ngữ: {term.name_vi}** ({term.name_en})\n\n"
        f"• **Phân loại**: {term.category}\n"
        f"• **Định nghĩa chuẩn**: {term.definition_vi}\n"
    )
    if term.details_vi:
        resp += f"• **Chi tiết vận hành**: {term.details_vi}\n"
    return resp.strip()
