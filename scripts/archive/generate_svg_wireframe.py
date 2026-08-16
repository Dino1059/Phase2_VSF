import json

def generate_svg():
    elements = [
        {"id": "bg_canvas", "type": "rectangle", "x": 0, "y": 0, "width": 1280, "height": 860, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "hdr_zone", "type": "rectangle", "x": 0, "y": 0, "width": 1280, "height": 60, "strokeColor": "#1971c2", "strokeWidth": 2, "backgroundColor": "#a5d8ff", "text": ""},
        {"id": "side_zone", "type": "rectangle", "x": 0, "y": 60, "width": 260, "height": 800, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "chat_zone", "type": "rectangle", "x": 260, "y": 60, "width": 520, "height": 800, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "work_zone", "type": "rectangle", "x": 780, "y": 60, "width": 500, "height": 800, "strokeColor": "#0c8599", "strokeWidth": 2, "backgroundColor": "#99e9f2", "text": ""},

        {"id": "hdr_title", "type": "text", "x": 20, "y": 35, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "🤖 DataTrust OS v3.0 — VinGroup Enterprise AI Governance"},
        {"id": "hdr_ds_pill", "type": "rectangle", "x": 580, "y": 12, "width": 310, "height": 36, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "text": "📦 real_vinfast_ev_telemetry"},
        {"id": "hdr_search", "type": "rectangle", "x": 900, "y": 12, "width": 160, "height": 36, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "🔍 Ctrl + K Search"},
        {"id": "hdr_upload", "type": "rectangle", "x": 1070, "y": 12, "width": 100, "height": 36, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "📤 Upload DB"},
        {"id": "hdr_user", "type": "text", "x": 1185, "y": 35, "fontSize": 14, "strokeColor": "#9c36b5", "text": "👤 Steward"},

        {"id": "btn_new_chat", "type": "rectangle", "x": 15, "y": 75, "width": 230, "height": 40, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ New Chat Session"},
        {"id": "lbl_sessions", "type": "text", "x": 15, "y": 140, "fontSize": 14, "strokeColor": "#868e96", "text": "ACTIVE SESSIONS"},
        {"id": "sess_1", "type": "rectangle", "x": 15, "y": 155, "width": 230, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "💬 VinFast EV Telemetry Scan"},
        {"id": "sess_2", "type": "rectangle", "x": 15, "y": 210, "width": 230, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 V-GREEN Charger Overheat"},
        {"id": "sess_3", "type": "rectangle", "x": 15, "y": 265, "width": 230, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Xanh SM Trips Ledger Audit"},
        {"id": "sess_4", "type": "rectangle", "x": 15, "y": 320, "width": 230, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Customer Feedback NLP"},
        {"id": "lbl_repos", "type": "text", "x": 15, "y": 400, "fontSize": 14, "strokeColor": "#868e96", "text": "DATASET REPOSITORY"},
        {"id": "ds_dropdown", "type": "rectangle", "x": 15, "y": 415, "width": 230, "height": 40, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "📦 real_vinfast_ev_telemetry"},

        {"id": "hitl_bar", "type": "rectangle", "x": 270, "y": 70, "width": 500, "height": 45, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "⚖️ Pending Governance Review (3 rules)  |  [✓ Approve All]  [✗ Reject]"},
        {"id": "user_msg", "type": "rectangle", "x": 280, "y": 125, "width": 480, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "👤 User: Detect anomalies & propose quality rules for VinFast EV Telemetry"},
        {"id": "agent_msg_1", "type": "rectangle", "x": 280, "y": 180, "width": 480, "height": 65, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🤖 Orchestrator Agent (Gemma-4-26b):\nExecuting Tri-Detector Suite (Z-Score + IQR + Isolation Forest ML)"},
        {"id": "agent_msg_2", "type": "rectangle", "x": 280, "y": 255, "width": 480, "height": 75, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "⚠️ Anomaly Detector Agent:\nFlagged 28 anomalies (GSM Basement Blackout, Negative SOC -12.5%, Overvoltage 9999V)"},
        
        {"id": "rule_card_bg", "type": "rectangle", "x": 280, "y": 340, "width": 480, "height": 150, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Rule Proposer Agent Proposal #1:\nColumn: battery_soc  |  Type: range_check  |  Severity: CRITICAL\nExpression: battery_soc >= 0.0 AND battery_soc <= 100.0\nDescription: Enforce valid non-negative battery state of charge"},
        {"id": "btn_approve", "type": "rectangle", "x": 295, "y": 440, "width": 95, "height": 35, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Approve"},
        {"id": "btn_reject", "type": "rectangle", "x": 400, "y": 440, "width": 85, "height": 35, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "✗ Reject"},
        {"id": "btn_edit", "type": "rectangle", "x": 495, "y": 440, "width": 75, "height": 35, "backgroundColor": "#e9ecef", "strokeColor": "#868e96", "text": "✏️ Edit"},
        {"id": "btn_next_step", "type": "rectangle", "x": 580, "y": 440, "width": 165, "height": 35, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "▶ Run Clean DB Pipeline"},

        {"id": "chat_input", "type": "rectangle", "x": 270, "y": 795, "width": 500, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "💬 Type command or ask AI steward...                                          [📎 Upload]"},

        {"id": "tab_bar", "type": "rectangle", "x": 790, "y": 70, "width": 480, "height": 40, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "[📊 Profile]  [🛡️ Rules]  [⚠️ Anomaly & RCA]  [📋 Audit]  [🔀 Diff]"},
        {"id": "active_tab_line", "type": "rectangle", "x": 975, "y": 105, "width": 115, "height": 4, "backgroundColor": "#0c8599", "text": ""},
        
        {"id": "anom_score_card", "type": "rectangle", "x": 800, "y": 125, "width": 460, "height": 75, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "🔥 Dual Composite Anomaly Score: S_composite = 0.89\n(Robust MAD Z-Score: 6.50  |  Isolation Forest Score: 0.92)"},
        {"id": "anom_breakdown", "type": "rectangle", "x": 800, "y": 210, "width": 460, "height": 165, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "📌 Detected Defects & Anomalies Breakdown:\n1. GSM Underground Blackout | Null GPS & Timestamp  | 25 rows\n2. Negative Battery SOC     | battery_soc = -12.5%  | 15 rows\n3. CAN-Bus Overvoltage Spikes| battery_voltage=9999V| 8 rows\n4. Motor RPM Mismatch       | Speed=0 & RPM=14500  | 12 rows"},
        {"id": "rca_box", "type": "rectangle", "x": 800, "y": 385, "width": 460, "height": 155, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🩺 Diagnosis Agent RCA (dbt Lineage Graph):\nRoot Cause: VinFast VF8 entered Vincom Underground Basement.\nGPS connection dropped & CAN-bus voltage telemetry spiked.\nRemediation: Apply linear interpolation & quarantine corrupt rows."},
        {"id": "cleandb_box", "type": "rectangle", "x": 800, "y": 550, "width": 460, "height": 125, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✨ Clean DB Execution Summary:\nClean Records: 940 / 1000 rows (94.0%)\nQuarantine Table: 60 rows (6.0%)\nSHA-256 Lineage Hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4"}
    ]

    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 860" width="1280" height="860" style="background:#ffffff; font-family:sans-serif;">'
    ]

    for el in elements:
        bg = el.get("backgroundColor", "#ffffff")
        sc = el.get("strokeColor", "#1e1e1e")
        if el["type"] == "rectangle":
            sw = el.get("strokeWidth", 1)
            svg_parts.append(f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" height="{el["height"]}" fill="{bg}" stroke="{sc}" stroke-width="{sw}" rx="4" />')
            if el.get("text"):
                lines = el["text"].split("\n")
                startY = el["y"] + (el["height"] / 2) - (len(lines) - 1) * 10
                for idx, line in enumerate(lines):
                    # Escape xml special chars
                    line_esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    svg_parts.append(f'<text x="{el["x"] + 12}" y="{startY + idx * 20}" font-size="13" fill="{sc}" font-weight="500">{line_esc}</text>')
        elif el["type"] == "text":
            text_esc = el["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            svg_parts.append(f'<text x="{el["x"]}" y="{el["y"]}" font-size="{el.get("fontSize", 14)}" fill="{sc}" font-weight="bold">{text_esc}</text>')

    svg_parts.append('</svg>')
    
    with open("docs/UI_UX_WIREFRAME_V3.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print("SVG generated successfully at docs/UI_UX_WIREFRAME_V3.svg")

if __name__ == "__main__":
    generate_svg()
