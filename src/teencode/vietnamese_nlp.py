from __future__ import annotations
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Aspect:
    component: str  # 'charger', 'battery', 'vehicle', 'app', 'driver', 'pricing', 'service'
    location: str | None = None
    symptom: str = ''
    severity: str = 'medium'  # 'critical', 'high', 'medium', 'low' — scoped to this aspect's clause
    sentiment: float = 0.0  # -1.0..1.0 — scoped to this aspect's clause, not the whole text


@dataclass
class CrossValidationResult:
    """Result of cross-referencing a charger complaint against V-GREEN hardware logs."""
    matched: bool  # True if the complaint's location resolved to a known station
    station_id: str | None = None
    max_station_temp_c: float | None = None
    threshold_c: float = 85.5
    threshold_exceeded: bool = False
    confirmed_hardware_fault: bool = False
    evidence: list[dict] = field(default_factory=list)


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

    # V-GREEN charging station hardware fault threshold (VGREEN_Thermal_Power_Drop fault family)
    STATION_TEMP_THRESHOLD_C = 85.5

    # Maps free-text feedback locations to V-GREEN station_id (data/vingroup/vgreen_charging_stations_dirty.csv)
    STATION_LOCATION_ALIASES = {
        'landmark 81': 'VG_STA_LANDMARK81',
        'landmark81': 'VG_STA_LANDMARK81',
        'royal city': 'VG_STA_ROYAL_CITY',
        'vincom ba trieu': 'VG_STA_VINCOM_BA_TRIEU',
        'vincom bà triệu': 'VG_STA_VINCOM_BA_TRIEU',
        'ocean park': 'VG_STA_OCEAN_PARK',
    }

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

    def strip_diacritics(self, text: str) -> str:
        """Strip Vietnamese diacritics (đ/Đ handled separately since NFD doesn't
        decompose them). Used to match domain keyword lists against accentless
        dirty feedback (e.g. 'ngat dien' should still hit 'ngắt điện')."""
        text = text.replace('đ', 'd').replace('Đ', 'D')
        decomposed = unicodedata.normalize('NFD', text)
        return ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')

    def split_clauses(self, text: str) -> list[str]:
        """Split text into clauses on punctuation and contrastive connectors
        (e.g. 'nhưng', 'tuy nhiên') so severity/sentiment can be scoped per-aspect
        instead of blending unrelated clauses together."""
        return re.split(r'[,.!?;]|\b(?:nhưng|nma|tuy nhiên|mà)\b', text)

    def _keyword_present(self, keyword: str, stripped_text: str) -> bool:
        """Word-boundary-anchored, diacritic-insensitive keyword lookup.
        Boundary anchoring matters once diacritics are stripped: e.g. 'hỏng'
        ('broken') strips to 'hong', which is a raw substring of 'không'
        ('not') stripped to 'khong' — a naive `in` check would misfire."""
        kw_s = self.strip_diacritics(keyword.lower())
        pattern = r'(?:^|(?<=\W))' + re.escape(kw_s) + r'(?:$|(?=\W))'
        return re.search(pattern, stripped_text) is not None

    def _keyword_negated(self, keyword: str, stripped_text: str) -> bool:
        kw_s = self.strip_diacritics(keyword.lower())
        pattern = r'(?:^|(?<=\W))(?:khong|chua|cha|deo)\s+' + re.escape(kw_s) + r'(?:$|(?=\W))'
        return re.search(pattern, stripped_text) is not None

    def compute_severity(self, text: str) -> str:
        """Compute severity based on precedence: critical > high > medium > low.
        Matching is diacritic-insensitive so accentless dirty input (e.g.
        'ngat dien', 'bao loi') scores the same as the fully-accented form."""
        stripped = self.strip_diacritics(text.lower())

        # 1. Critical
        critical_kw = ["cháy", "nổ", "chết máy", "không hoạt động", "nguy hiểm", "tai nạn", "chập điện", "chập"]
        for kw in critical_kw:
            if self._keyword_present(kw, stripped) and not self._keyword_negated(kw, stripped):
                return "critical"

        # 2. High
        high_kw = ["nóng", "quá nhiệt", "hỏng", "lỗi", "không sạc được", "mất điện", "ngắt điện", "liệt", "bị hỏng", "không vào điện", "scam", "lừa đảo"]
        for kw in high_kw:
            if self._keyword_present(kw, stripped):
                if kw == "không sạc được":
                    return "high"
                if not self._keyword_negated(kw, stripped):
                    return "high"

        # 3. Medium
        medium_kw = ["chậm", "lag", "đợi lâu", "không ổn định", "giật", "treo", "chán", "dở", "tệ", "đắt", "bực", "thất vọng", "tệ hại", "kinh khủng"]
        for kw in medium_kw:
            if self._keyword_present(kw, stripped) and not self._keyword_negated(kw, stripped):
                return "medium"

        # Default / Low
        return "low"

    def extract_aspects(self, text: str) -> list[Aspect]:
        """Extract structured aspects from normalized text.

        Severity and sentiment are scoped to the clause containing each
        aspect's matched keyword (not the whole text), so a single feedback
        mixing multiple components of differing severity (e.g. "trạm sạc
        cháy nổ, nhưng app thì ok") doesn't misattribute one component's
        severity/sentiment to another.
        """
        aspects = []
        text_lower = text.lower()
        components = self._ontology.get('components', {})
        locations = self._ontology.get('locations', {})
        clauses = self.split_clauses(text)

        # Detect components + the keyword/clause that triggered each match
        detected = []  # list of (comp_name, clause_or_None)
        for comp_name, comp_data in components.items():
            all_keywords = comp_data.get('keywords_vi', []) + comp_data.get('keywords_en', [])
            matched_kw = next((kw for kw in all_keywords if kw.lower() in text_lower), None)
            if matched_kw:
                clause = next((c for c in clauses if matched_kw.lower() in c.lower()), None)
                detected.append((comp_name, clause))

        # Detect location
        detected_location = None
        for region, locs in locations.items():
            for loc in locs:
                if loc.lower() in text_lower:
                    detected_location = loc
                    break
            if detected_location:
                break

        # Default if no component found
        if not detected:
            detected = [('service', None)]

        for comp_name, clause in detected:
            scope_text = clause.strip() if clause else text
            severity = self.compute_severity(scope_text)
            sentiment, _confidence = self.compute_sentiment(scope_text)
            aspects.append(Aspect(
                component=comp_name,
                location=detected_location,
                symptom=scope_text[:100],
                severity=severity,
                sentiment=sentiment,
            ))

        return aspects

    def compute_sentiment(self, text: str) -> tuple[float, float]:
        """Compute sentiment score with negation scope handling.
        Returns (sentiment: -1.0..1.0, confidence: 0.0..1.0)"""
        text_lower = text.lower()

        # Split into clauses by punctuation or clause connectors
        clauses = self.split_clauses(text_lower)

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

    def resolve_station_id(self, location: str | None) -> str | None:
        """Resolve a free-text feedback location to a V-GREEN station_id."""
        if not location:
            return None
        key = location.strip().lower()
        if key in self.STATION_LOCATION_ALIASES:
            return self.STATION_LOCATION_ALIASES[key]
        for alias, station_id in self.STATION_LOCATION_ALIASES.items():
            if alias in key or key in alias:
                return station_id
        return None

    def cross_validate_with_station_logs(
        self,
        result: NLPResult,
        station_logs: list[dict],
        threshold_c: float | None = None,
    ) -> CrossValidationResult:
        """Cross-validate a charger complaint's extracted aspects against V-GREEN
        charging station hardware logs (station_temp_c), confirming whether the
        complaint corresponds to a real thermal fault (temp >= threshold_c)."""
        threshold_c = self.STATION_TEMP_THRESHOLD_C if threshold_c is None else threshold_c

        charger_aspects = [a for a in result.aspects if a.component == 'charger']
        if not charger_aspects:
            return CrossValidationResult(matched=False, threshold_c=threshold_c)

        location = next((a.location for a in charger_aspects if a.location), None)
        station_id = self.resolve_station_id(location)
        if not station_id:
            return CrossValidationResult(matched=False, threshold_c=threshold_c)

        matching_logs = [row for row in station_logs if row.get('station_id') == station_id]
        readings = []
        for row in matching_logs:
            raw_temp = row.get('station_temp_c')
            if raw_temp not in (None, ''):
                readings.append((row, float(raw_temp)))
        temps = [temp for _row, temp in readings]
        max_temp = max(temps) if temps else None
        threshold_exceeded = max_temp is not None and max_temp >= threshold_c
        evidence = [row for row, temp in readings if temp >= threshold_c]

        return CrossValidationResult(
            matched=True,
            station_id=station_id,
            max_station_temp_c=max_temp,
            threshold_c=threshold_c,
            threshold_exceeded=threshold_exceeded,
            confirmed_hardware_fault=threshold_exceeded,
            evidence=evidence,
        )
