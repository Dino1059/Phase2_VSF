"""
DataTrust OS: Negation-Aware Priority Intent Classifier
Classifies user queries into distinct governance intents:
- GENERAL_CONVERSATION: Greetings, conversational chat, small talk, AI capability questions
- RUN_OVERVIEW: Queries about run status, metrics, overall progress
- ROOT_CAUSE_ONLY: Queries about why an error happened, RCA, reasons (with negation handling)
- REMEDIATION_ONLY: Queries about how to fix, treatment rules, proposals
- BOTH_RCA_AND_REMEDIATION: Combined queries asking for both cause and remedy
- PIPELINE_ERROR_OR_PROGRESS: Queries about pipeline execution errors, stalled steps, logs
- DATA_OR_CATALOG_INQUIRY: Queries about datasets, tables, schema, columns, profiling
- POLICY_OR_LEGAL_INQUIRY: Queries about compliance rules, Decree 13, Law 91, SOX-404, GDPR
- TOPIC_SWITCH: User explicitly changes topic or resets conversational focus
"""

import re
from enum import Enum
from typing import Tuple


class UserIntent(str, Enum):
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    RUN_OVERVIEW = "RUN_OVERVIEW"
    ROOT_CAUSE_ONLY = "ROOT_CAUSE_ONLY"
    REMEDIATION_ONLY = "REMEDIATION_ONLY"
    BOTH_RCA_AND_REMEDIATION = "BOTH_RCA_AND_REMEDIATION"
    PIPELINE_ERROR_OR_PROGRESS = "PIPELINE_ERROR_OR_PROGRESS"
    DATA_OR_CATALOG_INQUIRY = "DATA_OR_CATALOG_INQUIRY"
    POLICY_OR_LEGAL_INQUIRY = "POLICY_OR_LEGAL_INQUIRY"
    TOPIC_SWITCH = "TOPIC_SWITCH"


class IntentClassifier:
    """Classifies user messages using priority rules and negation detection."""

    # Patterns indicating topic switch or reset
    TOPIC_SWITCH_PATTERNS = [
        r"b\u1ecf\s+qua\s+(chuy\u1ec7n|ch\u1ee7\s+\u0111\u1ec1|v\u1ea5n\s+\u0111\u1ec1|finding)\s+(n\u00e0y|\u0111\u00f3)",
        r"(chuy\u1ec3n|sang|n\u00f3i)\s+(ch\u1ee7\s+\u0111\u1ec1|chuy\u1ec7n)\s+kh\u00e1c",
        r"\b\u0111\u1ed5i\s+ch\u1ee7\s+\u0111\u1ec1\b",
        r"\b(reset|restart|b\u1eaft\s+\u0111\u1ea7u\s+l\u1ea1i|quay\s+v\u1ec1\s+\u0111\u1ea7u|quay\s+l\u1ea1i\s+t\u1eeb\s+\u0111\u1ea7u)\b",
        r"kh\u00f4ng\s+h\u1ecfi\s+v\u1ec1\s+(c\u00e1i|finding|l\u1ed7i|ch\u1ee7\s+\u0111\u1ec1)\s+n\u00e0y\s+n\u1eefa",
    ]

    # Patterns indicating general conversation / greetings / bot intro
    GENERAL_CONVERSATION_PATTERNS = [
        r"^(xin\s+)?ch\u00e0o(\s+b\u1ea1n|\s+em|\s+bot)?[\s\!\?\.]*$",
        r"^(hi|hello|hey|chao|alo|good\s+morning|good\s+afternoon)(\s+b\u1ea1n|\s+bot)?[\s\!\?\.]*$",
        r"b\u1ea1n\s+(l\u00e0\s+ai|t\u00ean\s+g\u00ec|l\u00e0m\s+\u0111\u01b0\u1ee3c\s+g\u00ec|c\u00f3\s+th\u1ec3\s+gi\u00fap\s+g\u00ec|c\u00f3\s+vai\s+tr\u00f2\s+g\u00ec)",
        r"(gi\u1edbi\s+thi\u1ec7u|introduce)\s+(b\u1ea3n\s+th\u00e2n|v\u1ec1\s+b\u1ea1n)",
        r"^(c\u1ea3m\s+\u01a1n|thank\s+you|thanks)(\s+b\u1ea1n|\s+bot|\s+nhi\u1ec1u)?[\s\!\?\.]*$",
        r"b\u1ea1n\s+(kh\u1ecfe\s+kh\u00f4ng|th\u1ebf\s+n\u00e0o|how\s+are\s+you)",
        r"^gi\u00fap\s+t\u00f4i(\s+v\u1edbi)?[\s\!\?\.]*$",
    ]

    # Patterns indicating user explicitly DOES NOT want remediation
    NEGATION_REMEDIATION_PATTERNS = [
        r"kh\u00f4ng\s+(c\u1ea7n|ph\u1ea3i|mu\u1ed1n)\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|s\u1eeda|remediation|\u0111\u1ec1\s+xu\u1ea5t|x\u1eed\s+l\u00fd)",
        r"ch\u01b0a\s+c\u1ea7n\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|s\u1eeda|remediation|\u0111\u1ec1\s+xu\u1ea5t|x\u1eed\s+l\u00fd)",
        r"\u0111\u1eebng\s+(n\u00eau|\u0111\u1ec1\s+xu\u1ea5t|\u0111\u01b0a\s+ra)\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|remediation|ph\u01b0\u01a1ng\s+\u00e1n)",
        r"ch\u1ec9\s+(c\u1ea7n|h\u1ecfi|gi\u1ea3i\s+th\u00edch)\s+(nguy\u00ean\s+nh\u00e2n|l\u00fd\s+do|rca|t\u1ea1i\s+sao|v\u1ea5n\s+\u0111\u1ec1)",
        r"b\u1ecf\s+qua\s+(gi\u1ea3i\s+ph\u00e1p|kh\u1eafc\s+ph\u1ee5c|remediation)",
    ]

    # Patterns indicating user is asking about root cause
    ROOT_CAUSE_PATTERNS = [
        r"nguy\u00ean\s+nh\u00e2n",
        r"l\u00fd\s+do\s+(vi\s+ph\u1ea1m|b\u1ecb\s+l\u1ed7i|c\u00e1ch\s+ly|b\u1ecb\s+b\u1eaft)",
        r"t\u1ea1i\s+sao",
        r"\brca\b",
        r"\broot\s+cause\b",
        r"\bfinding\b",
        r"\bvi\s+ph\u1ea1m\b",
        r"\b\u0111i\u1ec1u\s+tra\b",
        r"gi\u1ea3i\s+th\u00edch\s+(l\u1ed7i|vi\s+ph\u1ea1m|finding)",
    ]

    # Patterns indicating user is asking for remediation / action
    REMEDIATION_PATTERNS = [
        r"kh\u1eafc\s+ph\u1ee5c",
        r"gi\u1ea3i\s+ph\u00e1p",
        r"s\u1eeda\s+(nh\u01b0\s+th\u1ebf\s+n\u00e0o|l\u1ed7i|d\u1eef\s+li\u1ec7u)",
        r"c\u00e1ch\s+(x\u1eed\s+l\u00fd|gi\u1ea3i\s+quy\u1ebft|kh\u1eafc\s+ph\u1ee5c)",
        r"\bremediation\b",
        r"\u0111\u1ec1\s+xu\u1ea5t\s+(rule|quy\s+t\u1eafc|x\u1eed\s+l\u00fd|h\u00e0nh\s+\u0111\u1ed9ng)",
        r"treatment\s+rule",
        r"l\u00e0m\s+sao\s+\u0111\u1ec3\s+h\u1ebft\s+l\u1ed7i",
    ]

    # Patterns indicating pipeline execution error or step logs
    PIPELINE_ERROR_PATTERNS = [
        r"b\u01b0\u1edbc\s+n\u00e0y\s+\u0111ang\s+l\u00e0m\s+g\u00ec",
        r"(l\u1ed7i\s+pipeline|pipeline\s+(b\u1ecb\s+)?l\u1ed7i)",
        r"(step|b\u01b0\u1edbc)\s+(b\u1ecb\s+l\u1ed7i|failed|stalled|d\u1eebng)",
        r"ti\u1ebfn\s+\u0111\u1ed9\s+(pipeline|ch\u1ea1y)",
        r"t\u1ea1i\s+sao\s+pipeline\s+(d\u1eebng|b\u1ecb\s+l\u1ed7i)",
        r"event\s+log",
        r"nh\u1eadt\s+k\u00fd\s+th\u1ef1c\s+thi",
    ]

    # Patterns for run overview
    RUN_OVERVIEW_PATTERNS = [
        r"t\u1ed5ng\s+quan(\s+l\u1ea7n\s+ch\u1ea1y)?",
        r"t\u00ecnh\s+h\u00ecnh\s+l\u1ea7n\s+ch\u1ea1y",
        r"k\u1ebft\s+qu\u1ea3\s+(l\u1ea7n\s+ch\u1ea1y|run)",
        r"bao\s+nhi\u00eau\s+l\u1ed7i",
        r"t\u1ed5ng\s+s\u1ed1\s+(b\u1ea3n\s+ghi|d\u00f2ng|c\u00e1ch\s+ly)",
        r"t\u00f3m\s+t\u1eaft\s+run",
        r"run\s+(n\u00e0y|overview)",
    ]

    # Patterns for data catalog / profiling inquiry
    DATA_OR_CATALOG_PATTERNS = [
        r"(b\u1ea3ng|dataset|table)\s+([a-zA-Z0-9_-]+|\u0111ang\s+ch\u1ea1y)\s+(c\u00f3\s+nh\u1eefng\s+c\u1ed9t\s+n\u00e0o|c\u1ea5u\s+tr\u00fac|schema)",
        r"(th\u00f4ng\s+tin|danh\s+s\u00e1ch)\s+(c\u1ed9t|b\u1ea3ng|dataset|catalog|columns)",
        r"profiling\s+(c\u1ee7a\s+)?(dataset|b\u1ea3ng|c\u1ed9t|d\u1eef\s+li\u1ec7u)",
        r"(t\u1ef7\s+l\u1ec7|th\u1ed1ng\s+k\u00ea)\s+(null|tr\u1ed1ng|d\u1eef\s+li\u1ec7u)",
        r"catalog\s+(c\u00f3\s+g\u00ec|d\u1eef\s+li\u1ec7u)",
    ]

    # Patterns for policy / legal compliance inquiry
    POLICY_OR_LEGAL_PATTERNS = [
        r"ngh\u1ecb\s+\u0111\u1ecbnh\s+13",
        r"lu\u1eadt\s+(91|an\s+ninh\s+m\u1ea1ng|b\u1ea3o\s+v\u1ec7\s+d\u1eef\s+li\u1ec7u)",
        r"\b(gdpr|sox|sox-404|hipaa)\b",
        r"(ch\u00ednh\s+s\u00e1ch|quy\s+t\u1eafc)\s+(tu\u00e2n\s+th\u1ee7|b\u1ea3o\s+m\u1eadt|compliance)",
        r"ti\u00eau\s+chu\u1ea9n\s+(ph\u00e1p\s+l\u00fd|ki\u1ec3m\s+to\u00e1n)",
    ]

    @classmethod
    def classify(cls, message: str) -> UserIntent:
        """
        Evaluates message against prioritized rules with negation overrides.
        """
        text = message.lower().strip()

        # 1. Topic Switch (explicit reset/change topic requested)
        if any(re.search(p, text) for p in cls.TOPIC_SWITCH_PATTERNS):
            return UserIntent.TOPIC_SWITCH

        # 2. General Conversation (greetings, pleasantries, small talk)
        if any(re.search(p, text) for p in cls.GENERAL_CONVERSATION_PATTERNS):
            return UserIntent.GENERAL_CONVERSATION

        # 3. Pipeline Execution Errors / Progress
        if any(re.search(p, text) for p in cls.PIPELINE_ERROR_PATTERNS):
            return UserIntent.PIPELINE_ERROR_OR_PROGRESS

        # 4. Check for Negation of Remediation (User strictly does NOT want remediation)
        has_remediation_negation = any(
            re.search(p, text) for p in cls.NEGATION_REMEDIATION_PATTERNS
        )

        has_root_cause_intent = any(
            re.search(p, text) for p in cls.ROOT_CAUSE_PATTERNS
        )

        has_remediation_intent = any(
            re.search(p, text) for p in cls.REMEDIATION_PATTERNS
        )

        # If remediation is negated, force ROOT_CAUSE_ONLY even if remediation words appear
        if has_remediation_negation and has_root_cause_intent:
            return UserIntent.ROOT_CAUSE_ONLY

        # Both RCA and Remediation requested
        if has_root_cause_intent and has_remediation_intent:
            return UserIntent.BOTH_RCA_AND_REMEDIATION

        # Only Remediation
        if has_remediation_intent and not has_root_cause_intent:
            return UserIntent.REMEDIATION_ONLY

        # Only Root Cause
        if has_root_cause_intent:
            return UserIntent.ROOT_CAUSE_ONLY

        # Data / Catalog inquiry
        if any(re.search(p, text) for p in cls.DATA_OR_CATALOG_PATTERNS):
            return UserIntent.DATA_OR_CATALOG_INQUIRY

        # Policy / Legal inquiry
        if any(re.search(p, text) for p in cls.POLICY_OR_LEGAL_PATTERNS):
            return UserIntent.POLICY_OR_LEGAL_INQUIRY

        # Explicit Run Overview
        if any(re.search(p, text) for p in cls.RUN_OVERVIEW_PATTERNS):
            return UserIntent.RUN_OVERVIEW

        # Default fallback: General conversation (natural dialogue, not forced run overview)
        return UserIntent.GENERAL_CONVERSATION
