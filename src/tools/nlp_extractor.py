from src.tools.base import BaseTool
from src.teencode.vietnamese_nlp import VietnameseNLPService


class NLPExtractorTool(BaseTool):
    name = "vietnamese_nlp_extractor"
    description = "Normalize Vietnamese teen-code, extract aspects (component, severity, location), and analyze sentiment from customer feedback text."
    input_schema = {
        "type": "object",
        "properties": {
            "review_text": {"type": "string", "description": "Raw Vietnamese feedback text"},
            "review_id": {"type": "integer", "description": "Optional review ID for tracking"}
        },
        "required": ["review_text"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "normalized_text": {"type": "string"},
            "aspects": {"type": "array"},
            "sentiment": {"type": "number"},
            "teencode_found": {"type": "array"},
            "language": {"type": "string"}
        }
    }

    def __init__(self):
        self._nlp = VietnameseNLPService()

    def execute(self, input_data: dict) -> dict:
        text = input_data.get("review_text", "")
        if not text:
            return {"normalized_text": "", "aspects": [], "sentiment": 0.0, "teencode_found": [], "language": ""}
        result = self._nlp.analyze(text)
        return {
            "normalized_text": result.normalized_text,
            "aspects": [{"component": a.component, "location": a.location, "symptom": a.symptom, "severity": a.severity} for a in result.aspects],
            "sentiment": result.sentiment,
            "teencode_found": result.teencode_found,
            "language": result.language,
            "confidence": result.confidence
        }
