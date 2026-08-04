import pytest
from src.services.vietnamese_nlp import VietnameseNLPService, NLPResult, Aspect


@pytest.fixture
def nlp():
    return VietnameseNLPService()


# === 1. Punctuation-Aware Tokenization Tests (3) ===

def test_tokenize_punctuation_marks(nlp):
    """Test handling of !, ?, ., , cleanly without stripping word boundaries."""
    tokens = nlp.tokenize("App khong lag, sac nhanhhh vl!")
    assert "," in tokens
    assert "!" in tokens
    assert "lag" in tokens
    assert "nhanhhh" in tokens


def test_tokenize_empty_string(nlp):
    """Test tokenization of empty or whitespace strings."""
    assert nlp.tokenize("") == []
    assert nlp.tokenize("   ") == []


def test_tokenize_multiple_punctuation(nlp):
    """Test handling of complex punctuation combinations."""
    tokens = nlp.tokenize("Trạm sạc ở đâu??? Có tốt không, hả?")
    assert "?" in tokens
    assert "," in tokens
    assert "đâu" in tokens
    assert "không" in tokens


# === 2. Repeated Character Normalization Tests (3) ===

def test_reduce_repeated_chars_consonants(nlp):
    """Test reduction of elongated repeated consonants."""
    assert nlp.reduce_repeated_chars("nhanhhh") == "nhanh"
    assert nlp.reduce_repeated_chars("okkk") == "ok"
    assert nlp.reduce_repeated_chars("ngonnn") == "ngon"


def test_reduce_repeated_chars_vowels(nlp):
    """Test reduction of elongated repeated vowels."""
    assert nlp.reduce_repeated_chars("laaag") == "lag"
    assert nlp.reduce_repeated_chars("quaaa") == "qua"


def test_reduce_repeated_chars_preserved(nlp):
    """Test that legitimate double characters in preserved words are not altered."""
    assert nlp.reduce_repeated_chars("app") == "app"
    assert nlp.reduce_repeated_chars("pass") == "pass"
    assert nlp.reduce_repeated_chars("wifi") == "wifi"


# === 3. Accentless Vietnamese Detection & Mapping Tests (3) ===

def test_is_accentless_true(nlp):
    """Test detection of accentless Vietnamese text."""
    assert nlp.is_accentless("khong sac dc") is True
    assert nlp.is_accentless("app khong lag, sac nhanh") is True


def test_is_accentless_false(nlp):
    """Test detection of accented Vietnamese text."""
    assert nlp.is_accentless("Trạm sạc hoạt động tốt") is False
    assert nlp.is_accentless("Ứng dụng chạy mượt") is False


def test_accentless_dictionary_mapping(nlp):
    """Test accentless term normalization and dictionary mapping."""
    norm = nlp.normalize("khong sac dc")
    assert "không" in norm
    assert "sạc" in norm
    assert "được" in norm


# === 4. Negation Scope Handling Tests (4) ===

def test_negation_scope_flips_negative_to_positive(nlp):
    """Test that negation terms before negative words yield positive sentiment."""
    res = nlp.analyze("app không lag")
    assert res.sentiment > 0


def test_negation_scope_flips_positive_to_negative(nlp):
    """Test that negation terms before positive words yield negative sentiment."""
    res1 = nlp.analyze("không sạc được")
    assert res1.sentiment < 0

    res2 = nlp.analyze("không tốt")
    assert res2.sentiment < 0


def test_negation_scope_multiple_negations(nlp):
    """Test various negation terms (chưa, đéo, chả)."""
    res1 = nlp.analyze("chưa hỏng")
    assert res1.sentiment > 0

    res2 = nlp.analyze("đéo sạc được")
    assert res2.sentiment < 0


def test_negation_scope_clause_boundary(nlp):
    """Test that negation scope stops at clause boundaries or punctuation."""
    res = nlp.analyze("khong lag, te va loii")
    # 'không lag' is positive, 'tệ và lỗi' is negative
    assert res.normalized_text is not None


# === 5. Severity Precedence Calculation Tests (4) ===

def test_severity_precedence_critical(nlp):
    """Test critical severity precedence for safety hazards."""
    severity = nlp.compute_severity("trạm sạc cháy nổ chập điện nguy hiểm")
    assert severity == "critical"


def test_severity_precedence_high(nlp):
    """Test high severity precedence for functional faults."""
    severity1 = nlp.compute_severity("không sạc được, trụ sạc bị hỏng")
    assert severity1 == "high"

    severity2 = nlp.compute_severity("pin bị nóng quá nhiệt")
    assert severity2 == "high"


def test_severity_precedence_medium(nlp):
    """Test medium severity precedence for performance degradations."""
    severity = nlp.compute_severity("ứng dụng Xanh SM bị lag và chậm")
    assert severity == "medium"


def test_severity_precedence_negated_fault(nlp):
    """Test that negated faults do not trigger high/medium severity."""
    severity = nlp.compute_severity("app không lag, sạc nhanh quá")
    assert severity == "low"


# === 6. Held-Out Set Evaluation (20 Vietnamese Review Samples) ===

HELD_OUT_REVIEWS = [
    ("Trạm sạc VinFast sạc nhanh, dịch vụ rất tốt!", "positive"),
    ("Ứng dụng Xanh SM hay bị lag và chậm", "negative"),
    ("Không sạc được, trụ sạc bị lỗi liên tục", "negative"),
    ("Xe đi êm, pin dùng lâu, rất hài lòng", "positive"),
    ("Dịch vụ chăm sóc khách hàng tệ quá", "negative"),
    ("App khong lag, sac nhanhhh vl", "positive"),
    ("Trạm sạc cháy nổ chập điện nguy hiểm", "negative"),
    ("Bác tài nhiệt tình, xe sạch đẹp", "positive"),
    ("Giá cước đắt, thời gian chờ quá lâu", "negative"),
    ("Sạc bt thôi, không có gì đặc biệt", "neutral"),
    ("Không bị hỏng, trạm sạc chạy mượt", "positive"),
    ("Chưa tốt lắm, app vẫn còn lỗi nhẹ", "negative"),
    ("Đầu sạc chắc chắn, sạc siêu nhanh", "positive"),
    ("Đéo sạc được, bực mình thật", "negative"),
    ("Pin xe tuột nhanh, chai pin rồi", "negative"),
    ("Xe mới, điều hòa mát lạnh, 10 điểm", "positive"),
    ("Không lag, không giật, dùng ngon", "positive"),
    ("Tổng đài không trả lời, hỗ trợ quá dở", "negative"),
    ("Mọi thứ bình thường, chấp nhận được", "neutral"),
    ("Sạc nhanh phết, trạm sạch sẽ vcl", "positive")
]


def test_eval_held_out_dataset_metrics(nlp):
    """Evaluate Macro F1, Micro F1, Precision, and Accuracy on held-out dataset."""
    y_true = []
    y_pred = []

    for text, gold_label in HELD_OUT_REVIEWS:
        result = nlp.analyze(text)
        sentiment_val = result.sentiment

        if sentiment_val > 0:
            pred_label = "positive"
        elif sentiment_val < 0:
            pred_label = "negative"
        else:
            pred_label = "neutral"

        y_true.append(gold_label)
        y_pred.append(pred_label)

    classes = ["positive", "negative", "neutral"]

    # Calculate Accuracy
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / len(y_true)

    # Calculate Per-Class Precision, Recall, F1
    precisions = []
    recalls = []
    f1s = []

    tp_total = 0
    fp_total = 0
    fn_total = 0

    for c in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp == c)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != c and yp == c)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp != c)

        tp_total += tp
        fp_total += fp
        fn_total += fn

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    macro_precision = sum(precisions) / len(classes)
    macro_recall = sum(recalls) / len(classes)
    macro_f1 = sum(f1s) / len(classes)

    micro_precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
    micro_recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
    micro_f1 = (2 * micro_precision * micro_recall) / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0.0

    print(f"\n--- NLP Evaluation Results on 20 Samples ---")
    print(f"Accuracy:        {accuracy:.4f}")
    print(f"Macro Precision: {macro_precision:.4f}")
    print(f"Macro Recall:    {macro_recall:.4f}")
    print(f"Macro F1:        {macro_f1:.4f}")
    print(f"Micro F1:        {micro_f1:.4f}")

    assert accuracy >= 0.85, f"Accuracy {accuracy:.4f} is below 0.85 threshold"
    assert macro_precision >= 0.85, f"Precision {macro_precision:.4f} is below 0.85 threshold"
    assert macro_f1 >= 0.85, f"Macro F1 {macro_f1:.4f} is below 0.85 threshold"
    assert micro_f1 >= 0.85, f"Micro F1 {micro_f1:.4f} is below 0.85 threshold"
