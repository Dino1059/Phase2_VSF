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
    VIETNAMESE_DIACRITICS = set('àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ')

    def __init__(self, teencode_path: str | None = None, ontology_path: str | None = None):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.teencode_path = teencode_path or os.path.join(base, 'src', 'data', 'teencode_dict.json')
        self.ontology_path = ontology_path or os.path.join(base, 'src', 'data', 'ev_domain_ontology.json')
        self._teencode: dict[str, str] = {}
        self._ontology: dict = {}
        self._load_data()

        # Negation terms
        self._negation_terms = {'không', 'chưa', 'chả', 'đéo', 'khôg', 'k', 'ko', 'khg', 'kg', 'hok', 'hong', 'hông', 'dek'}

        # Sentiment lexicon
        self._positive_words = {
            'tốt', 'tuyệt', 'tuyệt vời', 'đẹp', 'nhanh', 'sạch', 'rẻ', 'tiện',
            'hay', 'đỉnh', 'chất', 'phê', 'thích', 'ổn', 'ok', 'ngon', 'mát',
            'recommend', 'perfect', 'good', 'nice', 'great', 'excellent', 'love',
            'hài lòng', 'chuyên nghiệp', 'lịch sự', 'an toàn', 'khuyên dùng',
            'mượt', 'êm', 'sạc được', 'hoạt động', 'uy tín', 'chạy', 'xuất sắc'
        }
        self._negative_words = {
            'tệ', 'dở', 'chậm', 'nóng', 'lỗi', 'hỏng', 'chán', 'lag', 'crash',
            'bug', 'scam', 'lừa', 'phí', 'nguy hiểm', 'cháy', 'nổ', 'liệt',
            'không được', 'kém', 'tồi', 'đắt', 'mất', 'treo', 'giật', 'khó chịu',
            'bực', 'thất vọng', 'tệ hại', 'kinh khủng', 'hỏng hóc', 'ức chế', 'chập',
            'chai pin', 'tuột', 'tụt'
        }

        # Preserved words that naturally have double letters
        self._preserved_double_chars = {
            'app', 'pass', 'boss', 'less', 'loss', 'coop', 'free', 'see', 'feed',
            'css', 'wifi', '4g', '5g', 'ios', 'android', 'error', 'reset', 'reboot'
        }

    def _load_data(self):
        if os.path.exists(self.teencode_path):
            with open(self.teencode_path, 'r', encoding='utf-8') as f:
                self._teencode = json.load(f)
        if os.path.exists(self.ontology_path):
            with open(self.ontology_path, 'r', encoding='utf-8') as f:
                self._ontology = json.load(f)

    def tokenize(self, text: str) -> list[str]:
        """Punctuation-aware tokenization handling !, ?, ., , cleanly without stripping word boundaries."""
        if not text:
            return []
        pattern = r'([!?,.;:])'
        spaced = re.sub(pattern, r' \1 ', text)
        return [t.strip() for t in spaced.split() if t.strip()]

    def reduce_repeated_chars(self, text: str) -> str:
        """Normalize repeated character elongation (e.g. 'nhanhhh' -> 'nhanh', 'okkk' -> 'ok', 'laaag' -> 'lag')."""
        if not text:
            return text

        def _fix_word(word: str) -> str:
            if len(word) <= 1:
                return word
            if word.lower() in self._preserved_double_chars:
                return word

            # First: reduce 3+ repeated identical letters to 1
            w = re.sub(
                r'([a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ])\1{2,}',
                r'\1',
                word,
                flags=re.IGNORECASE
            )
            # Second: reduce double consonants for non-preserved words
            w = re.sub(r'([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ])\1+', r'\1', w)
            # Third: reduce double vowels if resulting word isn't in preserved/teencode dict
            if w.lower() not in self._preserved_double_chars and w.lower() not in self._teencode:
                w = re.sub(r'([aeiouyAEIOUY])\1+', r'\1', w)
            return w

        # Split preserving punctuation tokens
        tokens = re.split(r'(\s+|[!?,.;:])', text)
        processed = [
            _fix_word(t) if t.strip() and not re.match(r'^[!?,.;:]+$', t) else t
            for t in tokens
        ]
        return ''.join(processed)

    def is_accentless(self, text: str) -> bool:
        """Detect if input text is accentless Vietnamese."""
        if not text or not text.strip():
            return False
        text_lower = text.lower()
        has_vi_diacritics = any(c in self.VIETNAMESE_DIACRITICS for c in text_lower)
        if has_vi_diacritics:
            return False

        # Check if words match accentless dictionary keys or teencode entries
        words = re.findall(r'\w+', text_lower)
        if not words:
            return False

        accentless_matches = sum(
            1 for w in words if w in self._teencode or w in {
                'khong', 'sac', 'dc', 'tram', 'tru', 'loi', 'hong', 'tot', 'dep',
                'te', 're', 'tien', 'cham', 'nong', 'dat', 'mat', 'pin', 'xe'
            }
        )
        return accentless_matches > 0

    def normalize(self, text: str) -> str:
        """Normalize teen-code, accentless Vietnamese, and repeated characters."""
        if not text:
            return text

        # Step 1: Reduce repeated characters
        result = self.reduce_repeated_chars(text)

        if not self._teencode:
            return result

        # Step 2: Ensure space around punctuation before dictionary lookup so word boundaries match
        result = re.sub(r'([!?,.;:])', r' \1 ', result)

        # Step 3: Replace teen-code and accentless mappings (longest first)
        found = []
        for key in sorted(self._teencode.keys(), key=len, reverse=True):
            pattern = re.compile(r'(?:^|(?<=\s))' + re.escape(key) + r'(?:$|(?=\s))', re.IGNORECASE)
            if pattern.search(result):
                found.append(key)
                result = pattern.sub(self._teencode[key], result)

        # Step 4: Clean up punctuation spacing
        result = re.sub(r'\s+([!?,.;:])', r'\1', result)
        result = re.sub(r'\s+', ' ', result).strip()
        return result

    def detect_language(self, text: str) -> str:
        """Detect language: 'vi', 'en', or 'mixed'."""
        has_vi = any(c in self.VIETNAMESE_DIACRITICS for c in text.lower())
        words = text.split()
        ascii_words = sum(1 for w in words if all(ord(c) < 128 for c in w))
        if not has_vi and ascii_words == len(words):
            return 'en'
        elif has_vi and ascii_words / max(len(words), 1) > 0.5:
            return 'mixed'
        return 'vi'

    def compute_severity(self, text: str) -> str:
        """Compute severity based on precedence: critical > high > medium > low."""
        text_lower = text.lower()

        # 1. Critical
        critical_kw = ["cháy", "nổ", "chết máy", "không hoạt động", "nguy hiểm", "tai nạn", "chập điện", "chập"]
        for kw in critical_kw:
            if kw in text_lower:
                pattern = r'(?:không|chưa|chả|đéo)\s+' + re.escape(kw)
                if not re.search(pattern, text_lower):
                    return "critical"

        # 2. High
        high_kw = ["nóng", "quá nhiệt", "hỏng", "lỗi", "không sạc được", "mất điện", "liệt", "bị hỏng", "không vào điện", "scam", "lừa đảo"]
        for kw in high_kw:
            if kw in text_lower:
                if kw == "không sạc được":
                    return "high"
                pattern = r'(?:không|chưa|chả|đéo)\s+' + re.escape(kw)
                if not re.search(pattern, text_lower):
                    return "high"

        # 3. Medium
        medium_kw = ["chậm", "lag", "đợi lâu", "không ổn định", "giật", "treo", "chán", "dở", "tệ", "đắt", "bực", "thất vọng", "tệ hại", "kinh khủng"]
        for kw in medium_kw:
            if kw in text_lower:
                pattern = r'(?:không|chưa|chả|đéo)\s+' + re.escape(kw)
                if not re.search(pattern, text_lower):
                    return "medium"

        # Default / Low
        return "low"

    def extract_aspects(self, text: str) -> list[Aspect]:
        """Extract structured aspects from normalized text."""
        aspects = []
        text_lower = text.lower()
        components = self._ontology.get('components', {})
        locations = self._ontology.get('locations', {})

        # Detect components
        detected_components = []
        for comp_name, comp_data in components.items():
            all_keywords = comp_data.get('keywords_vi', []) + comp_data.get('keywords_en', [])
            for kw in all_keywords:
                if kw.lower() in text_lower:
                    detected_components.append(comp_name)
                    break

        # Compute severity using precedence calculation
        detected_severity = self.compute_severity(text)

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
                symptom=text[:100],
                severity=detected_severity
            ))

        return aspects

    def compute_sentiment(self, text: str) -> tuple[float, float]:
        """Compute sentiment score with negation scope handling.
        Returns (sentiment: -1.0..1.0, confidence: 0.0..1.0)"""
        text_lower = text.lower()

        # Split into clauses by punctuation or clause connectors
        clauses = re.split(r'[,.!?;]|\b(?:nhưng|nma|tuy nhiên|mà)\b', text_lower)

        pos_count = 0
        neg_count = 0

        for clause in clauses:
            tokens = self.tokenize(clause)
            if not tokens:
                continue

            negated = False
            scope = 0

            i = 0
            while i < len(tokens):
                tok = tokens[i]

                # Check 2-word expressions first
                phrase_2 = f"{tok} {tokens[i+1]}" if i + 1 < len(tokens) else ""
                phrase_3 = f"{tok} {tokens[i+1]} {tokens[i+2]}" if i + 2 < len(tokens) else ""

                if tok in self._negation_terms:
                    negated = True
                    scope = 3
                    i += 1
                    continue

                matched = False

                # 3-word phrase match
                if phrase_3 and (phrase_3 in self._positive_words or phrase_3 in self._negative_words):
                    if phrase_3 in self._positive_words:
                        if negated and scope > 0:
                            neg_count += 1
                        else:
                            pos_count += 1
                    elif phrase_3 in self._negative_words:
                        if negated and scope > 0:
                            pos_count += 1
                        else:
                            neg_count += 1
                    matched = True
                    i += 3
                # 2-word phrase match
                elif phrase_2 and (phrase_2 in self._positive_words or phrase_2 in self._negative_words):
                    if phrase_2 in self._positive_words:
                        if negated and scope > 0:
                            neg_count += 1
                        else:
                            pos_count += 1
                    elif phrase_2 in self._negative_words:
                        if negated and scope > 0:
                            pos_count += 1
                        else:
                            neg_count += 1
                    matched = True
                    i += 2
                # Single word match
                elif tok in self._positive_words or tok in self._negative_words:
                    if tok in self._positive_words:
                        if negated and scope > 0:
                            neg_count += 1
                        else:
                            pos_count += 1
                    elif tok in self._negative_words:
                        if negated and scope > 0:
                            pos_count += 1
                        else:
                            neg_count += 1
                    matched = True
                    i += 1
                else:
                    i += 1

                if matched and scope > 0:
                    scope -= 1
                    if scope == 0:
                        negated = False
                elif scope > 0:
                    scope -= 1
                    if scope == 0:
                        negated = False

        total = pos_count + neg_count
        if total == 0:
            return 0.0, 0.3
        sentiment = (pos_count - neg_count) / total
        confidence = min(total / 5.0, 1.0)
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
