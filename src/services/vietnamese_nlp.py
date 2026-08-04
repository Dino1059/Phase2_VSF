from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field


@dataclass
class Aspect:
    component: str  # 'charger', 'battery', 'vehicle', 'app', 'driver', 'service'
    location: str | None = None
    symptom: str = ''
    severity: str = 'medium'  # 'critical', 'high', 'medium', 'low'


@dataclass
class NLPResult:
    original_text: str
    normalized_text: str
    language: str  # 'vi', 'en', 'mixed'
    teencode_found: list[str] = field(default_factory=list)
    aspects: list[Aspect] = field(default_factory=list)
    sentiment: float = 0.0  # -1.0 to 1.0
    confidence: float = 0.0  # 0.0 to 1.0

    def __getitem__(self, item: str):
        if item == "sentiment":
            if self.sentiment <= -0.5:
                return "very_negative"
            elif self.sentiment < 0:
                return "negative"
            elif self.sentiment >= 0.5:
                return "very_positive"
            elif self.sentiment > 0:
                return "positive"
            return "neutral"
        return getattr(self, item)


class VietnameseNLPService:
    def __init__(self, teencode_path: str | None = None, ontology_path: str | None = None):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.teencode_path = teencode_path or os.path.join(base, 'src', 'data', 'teencode_dict.json')
        self.ontology_path = ontology_path or os.path.join(base, 'src', 'data', 'ev_domain_ontology.json')
        self._teencode: dict[str, str] = {}
        self._ontology: dict = {}
        self._load_data()
        # Pre-compile regex for teen-code: sort by length descending for greedy matching
        self._teencode_pattern = self._build_teencode_pattern()
        # Sentiment lexicon (basic Vietnamese + English)
        self._positive_words = {
            'tốt', 'tuyệt', 'tuyệt vời', 'đẹp', 'nhanh', 'sạch', 'rẻ', 'tiện',
            'hay', 'đỉnh', 'chất', 'phê', 'thích', 'ổn', 'ok', 'ngon', 'mát',
            'recommend', 'perfect', 'good', 'nice', 'great', 'excellent', 'love',
            'hài lòng', 'chuyên nghiệp', 'lịch sự', 'an toàn', 'khuyên dùng'
        }
        self._negative_words = {
            'tệ', 'dở', 'chậm', 'nóng', 'lỗi', 'hỏng', 'chán', 'lag', 'crash',
            'bug', 'scam', 'lừa', 'phí', 'nguy hiểm', 'cháy', 'nổ', 'liệt',
            'không được', 'kém', 'tồi', 'đắt', 'mất', 'treo', 'giật', 'khó chịu',
            'bực', 'thất vọng', 'tệ hại', 'kinh khủng'
        }

    def _load_data(self):
        if os.path.exists(self.teencode_path):
            with open(self.teencode_path, 'r', encoding='utf-8') as f:
                self._teencode = json.load(f)
        if os.path.exists(self.ontology_path):
            with open(self.ontology_path, 'r', encoding='utf-8') as f:
                self._ontology = json.load(f)

    def _build_teencode_pattern(self) -> re.Pattern | None:
        if not self._teencode:
            return None
        # Sort by length descending so longer matches are preferred
        keys = sorted(self._teencode.keys(), key=len, reverse=True)
        escaped = [re.escape(k) for k in keys]
        pattern = r'(?:^|\b|(?<=\s))(' + '|'.join(escaped) + r')(?:$|\b|(?=\s))'
        return re.compile(pattern, re.IGNORECASE)

    def normalize(self, text: str) -> str:
        """Normalize teen-code to standard Vietnamese."""
        if not text or not self._teencode:
            return text
        result = text
        found = []
        # Apply longest-first replacement
        for key in sorted(self._teencode.keys(), key=len, reverse=True):
            pattern = re.compile(r'(?:^|(?<=\s))' + re.escape(key) + r'(?:$|(?=\s))', re.IGNORECASE)
            if pattern.search(result):
                found.append(key)
                result = pattern.sub(self._teencode[key], result)
        # Clean up extra whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        return result

    def detect_language(self, text: str) -> str:
        """Detect language: 'vi', 'en', or 'mixed'."""
        vietnamese_chars = set('àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ')
        has_vi = any(c in vietnamese_chars for c in text.lower())
        # Simple heuristic: if more than 50% ASCII words, likely mixed/en
        words = text.split()
        ascii_words = sum(1 for w in words if all(ord(c) < 128 for c in w))
        if not has_vi and ascii_words == len(words):
            return 'en'
        elif has_vi and ascii_words / max(len(words), 1) > 0.5:
            return 'mixed'
        return 'vi'

    def extract_aspects(self, text: str) -> list[Aspect]:
        """Extract structured aspects from normalized text."""
        aspects = []
        text_lower = text.lower()
        components = self._ontology.get('components', {})
        severity_keywords = self._ontology.get('severity_keywords', {})
        locations = self._ontology.get('locations', {})

        # Detect components
        detected_components = []
        for comp_name, comp_data in components.items():
            all_keywords = comp_data.get('keywords_vi', []) + comp_data.get('keywords_en', [])
            for kw in all_keywords:
                if kw.lower() in text_lower:
                    detected_components.append(comp_name)
                    break

        # Detect severity
        detected_severity = 'medium'
        for sev, keywords in severity_keywords.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    detected_severity = sev
                    break
            if detected_severity != 'medium':
                break

        # Detect location
        detected_location = None
        for region, locs in locations.items():
            for loc in locs:
                if loc.lower() in text_lower:
                    detected_location = loc
                    break
            if detected_location:
                break

        # Build aspects
        if not detected_components:
            detected_components = ['service']  # default if no component found

        for comp in detected_components:
            aspects.append(Aspect(
                component=comp,
                location=detected_location,
                symptom=text[:100],  # first 100 chars as symptom summary
                severity=detected_severity
            ))

        return aspects

    def compute_sentiment(self, text: str) -> tuple[float, float]:
        """Compute sentiment score and confidence.
        Returns (sentiment: -1.0..1.0, confidence: 0.0..1.0)"""
        text_lower = text.lower()
        words = set(re.findall(r'\w+', text_lower))
        # Also check multi-word expressions
        pos_count = sum(1 for w in self._positive_words if w in text_lower)
        neg_count = sum(1 for w in self._negative_words if w in text_lower)
        total = pos_count + neg_count
        if total == 0:
            return 0.0, 0.3  # neutral, low confidence
        sentiment = (pos_count - neg_count) / total
        confidence = min(total / 5.0, 1.0)  # More words = higher confidence
        return round(sentiment, 3), round(confidence, 3)

    def find_teencode(self, text: str) -> list[str]:
        """Find all teen-code tokens in text."""
        found = []
        text_lower = text.lower()
        for key in sorted(self._teencode.keys(), key=len, reverse=True):
            pattern = re.compile(r'(?:^|(?<=\s))' + re.escape(key) + r'(?:$|(?=\s))', re.IGNORECASE)
            if pattern.search(text_lower):
                found.append(key)
        return found

    def analyze(self, text: str) -> NLPResult:
        """Full NLP analysis pipeline."""
        teencode_found = self.find_teencode(text)
        normalized = self.normalize(text)
        language = self.detect_language(text)
        aspects = self.extract_aspects(normalized)
        sentiment, confidence = self.compute_sentiment(normalized)
        return NLPResult(
            original_text=text,
            normalized_text=normalized,
            language=language,
            teencode_found=teencode_found,
            aspects=aspects,
            sentiment=sentiment,
            confidence=confidence
        )

    def batch_analyze(self, texts: list[str]) -> list[NLPResult]:
        """Batch analyze multiple texts."""
        return [self.analyze(t) for t in texts]
