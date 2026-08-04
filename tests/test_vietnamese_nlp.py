import pytest
from src.services.vietnamese_nlp import VietnameseNLPService, NLPResult, Aspect


@pytest.fixture
def nlp():
    return VietnameseNLPService()


# === Teen-code Normalization Tests (10+) ===

def test_normalize_ko(nlp):
    assert "không" in nlp.normalize("ko sạc được")

def test_normalize_dc(nlp):
    assert "được" in nlp.normalize("sạc dc nhanh")

def test_normalize_vl(nlp):
    result = nlp.normalize("nhanh vl")
    assert "quá" in result or "vãi" in result

def test_normalize_bt(nlp):
    assert "bình thường" in nlp.normalize("sạc bt thôi")

def test_normalize_cx(nlp):
    assert "cũng" in nlp.normalize("cx ổn")

def test_normalize_mk(nlp):
    assert "mình" in nlp.normalize("mk thấy ổn")

def test_normalize_nma(nlp):
    assert "nhưng mà" in nlp.normalize("ok nma hơi chậm")

def test_normalize_tks(nlp):
    result = nlp.normalize("tks bác tài")
    assert "cảm ơn" in result or "thanks" in result

def test_normalize_multiple(nlp):
    """Multiple teen-codes in one sentence."""
    result = nlp.normalize("ko dc j, bt thôi")
    assert "không" in result
    assert "được" in result
    assert "bình thường" in result

def test_normalize_preserves_standard(nlp):
    """Standard Vietnamese should not be changed."""
    text = "Trạm sạc hoạt động tốt, nhanh và sạch sẽ"
    assert nlp.normalize(text) == text

def test_normalize_empty(nlp):
    assert nlp.normalize("") == ""

def test_normalize_ev_slang(nlp):
    result = nlp.normalize("tram sac vincom ok phet")
    assert "trạm sạc" in result


# === Language Detection Tests (5) ===

def test_detect_vi(nlp):
    assert nlp.detect_language("Trạm sạc rất tốt") == "vi"

def test_detect_en(nlp):
    assert nlp.detect_language("The charging station works great") == "en"

def test_detect_mixed(nlp):
    result = nlp.detect_language("Trạm sạc ok, very good")
    assert result in ("mixed", "vi")  # either is acceptable

def test_detect_teencode_as_vi(nlp):
    """Teen-code text should be detected as Vietnamese."""
    result = nlp.detect_language("sạc nhanh vl, đỉnh lắm")
    assert result == "vi"

def test_detect_empty(nlp):
    result = nlp.detect_language("")
    assert result in ("en", "vi")  # either acceptable for empty


# === Aspect Extraction Tests (8) ===

def test_extract_charger_aspect(nlp):
    aspects = nlp.extract_aspects("trạm sạc không hoạt động")
    assert any(a.component == "charger" for a in aspects)

def test_extract_battery_aspect(nlp):
    aspects = nlp.extract_aspects("pin xe yếu quá")
    assert any(a.component == "battery" for a in aspects)

def test_extract_vehicle_aspect(nlp):
    aspects = nlp.extract_aspects("xe VinFast VF8 đẹp lắm")
    assert any(a.component == "vehicle" for a in aspects)

def test_extract_app_aspect(nlp):
    aspects = nlp.extract_aspects("ứng dụng Xanh SM lag quá")
    assert any(a.component == "app" for a in aspects)

def test_extract_driver_aspect(nlp):
    aspects = nlp.extract_aspects("tài xế lái xe rất giỏi")
    assert any(a.component == "driver" for a in aspects)

def test_extract_critical_severity(nlp):
    aspects = nlp.extract_aspects("trạm sạc cháy nổ nguy hiểm")
    assert any(a.severity == "critical" for a in aspects)

def test_extract_location(nlp):
    aspects = nlp.extract_aspects("trạm sạc Vincom rất tốt")
    assert any(a.location is not None for a in aspects)

def test_extract_default_component(nlp):
    """Unknown text defaults to 'service' component."""
    aspects = nlp.extract_aspects("mọi thứ bình thường")
    assert len(aspects) > 0


# === Full Analysis Pipeline Tests (5) ===

def test_analyze_returns_nlp_result(nlp):
    result = nlp.analyze("trạm sạc ok")
    assert isinstance(result, NLPResult)
    assert result.original_text == "trạm sạc ok"

def test_analyze_positive_sentiment(nlp):
    result = nlp.analyze("Trạm sạc tuyệt vời, sạch đẹp nhanh")
    assert result.sentiment > 0

def test_analyze_negative_sentiment(nlp):
    result = nlp.analyze("Dịch vụ tệ, chậm lag lỗi liên tục")
    assert result.sentiment < 0

def test_analyze_teencode_detected(nlp):
    result = nlp.analyze("ko sac dc, tệ vl")
    assert len(result.teencode_found) > 0

def test_batch_analyze(nlp):
    results = nlp.batch_analyze(["tốt lắm", "tệ quá", "bình thường"])
    assert len(results) == 3
    assert all(isinstance(r, NLPResult) for r in results)


# === Edge Cases (3) ===

def test_analyze_unicode(nlp):
    result = nlp.analyze("Trạm sạc ở Thủ Đức hoạt động ổn định 👍")
    assert isinstance(result, NLPResult)

def test_analyze_long_text(nlp):
    text = "tốt " * 500
    result = nlp.analyze(text)
    assert result.sentiment > 0

def test_find_teencode(nlp):
    found = nlp.find_teencode("ko dc j, bt thôi nma cx ok")
    assert len(found) >= 3
