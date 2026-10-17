"""
DataTrust OS: Multi-Tier Hybrid Intent Classifier
Combines normalized deterministic rule-matching with semantic classification fallback.
Supports multi-intent splitting and negation handling.
"""

import re
import unicodedata
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Any

logger = logging.getLogger("DataTrust.IntentClassifier")


class UserIntent(str, Enum):
    # Specialized DataTrust Governance Intents
    RUN_METRICS = "RUN_METRICS"
    DOMAIN_GLOSSARY = "DOMAIN_GLOSSARY"
    RUN_OVERVIEW = "RUN_OVERVIEW"
    ROOT_CAUSE_ONLY = "ROOT_CAUSE_ONLY"
    REMEDIATION_ONLY = "REMEDIATION_ONLY"
    BOTH_RCA_AND_REMEDIATION = "BOTH_RCA_AND_REMEDIATION"
    PIPELINE_ERROR_OR_PROGRESS = "PIPELINE_ERROR_OR_PROGRESS"
    DATA_OR_CATALOG_INQUIRY = "DATA_OR_CATALOG_INQUIRY"
    POLICY_OR_LEGAL_INQUIRY = "POLICY_OR_LEGAL_INQUIRY"
    RULE_INQUIRY = "RULE_INQUIRY"
    WARNING_INQUIRY = "WARNING_INQUIRY"
    TOPIC_SWITCH = "TOPIC_SWITCH"

    # Conversational (Strictly for greetings, pleasantries, small talk, bot intro)
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"

    # Default Fallback for out-of-scope or ungrounded queries
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ClassificationResult:
    intent: UserIntent
    confidence: float
    sub_intents: List[UserIntent] = field(default_factory=list)
    raw_query: str = ""
    normalized_query: str = ""
    glossary_term: Optional[str] = None
    metric_target: Optional[str] = None
    is_multi_intent: bool = False


def normalize_query_text(text: str) -> Tuple[str, str]:
    """
    Normalizes query text:
    - returns (cleaned_with_accents, unaccented_normalized)
    """
    if not text:
        return "", ""
    s = text.strip()
    # Normalize unicode to NFC
    s = unicodedata.normalize('NFC', s)
    # Remove excessive punctuation but keep spaces
    cleaned = re.sub(r'[\r\n\t]+', ' ', s)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Unaccented normalized form for robust matching
    nfkd = unicodedata.normalize('NFKD', cleaned.lower())
    unaccented = "".join([c for c in nfkd if not unicodedata.combining(c)])
    unaccented = re.sub(r'[^\w\s]', ' ', unaccented)
    unaccented = " ".join(unaccented.split())

    return cleaned, unaccented


class IntentClassifier:
    """Multi-Tier Intent Classifier for DataTrust OS."""

    # 1. TOPIC SWITCH PATTERNS
    TOPIC_SWITCH_PATTERNS = [
        r"b\u1ecf\s+qua\s+(chuy\u1ec7n|ch\u1ee7\s+\u0111\u1ec1|v\u1ea5n\s+\u0111\u1ec1|finding)\s+(n\u00e0y|\u0111\u00f3)",
        r"(chuy\u1ec3n|sang|n\u00f3i)\s+(ch\u1ee7\s+\u0111\u1ec1|chuy\u1ec7n)\s+kh\u00e1c",
        r"\b\u0111\u1ed5i\s+ch\u1ee7\s+\u0111\u1ec1\b",
        r"\b(reset|restart|b\u1eaft\s+\u0111\u1ea7u\s+l\u1ea1i|quay\s+v\u1ec1\s+\u0111\u1ea7u|quay\s+l\u1ea1i\s+t\u1eeb\s+\u0111\u1ea7u)\b",
        r"kh\u00f4ng\s+h\u1ecfi\s+v\u1ec1\s+(c\u00e1i|finding|l\u1ed7i|ch\u1ee7\s+\u0111\u1ec1)\s+n\u00e0y\s+n\u1eefa",
    ]

    # 2. STRICT GENERAL CONVERSATION (Only greetings, thanks, identity)
    # MUST NOT match business queries like "chào bạn, có bao nhiêu lỗi?"
    GREETING_PATTERNS = [
        r"^(xin\s+)?ch(à|a)o(\s+(bạn|ban|em|bot|trợ\s+lý|tro\s+ly|assistant))?[\s\!\?\.]*$",
        r"^(hi|hello|hey|chao|alo|good\s+morning|good\s+afternoon)(\s+(bạn|ban|bot|there|assistant))?[\s\!\?\.]*$",
        r"^(c(ả|a)m\s+(ơ|o)n|thank\s+you|thanks)(\s+(bạn|ban|bot|nhiều|nhieu|nhé|nhe|nha|a\s+lot|rất\s+nhiều|rat\s+nhieu))*[\s\!\?\.]*$",
        r"^b(ạ|a)n\s+(kh(ỏ|o)e\s+kh(ô|o)ng|th(ế|e)\s+n(à|a)o|how\s+are\s+you)[\s\!\?\.]*$",
        r"^gi(ú|u)p\s+t(ô|o)i(\s+v(ớ|o)i)?[\s\!\?\.]*$",
        r"^(b(ạ|a)n\s+l(à|a)\s+ai|b(ạ|a)n\s+t(ê|e)n\s+g(ì|i)|who\s+are\s+you)[\s\!\?\.]*$",
        r"^(b(ạ|a)n\s+(c(ó|o)\s+th(ể|e)\s+)?(l(à|a)m|gi(ú|u)p)\s+((\u0111|d)(ượ|uo)c\s+)?(nh(ữ|u)ng\s+)?g(ì|i)|what\s+can\s+you\s+do)[\s\!\?\.]*$",
        r"^(tr(ợ|o)\s+l(ý|y)|bot|h(ệ|e)\s+th(ố|o)ng)\s+c(ó|o)\s+(nh(ữ|u)ng\s+)?(t(í|i)nh\s+n(ă|a)ng|ch(ứ|u)c\s+n(ă|a)ng)\s+g(ì|i)[\s\!\?\.]*$",
        r"^(gi(ớ|o)i\s+thi(ệ|e)u|introduce)\s+(b(ả|a)n\s+th(â|a)n|v(ề|e)\s+b(ạ|a)n)[\s\!\?\.]*$",
    ]

    # 3. DOMAIN GLOSSARY PATTERNS
    GLOSSARY_QUESTION_PATTERNS = [
        r"(l(à|a)\s+g(ì|i)|ngh(ĩ|i)a\s+l(à|a)\s+g(ì|i)|what\s+is|what\s+are|define|(\u0111|d)(ị|i)nh\s+ngh(ĩ|i)a|kh(á|a)i\s+ni(ệ|e)m|gi(ả|a)i\s+th(í|i)ch\s+thu(ậ|a)t\s+ng(ữ|u))\b",
        r"\b(thu(ậ|a)t\s+ng(ữ|u)|glossary|kh(á|a)i\s+ni(ệ|e)m)\b",
        r"(ki(ể|e)m\s+tra\s+(c(á|a)i\s+)?g(ì|i)|ho(ạ|a)t\s+(\u0111|d)(ộ|o)ng\s+ra\s+sao|l(à|a)m\s+g(ì|i)|ph(á|a)t\s+hi(ệ|e)n\s+g(ì|i))\b",
        r"(kh(á|a)c\s+nhau\s+nh(ư|u)\s+th(ế|e)\s+n(à|a)o|kh(á|a)c\s+g(ì|i)|so\s+s(á|a)nh|difference\s+between)\b",
        r"^(gi(ả|a)i\s+th(í|i)ch|n(ó|o)i\s+v(ề|e)|th(ô|o)ng\s+tin\s+v(ề|e))\s+(silver|bronze|gold|l1|l2|l3|l4|lane\s+[ab]|l(à|a)n\s+[ab]|hitl|finding|warning|quarantine|c(á|a)ch\s+ly|sod|racix)[\s\!\?\.]*$",
        r"^(silver|bronze|gold|l1|l2|l3|l4|lane\s+[ab]|l(à|a)n\s+[ab]|hitl|finding|warning|quarantine|c(á|a)ch\s+ly|sod)\s+(l(à|a)\s+g(ì|i)|l(à|a)\s+sao|nh(ư|u)\s+th(ế|e)\s+n(à|a)o|la\s+gi)[\s\!\?\.]*$",
        r"^th(ế|e)\s+n(à|a)o\s+l(à|a)\s+(silver|bronze|b(ả|a)n\s+ghi\s+s(ạ|a)ch|l1|l2|l3|l4)[\s\!\?\.]*$",
    ]

    GLOSSARY_TERMS_SET = {
        "silver", "bronze", "gold", "l1", "l2", "l3", "l4", "lane a", "lane b", "lan a", "lan b",
        "l1 l4", "l1 den l4", "l1 toi l4", "hitl", "finding", "warning", "quarantine", "cach ly",
        "data treatment", "sod", "racix"
    }

    # Match semantic slots anywhere in a sentence instead of requiring one
    # exact Vietnamese word order (for example: "mấy record vào silver").
    QUANTITY_SLOT_PATTERNS = [
        r"\bbao\s+nhieu\b", r"\bmay\b", r"\bso\s+luong\b", r"\btong\s+so\b",
        r"\bcount\b", r"\bhow\s+many\b", r"\bty\s+le\b", r"\bphan\s+tram\b",
        r"\bpercentage\b", r"\brate\b", r"\byield\b",
    ]
    DATA_STATE_SLOT_PATTERNS = {
        "silver_count": [r"\bsilver\b", r"\bdu\s+lieu\s+sach\b", r"\bban\s+ghi\s+sach\b", r"\bdong\s+sach\b", r"\bdat\s+chuan\b", r"\bpass(?:ed)?\b"],
        "quarantine_count": [r"\bquarantine\b", r"\bcach\s+ly\b", r"\bbi\s+bat\b"],
        "warning_count": [r"\bwarning(?:s)?\b", r"\bcanh\s+bao\b"],
        "not_evaluated_count": [r"\bnot\s+evaluated\b", r"\bchua\s+danh\s+gia\b"],
        "scanned_count": [r"\bscanned\b", r"\bquet\b", r"\btong\s+ban\s+ghi\b", r"\btong\s+record(?:s)?\b"],
    }

    # 4. RUN METRICS PATTERNS (counts, rates, volumes, clean vs quarantine)
    RUN_METRICS_PATTERNS = [
        r"(bao\s+nhi(ê|e)u|m(ấ|a)y|count|how\s+many)\s+(d(ò|o)ng|b(ả|a)n\s+ghi|d(ữ|u)\s+li(ệ|e)u|m(ẫ|a)u|records?)?\s*(s(ạ|a)ch|(\u0111|d)(ạ|a)t\s+chu(ẩ|a)n|silver|pass|c(á|a)ch\s+ly|quarantine|warning|c(ả|a)nh\s+b(á|a)o|ch(ư|u)a\s+(\u0111|d)(á|a)nh\s+gi(á|a))",
        r"(s(ố|o)\s+l(ượ|uo)ng|s(ố|o)\s+d(ò|o)ng|s(ố|o)\s+b(ả|a)n\s+ghi|s(ố|o)\s+records?)\s+(s(ạ|a)ch|(\u0111|d)(ạ|a)t\s+chu(ẩ|a)n|silver|c(á|a)ch\s+ly|quarantine|warning|c(ả|a)nh\s+b(á|a)o)",
        r"(t(ỷ|y|ỉ|i)\s+l(ệ|e)|ph(ầ|a)n\s+tr(ă|a)m|percentage|rate|yield)\s+(d(ữ|u)\s+li(ệ|e)u\s+)?(s(ạ|a)ch|(\u0111|d)(ạ|a)t\s+chu(ẩ|a)n|silver|c(á|a)ch\s+ly|quarantine|warning|pass)",
        r"(c(ó|o)\s+)?(bao\s+nhi(ê|e)u|how\s+many)\s+.*(silver|s(ạ|a)ch|(\u0111|d)(ạ|a)t\s+chu(ẩ|a)n|c(á|a)ch\s+ly|quarantine|warning|b(ị|i)\s+b(ắ|a)t|b(ị|i)\s+l(ỗ|o)i)",
        r"\b(silver_count|quarantine_count|warning_count|scanned_count|not_evaluated_count)\b",
        r"(t(ổ|o)ng\s+s(ố|o)|s(ố|o))\s+(d(ò|o)ng|b(ả|a)n\s+ghi|records?)\s+(qu(é|e)t|scanned)",
        r"(qu(é|e)t|scanned)\s+(\u0111|d)(ượ|uo)c\s+bao\s+nhi(ê|e)u",
        r"\b(scanned\s+records?\s+count|scanned\s+count|records?\s+scanned)\b",
        r"\b(how\s+many|count|percentage|rate)\s+(silver|clean|quarantine|warning|passed|records?)\b",
    ]

    # 5. WARNING INQUIRY PATTERNS
    WARNING_PATTERNS = [
        r"\bwarning(s)?\b",
        r"c\u1ea3nh\s+b\u00e1o",
        r"b\u1ea3n\s+ghi\s+(warning|c\u1ea3nh\s+b\u00e1o)",
        r"s\u1ed1\s+(warning|c\u1ea3nh\s+b\u00e1o)",
        r"(t\u1ea1i\s+sao|l\u00fd\s+do|nguy\u00ean\s+nh\u00e2n).*(warning|c\u1ea3nh\s+b\u00e1o|d\u1ecb\s+th\u01b0\u1eddng)",
        r"(warning|c\u1ea3nh\s+b\u00e1o).*(vi\s+ph\u1ea1m|g\u00ec|t\u1ea1i\s+sao|l\u00e0\s+sao)",
    ]

    # 6. NEGATION PATTERNS FOR REMEDIATION
    NEGATION_REMEDIATION_PATTERNS = [
        r"kh\u00f4ng\s+(c\u1ea7n|ph\u1ea3i|mu\u1ed1n)\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|s\u1eeda|remediation|\u0111\u1ec1\s+xu\u1ea5t|x\u1eed\s+l\u00fd)",
        r"ch\u01b0a\s+c\u1ea7n\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|s\u1eeda|remediation|\u0111\u1ec1\s+xu\u1ea5t|x\u1eed\s+l\u00fd)",
        r"\u0111\u1eebng\s+(n\u00eau|\u0111\u1ec1\s+xu\u1ea5t|\u0111\u01b0a\s+ra)\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|remediation|ph\u01b0\u01a1ng\s+\u00e1n)",
        r"ch\u1ec9\s+(c\u1ea7n|h\u1ecfi|gi\u1ea3i\s+th\u00edch)\s+(nguy\u00ean\s+nh\u00e2n|l\u00fd\s+do|rca|t\u1ea1i\s+sao|v\u1ea5n\s+\u0111\u1ec1)",
        r"b\u1ecf\s+qua\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|remediation)",
    ]

    # 7. ROOT CAUSE PATTERNS
    ROOT_CAUSE_PATTERNS = [
        r"nguy\u00ean\s+nh\u00e2n",
        r"l\u00fd\s+do\s+(vi\s+ph\u1ea1m|b\u1ecb\s+l\u1ed7i|c\u00e1ch\s+ly|b\u1ecb\s+b\u1eaft)",
        r"t\u1ea1i\s+sao",
        r"\brca\b",
        r"\broot\s+cause\b",
        r"\bfinding\b",
        r"\b\u0111i\u1ec1u\s+tra\b",
        r"gi\u1ea3i\s+th\u00edch\s+(l\u1ed7i|vi\s+ph\u1ea1m|finding)",
        r"ph\u00e2n\s+t\u00edch\s+(nguy\u00ean\s+nh\u00e2n|vi\s+ph\u1ea1m|l\u1ed7i)",
    ]

    # 8. REMEDIATION PATTERNS
    REMEDIATION_ACTION_PATTERNS = [
        r"kh\u1eafc\s+ph\u1ee5c",
        r"gi\u1ea3i\s+ph\u00e1p",
        r"s\u1eeda\s+(nh\u01b0\s+th\u1ebf\s+n\u00e0o|l\u1ed7i|d\u1eef\s+li\u1ec7u)",
        r"c\u00e1ch\s+(x\u1eed\s+l\u00fd|gi\u1ea3i\s+quy\u1ebft|kh\u1eafc\s+ph\u1ee5c)",
        r"\bremediation\b",
        r"(\u0111\u1ec1\s+xu\u1ea5t|t\u1ea1o|th\u00eam|sinh|s\u1eeda|c\u1ea7n\s+s\u1eeda|mu\u1ed1n\s+\u00e1p\s+d\u1ee5ng|h\u00e3y\s+\u00e1p\s+d\u1ee5ng)\s+(rule|quy\s+t\u1eafc|treatment|x\u1eed\s+l\u00fd|h\u00e0nh\s+\u0111\u1ed9ng)",
        r"l\u00e0m\s+sao\s+\u0111\u1ec3\s+h\u1ebft\s+l\u1ed7i",
    ]

    # 9. PIPELINE EXECUTION PATTERNS
    PIPELINE_ERROR_PATTERNS = [
        r"b\u01b0\u1edbc\s+n\u00e0y\s+\u0111ang\s+l\u00e0m\s+g\u00ec",
        r"(l\u1ed7i\s+pipeline|pipeline\s+(b\u1ecb\s+)?l\u1ed7i)",
        r"(step|b\u01b0\u1edbc)\s+(b\u1ecb\s+l\u1ed7i|failed|stalled|d\u1eebng)",
        r"ti\u1ebfn\s+\u0111\u1ed9\s+(pipeline|ch\u1ea1y)",
        r"t\u1ea1i\s+sao\s+pipeline\s+(d\u1eebng|b\u1ecb\s+l\u1ed7i)",
        r"event\s+log",
        r"nh\u1eadt\s+k\u00fd\s+th\u1ef1c\s+thi",
    ]

    # 10. RUN OVERVIEW PATTERNS
    RUN_OVERVIEW_PATTERNS = [
        r"t\u1ed5ng\s+quan(\s+l\u1ea7n\s+ch\u1ea1y)?",
        r"t\u00ecnh\s+h\u00ecnh\s+l\u1ea7n\s+ch\u1ea1y",
        r"k\u1ebft\s+qu\u1ea3\s+(l\u1ea7n\s+ch\u1ea1y|run)",
        r"t\u00f3m\s+t\u1eaft\s+run",
        r"run\s+(n\u00e0y|overview)",
    ]

    # 11. DATA CATALOG PATTERNS
    DATA_OR_CATALOG_PATTERNS = [
        r"(b\u1ea3ng|dataset|table)\s+([a-zA-Z0-9_-]+|\u0111ang\s+ch\u1ea1y)\s+(c\u00f3\s+nh\u1eefng\s+c\u1ed9t\s+n\u00e0o|c\u1ea5u\s+tr\u00fac|schema)",
        r"(th\u00f4ng\s+tin|danh\s+s\u00e1ch)\s+(c\u1ed9t|b\u1ea3ng|dataset|catalog|columns)",
        r"profiling\s+(c\u1ee7a\s+)?(dataset|b\u1ea3ng|c\u1ed9t|d\u1eef\s+li\u1ec7u)",
        r"(t\u1ef7\s+l\u1ec7|th\u1ed1ng\s+k\u00ea)\s+(null|tr\u1ed1ng|d\u1eef\s+li\u1ec7u)",
        r"catalog\s+(c\u00f3\s+g\u00ec|d\u1eef\s+li\u1ec7u)",
    ]

    # 12. POLICY / LEGAL PATTERNS
    POLICY_OR_LEGAL_PATTERNS = [
        r"ngh\u1ecb\s+\u0111\u1ecbnh\s+13",
        r"lu\u1eadt\s+(91|an\s+ninh\s+m\u1ea1ng|b\u1ea3o\s+v\u1ec7\s+d\u1eef\s+li\u1ec7u)",
        r"\b(gdpr|sox|sox-404|hipaa|ccpa)\b",
        r"(ch\u00ednh\s+s\u00e1ch|quy\s+\u0111\u1ecbnh)\s+(tu\u00e2n\s+th\u1ee7|b\u1ea3o\s+m\u1eadt|compliance)",
        r"ti\u00eau\s+chu\u1ea9n\s+(ph\u00e1p\s+l\u00fd|ki\u1ec3m\s+to\u00e1n)",
    ]

    # 13. RULE INQUIRY PATTERNS
    RULE_INQUIRY_PATTERNS = [
        r"(quy\s+t\u1eafc|rules?)\s+[a-zA-Z0-9_-]+\s+(l\u00e0\s+g\u00ec|ki\u1ec3m\s+tra\s+g\u00ec|ho\u1ea1t\s+\u0111\u1ed9ng\s+nh\u01b0\s+th\u1ebf\s+n\u00e0o|nh\u01b0\s+th\u1ebf\s+n\u00e0o)",
        r"(th\u00f4ng\s+tin|chi\s+ti\u1ebft|gi\u1ea3i\s+th\u00edch|n\u00f3i|cho\s+bi\u1ebft)(\s+cho\s+t\u00f4i)?\s+(v\u1ec1\s+)?(rules?|quy\s+t\u1eafc)",
        r"(gi\u1ea3i\s+th\u00edch|chi\s+ti\u1ebft|\u0111\u1ecbnh\s+ngh\u0129a|n\u1ed9i\s+dung)\s+(c\u1ee7a\s+)?(rules?|quy\s+t\u1eafc)",
        r"(danh\s+s\u00e1ch|c\u00f3\s+nh\u1eefng|tra\s+c\u1ee9u)\s+([a-zA-Z0-9\s_\u00c0-\u1ef9]*)(rules?|quy\s+t\u1eafc)",
        r"\b(compliance|treatment|reliability)\s+rules?\b",
        r"treatment\s+rules?\s+(n\u00e0o|g\u00ec|hi\u1ec7n\s+c\u00f3|trong\s+h\u1ec7\s+th\u1ed1ng)",
        r"(l\u1ea7n\s+ch\u1ea1y|run)\s+(n\u00e0y\s+)?(\u0111\u00e3\s+)?(\u00e1p\s+d\u1ee5ng|ch\u1ea1y|th\u1ef1c\s+thi)\s+(nh\u1eefng\s+)?(rules?|quy\s+t\u1eafc)",
        r"(nh\u1eefng\s+)?(rules?|quy\s+t\u1eafc)\s+(n\u00e0o\s+)?(\u0111\u00e3\s+)?(ch\u1ea1y|th\u1ef1c\s+thi|\u00e1p\s+d\u1ee5ng|\u0111\u01b0\u1ee3c\s+\u00e1p\s+d\u1ee5ng)",
        r"(quy\s+t\u1eafc|rules?)\s+(ki\u1ec3m\s+tra|tu\u00e2n\s+th\u1ee7|x\u1eed\s+l\u00fd|treatment|reliability|compliance)",
        r"^\s*(rules?|quy\s+t\u1eafc)\s+[a-zA-Z0-9_-]+[\s\?\!\.]*$",
        r"\b(comp|chk|rel|drift|changepoint|treatment|val|trt|pol|l1|l2)-[a-zA-Z0-9_-]+\b",
    ]

    @classmethod
    def _split_multi_clauses(cls, text: str) -> List[str]:
        """
        Splits a compound question by explicit coordinating conjunctions ('và', 'đồng thời', 'cũng như', 'and', '&').
        Does not split on commas to avoid breaking subordinate clauses.
        Does not split comparison questions (e.g. 'Lane A và Lane B khác nhau như thế nào?').
        """
        if re.search(r"(kh(á|a)c\s+nhau|kh(á|a)c\s+g(ì|i)|so\s+s(á|a)nh|difference)", text, re.IGNORECASE):
            return [text]
        raw_clauses = re.split(r'\s+(?:v\u00e0|\u0111\u1ed3ng\s+th\u1eddi|c\u0169ng\s+nh\u01b0|and|\&)\s+', text)
        clauses = [c.strip() for c in raw_clauses if len(c.strip()) >= 3]
        return clauses if len(clauses) > 1 else [text]

    @classmethod
    def _classify_single_clause(cls, text: str, unaccented: str) -> Tuple[UserIntent, float, Optional[str], Optional[str]]:
        """
        Classifies a single clause using deterministic prioritized rules.
        Returns (intent, confidence, glossary_term, metric_target).
        """
        # 1. Topic Switch
        if any(re.search(p, text, re.IGNORECASE) for p in cls.TOPIC_SWITCH_PATTERNS):
            return UserIntent.TOPIC_SWITCH, 0.98, None, None

        # 2. Strict Greetings / Pleasantries
        if any(re.search(p, text, re.IGNORECASE) or re.search(p, unaccented, re.IGNORECASE) for p in cls.GREETING_PATTERNS):
            return UserIntent.GENERAL_CONVERSATION, 0.99, None, None

        # Semantic slots: quantity/rate + a governed record state. Tokens may
        # be separated by natural connector words and may appear in any order.
        has_quantity_slot = any(re.search(p, unaccented) for p in cls.QUANTITY_SLOT_PATTERNS)
        metric_slot = next((
            target for target, patterns in cls.DATA_STATE_SLOT_PATTERNS.items()
            if any(re.search(p, unaccented) for p in patterns)
        ), None)
        if has_quantity_slot and metric_slot:
            return UserIntent.RUN_METRICS, 0.97, None, metric_slot

        # A layer range describes the detector suite, not a rule identifier.
        layer_range = bool(
            re.search(r"\bl1\s*(?:[-\u2013\u2014]|den|toi|to)\s*l4\b", text, re.IGNORECASE)
            or re.search(r"\bl1\s+(?:den\s+|toi\s+|to\s+)?l4\b", unaccented)
        )
        definition_cue = bool(re.search(
            r"\b(la\s+gi|nghia|dinh\s+nghia|giai\s+thich|what\s+(?:is|are)|define|hoat\s+dong|kiem\s+tra)\b",
            unaccented,
        ))
        if layer_range and definition_cue:
            return UserIntent.DOMAIN_GLOSSARY, 0.99, "detector_levels", None

        # 3. Rule Inquiry with explicit code/ID (e.g. "Rule L1-01 là gì?", "POL-VN-01", "rule CHK-01")
        # Must take precedence over glossary so "L1-01" is not misidentified as "L1" glossary concept
        has_rule_code = bool(re.search(r"\b(comp|chk|rel|drift|changepoint|treatment|val|trt|pol|l1|l2)-[a-zA-Z0-9_-]+\b", text, re.IGNORECASE))
        has_rule_keyword = bool(re.search(r"^\s*(rules?|quy\s+t\u1eafc)\s+[a-zA-Z0-9_-]+", text, re.IGNORECASE))
        if has_rule_code or has_rule_keyword:
            return UserIntent.RULE_INQUIRY, 0.98, None, None

        # 4. Domain Glossary: "Silver là gì", "L1 là gì", "Finding là gì", "Warning trong DataTrust là gì", "L3 detector kiểm tra cái gì"
        # Must take precedence over generic RCA / Warning patterns when asking for concept definition
        from backend.ai.domain.glossary import lookup_glossary_term
        found_term = lookup_glossary_term(text)
        is_glossary_question = any(re.search(p, text, re.IGNORECASE) or re.search(p, unaccented, re.IGNORECASE) for p in cls.GLOSSARY_QUESTION_PATTERNS)

        if is_glossary_question and found_term:
            return UserIntent.DOMAIN_GLOSSARY, 0.96, found_term.term_id, None

        # Also check unaccented words against known terms
        if is_glossary_question:
            matched_key = None
            for t in cls.GLOSSARY_TERMS_SET:
                if re.search(rf"\b{re.escape(t)}\b", unaccented):
                    term_obj = lookup_glossary_term(t)
                    if term_obj:
                        matched_key = term_obj.term_id
                        break
            if matched_key:
                return UserIntent.DOMAIN_GLOSSARY, 0.95, matched_key, None

        # 5. Run Metrics: Count, rate, silver vs quarantine
        is_metrics_question = any(re.search(p, text, re.IGNORECASE) or re.search(p, unaccented, re.IGNORECASE) for p in cls.RUN_METRICS_PATTERNS)
        if is_metrics_question:
            target = "silver_count" if any(w in unaccented for w in ("silver", "sach", "dat chuan", "pass")) else "general_metrics"
            if any(w in unaccented for w in ("cach ly", "quarantine", "bi bat", "vi pham")):
                target = "quarantine_count"
            elif any(w in unaccented for w in ("warning", "canh bao")):
                target = "warning_count"
            return UserIntent.RUN_METRICS, 0.95, None, target

        # 6. Pipeline Execution Errors / Progress (must take precedence over RCA keywords like 'tại sao', 'lỗi')
        if any(re.search(p, text, re.IGNORECASE) for p in cls.PIPELINE_ERROR_PATTERNS):
            return UserIntent.PIPELINE_ERROR_OR_PROGRESS, 0.95, None, None

        # 7. Warning Inquiry (e.g. "Tại sao có 200 warning?", "Bản ghi warning này vi phạm gì?")
        if any(re.search(p, text, re.IGNORECASE) for p in cls.WARNING_PATTERNS):
            return UserIntent.WARNING_INQUIRY, 0.94, None, None

        # 8. Root Cause and Remediation with Negation Awareness
        has_remediation_negation = any(re.search(p, text, re.IGNORECASE) for p in cls.NEGATION_REMEDIATION_PATTERNS)
        has_root_cause_intent = any(re.search(p, text, re.IGNORECASE) for p in cls.ROOT_CAUSE_PATTERNS)
        has_remediation_action = any(re.search(p, text, re.IGNORECASE) for p in cls.REMEDIATION_ACTION_PATTERNS)

        if has_remediation_negation:
            if has_root_cause_intent:
                return UserIntent.ROOT_CAUSE_ONLY, 0.98, None, None
            return UserIntent.UNSUPPORTED, 0.40, None, None

        if has_root_cause_intent and has_remediation_action:
            return UserIntent.BOTH_RCA_AND_REMEDIATION, 0.96, None, None

        if has_remediation_action and not has_root_cause_intent:
            return UserIntent.REMEDIATION_ONLY, 0.94, None, None

        if has_root_cause_intent:
            return UserIntent.ROOT_CAUSE_ONLY, 0.93, None, None

        # 9. General Rule Inquiry without ID
        if any(re.search(p, text, re.IGNORECASE) for p in cls.RULE_INQUIRY_PATTERNS):
            return UserIntent.RULE_INQUIRY, 0.96, None, None

        # 10. Policy / Legal inquiry (general regulatory framework)
        if any(re.search(p, text, re.IGNORECASE) for p in cls.POLICY_OR_LEGAL_PATTERNS):
            return UserIntent.POLICY_OR_LEGAL_INQUIRY, 0.92, None, None

        # 11. Data / Catalog inquiry
        if any(re.search(p, text, re.IGNORECASE) for p in cls.DATA_OR_CATALOG_PATTERNS):
            return UserIntent.DATA_OR_CATALOG_INQUIRY, 0.91, None, None

        # 12. Run Overview
        if any(re.search(p, text, re.IGNORECASE) for p in cls.RUN_OVERVIEW_PATTERNS):
            return UserIntent.RUN_OVERVIEW, 0.90, None, None

        # 13. Direct single-term lookup: If query is simply "Silver", "L1", "L4", "HITL"
        if found_term and len(unaccented.split()) <= 4:
            return UserIntent.DOMAIN_GLOSSARY, 0.88, found_term.term_id, None

        # DEFAULT FALLBACK: UNSUPPORTED (Never automatically fall back to GENERAL_CONVERSATION!)
        return UserIntent.UNSUPPORTED, 0.40, None, None

    @classmethod
    def classify_full(cls, message: str, llm_adapter: Optional[Any] = None) -> ClassificationResult:
        """
        Full multi-tier classification:
        1. Normalizes text (case, accents, punctuation).
        2. Detects multi-intent compound queries (e.g. 'Silver là gì và run này có bao nhiêu dòng đạt chuẩn?').
        3. Evaluates priority rules.
        4. If confidence is low or ambiguous, performs semantic classifier fallback if LLM is available.
        """
        raw_text = (message or "").strip()
        if not raw_text:
            return ClassificationResult(
                intent=UserIntent.UNSUPPORTED,
                confidence=0.0,
                raw_query="",
                normalized_query=""
            )

        cleaned, unaccented = normalize_query_text(raw_text)

        # 1. First check if entire query is BOTH_RCA_AND_REMEDIATION or single high-confidence intent
        whole_intent, whole_conf, whole_term, whole_metric = cls._classify_single_clause(cleaned, unaccented)
        if whole_intent == UserIntent.BOTH_RCA_AND_REMEDIATION:
            return ClassificationResult(
                intent=UserIntent.BOTH_RCA_AND_REMEDIATION,
                confidence=whole_conf,
                sub_intents=[UserIntent.ROOT_CAUSE_ONLY, UserIntent.REMEDIATION_ONLY],
                raw_query=raw_text,
                normalized_query=unaccented,
                is_multi_intent=True
            )

        # 2. Check for multi-clause compound questions (e.g. 'Silver là gì và có bao nhiêu dòng sạch?')
        clauses = cls._split_multi_clauses(cleaned)
        if len(clauses) > 1:
            clause_results = []
            for c in clauses:
                c_clean, c_unacc = normalize_query_text(c)
                c_intent, c_conf, c_term, c_metric = cls._classify_single_clause(c_clean, c_unacc)
                if c_intent != UserIntent.UNSUPPORTED:
                    clause_results.append((c_intent, c_conf, c_term, c_metric))

            if len(clause_results) >= 2:
                # Compound multi-intent found!
                sub_intents = [cr[0] for cr in clause_results]
                if UserIntent.ROOT_CAUSE_ONLY in sub_intents and UserIntent.REMEDIATION_ONLY in sub_intents:
                    primary_intent = UserIntent.BOTH_RCA_AND_REMEDIATION
                else:
                    primary_intent = clause_results[0][0]

                glossary_term = next((cr[2] for cr in clause_results if cr[2]), None)
                metric_target = next((cr[3] for cr in clause_results if cr[3]), None)
                return ClassificationResult(
                    intent=primary_intent,
                    confidence=0.95,
                    sub_intents=sub_intents,
                    raw_query=raw_text,
                    normalized_query=unaccented,
                    glossary_term=glossary_term,
                    metric_target=metric_target,
                    is_multi_intent=True
                )

        # Single clause evaluation (use whole query evaluation)
        intent, conf, glossary_term, metric_target = whole_intent, whole_conf, whole_term, whole_metric

        # Optional Semantic LLM Classifier if rule was inconclusive and LLM is present
        if conf < 0.60 and llm_adapter is not None:
            semantic_intent = cls._semantic_classify(raw_text, llm_adapter)
            if semantic_intent and semantic_intent != UserIntent.UNSUPPORTED:
                intent = semantic_intent
                conf = 0.82

        return ClassificationResult(
            intent=intent,
            confidence=conf,
            sub_intents=[intent],
            raw_query=raw_text,
            normalized_query=unaccented,
            glossary_term=glossary_term,
            metric_target=metric_target,
            is_multi_intent=False
        )

    @classmethod
    def _semantic_classify(cls, message: str, llm_adapter: Any) -> Optional[UserIntent]:
        """
        Lightweight closed-set semantic classification with strict timeout.
        Falls back safely to None on any error or timeout.
        """
        try:
            allowed_intents = [e.value for e in UserIntent]
            sys_inst = (
                "You are an intent classifier for DataTrust OS governance queries. "
                "Classify the user message into exactly ONE of the following valid intents:\n"
                f"{', '.join(allowed_intents)}.\n"
                "Return ONLY the exact intent name. If not related to DataTrust, return UNSUPPORTED."
            )
            # Short prompt, temperature 0.0, max_tokens 20
            res = llm_adapter.complete(
                prompt=f"Message: {message}\nIntent:",
                system_instruction=sys_inst,
                temperature=0.0,
                max_tokens=20
            )
            text = (res.get("text") or "").strip().upper()
            # Match against enum
            for e in UserIntent:
                if e.value in text:
                    return e
        except Exception as e:
            logger.debug(f"Semantic intent classification fallback skipped: {e}")
        return None

    @classmethod
    def classify_detailed(cls, message: str, llm_adapter: Any = None) -> ClassificationResult:
        """
        Alias for classify_full returning complete ClassificationResult.
        """
        return cls.classify_full(message, llm_adapter=llm_adapter)

    @classmethod
    def classify(cls, message: str) -> UserIntent:
        """
        Backward-compatible entry point: returns primary UserIntent enum.
        """
        res = cls.classify_full(message)
        return res.intent
