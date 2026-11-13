"""Dependency-free, vector PDF rendering for persisted VoiceShield reports."""
from datetime import timezone
import textwrap


PAGE_W, PAGE_H = 595.28, 841.89
INK = (0.07, 0.13, 0.16)
MUTED = (0.34, 0.43, 0.46)
TEAL = (0.05, 0.45, 0.41)
PALE = (0.93, 0.97, 0.96)
LINE = (0.83, 0.88, 0.88)
WHITE = (1, 1, 1)
AMBER = (0.68, 0.40, 0.12)


def _pdf_text(value) -> str:
    """Escape a report string for a PDF literal string using built-in WinAnsi fonts."""
    value = str(value if value is not None else "")
    value = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    value = (value.replace("→", "->").replace("…", "...").replace("−", "-")
             .replace("—", "-").replace("–", "-").replace("•", "-").replace("·", " | "))
    value = value.encode("cp1252", errors="replace").decode("cp1252")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _fmt_time(value) -> str:
    if value is None:
        return "Unavailable"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class _Report:
    def __init__(self, record):
        self.record = record
        self.pages: list[list[str]] = []
        self.y = 0
        self.new_page()

    @staticmethod
    def _color(rgb, stroke=False):
        op = "RG" if stroke else "rg"
        return f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} {op}"

    def new_page(self):
        self.pages.append([])
        ops = self.pages[-1]
        ops.append("q")
        ops.append(self._color(INK))
        ops.append(f"0 {PAGE_H - 92:.2f} {PAGE_W:.2f} 92 re f")
        ops.append(self._color(TEAL))
        ops.append(f"0 {PAGE_H - 92:.2f} 7 92 re f")
        self.text(40, 27, "VOICE", 11, WHITE, bold=True)
        self.text(76, 27, "SHIELD", 11, (0.53, 0.88, 0.81), bold=True)
        self.text(40, 49, "AI DIGITAL FORENSICS", 7.5, (0.72, 0.81, 0.82), bold=True)
        self.text(367, 27, "INVESTIGATION REPORT", 8, WHITE, bold=True)
        self.text(367, 49, f"RECORD VS-{self.record.id:06d}  |  {_fmt_time(self.record.created_at)}", 7, (0.72, 0.81, 0.82))
        ops.append("Q")
        self.y = 116

    def text(self, x, top, value, size=10, color=INK, bold=False):
        font = "F2" if bold else "F1"
        baseline = PAGE_H - top - size
        self.pages[-1].append(self._color(color))
        self.pages[-1].append(f"BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {baseline:.2f} Tm ({_pdf_text(value)}) Tj ET")

    def rect(self, x, top, w, h, color, stroke=None):
        y = PAGE_H - top - h
        if stroke:
            self.pages[-1].append(self._color(stroke, stroke=True))
            self.pages[-1].append(self._color(color))
            self.pages[-1].append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")
        else:
            self.pages[-1].append(self._color(color))
            self.pages[-1].append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def line(self, x1, top1, x2, top2, color=LINE, width=0.6):
        self.pages[-1].append(self._color(color, stroke=True))
        self.pages[-1].append(f"{width:.2f} w {x1:.2f} {PAGE_H-top1:.2f} m {x2:.2f} {PAGE_H-top2:.2f} l S")

    def ensure(self, height):
        if self.y + height > PAGE_H - 58:
            self.new_page()

    def section(self, title, kicker=None):
        self.ensure(37)
        if kicker:
            self.text(40, self.y, kicker.upper(), 7.2, TEAL, bold=True)
            self.y += 12
        self.text(40, self.y, title, 14, INK, bold=True)
        self.y += 23
        self.line(40, self.y, PAGE_W - 40, self.y)
        self.y += 12

    def paragraph(self, value, size=9.2, color=INK, indent=0, line_height=None, bullet=False):
        value = str(value or "").strip()
        if not value:
            return
        line_height = line_height or size * 1.48
        usable = PAGE_W - 80 - indent
        width = max(24, int(usable / (size * 0.50)))
        for source_line in value.splitlines() or [value]:
            wrapped = textwrap.wrap(source_line, width=width, break_long_words=True, break_on_hyphens=False) or [""]
            for index, item in enumerate(wrapped):
                self.ensure(line_height + 2)
                prefix = "- " if bullet and index == 0 else ("  " if bullet else "")
                self.text(40 + indent, self.y, prefix + item, size, color)
                self.y += line_height

    def badge(self, value, x, top, color=TEAL):
        label = str(value or "unknown").replace("_", " ").upper()
        w = min(180, max(66, len(label) * 5.2 + 18))
        self.rect(x, top, w, 20, PALE)
        self.text(x + 9, top + 5, label, 7.2, color, bold=True)

    def draw_hero(self):
        record = self.record
        name = {"audio": "VOICE AUTHENTICITY SCREENING", "image": "SCREENSHOT CLAIM ANALYSIS", "text": "TEXT CLAIM SCREENING"}.get(record.kind, "FORENSIC ANALYSIS")
        self.text(40, self.y, name, 8, TEAL, bold=True)
        self.y += 18
        self.text(40, self.y, record.label or "Analysis report", 21, INK, bold=True)
        self.y += 31
        summary = record.summary or "No analysis summary was returned."
        wrapped = textwrap.wrap(summary, width=100, break_long_words=True) or [""]
        box_h = 18 + len(wrapped) * 13
        self.rect(40, self.y, PAGE_W - 80, box_h, PALE)
        for i, line in enumerate(wrapped):
            self.text(52, self.y + 9 + i * 13, line, 8.5, INK)
        self.y += box_h + 16

    def draw_metrics(self):
        record = self.record
        metadata = record.processing_metadata or {}
        metrics = []
        if record.risk_score is not None:
            label = "SPOOF-PATTERN PROBABILITY" if record.kind == "audio" else "FAKE-PATTERN SCORE"
            metrics.insert(0, (label, f"{record.risk_score:.1f}%"))
        if record.model_confidence is not None:
            metrics.append(("MODEL CONFIDENCE", f"{record.model_confidence * 100:.1f}%"))
        if record.kind == "image" and metadata.get("ocr_confidence") is not None:
            metrics.append(("OCR CONFIDENCE", f"{metadata['ocr_confidence'] * 100:.1f}%"))
        if record.kind == "audio" and metadata.get("duration_seconds") is not None:
            metrics.append(("AUDIO DURATION", f"{float(metadata['duration_seconds']):.1f} sec"))
        if not metrics:
            self.paragraph("No numeric score was returned by the analysis pipeline.", size=9, color=MUTED)
            return
        gap, x0 = 9, 40
        w = (PAGE_W - 80 - (len(metrics) - 1) * gap) / len(metrics)
        for index, (label, value) in enumerate(metrics):
            x = x0 + index * (w + gap)
            self.rect(x, self.y, w, 67, WHITE, LINE)
            self.text(x + 10, self.y + 10, label, 6.5, MUTED, bold=True)
            self.text(x + 10, self.y + 31, value[:30], 12.5 if len(value) < 20 else 9, TEAL, bold=True)
        self.y += 78

    def draw_provenance(self):
        record = self.record
        metadata = record.processing_metadata or {}
        self.section("Method and provenance", "How this result was produced")
        self.paragraph(f"Analysis ID: VS-{record.id:06d}    Created: {_fmt_time(record.created_at)}", size=8.5, color=MUTED)
        self.paragraph(f"Model: {record.model_name or 'No model returned'}    Status: {(record.model_status or 'unknown').replace('_', ' ')}    Language: {record.language or 'Not detected'}", size=8.5)
        if record.kind == "audio":
            method = "The uploaded recording was decoded, converted to mono 16 kHz audio, and evaluated in non-overlapping four-second windows by the configured ONNX checkpoint. The report includes only window scores returned by that model."
        elif record.kind == "image":
            method = "The screenshot was processed with local OCR, and the extracted text was passed to the configured language-specific text classifier. No pixel-level image manipulation detector is reported by this pipeline."
        else:
            method = "The supplied text was routed to the configured language-specific text classification checkpoint. Publisher fact-check lookups, when returned, are listed separately from the model output."
        self.paragraph(method, size=8.4, color=MUTED)
        fields = [
            ("Source file", metadata.get("source_filename")),
            ("Media type", metadata.get("source_content_type")),
            ("File size", f"{metadata['bytes_received']:,} bytes" if isinstance(metadata.get("bytes_received"), int) else None),
            ("SHA-256", metadata.get("source_sha256")),
            ("Characters analyzed", str(metadata["input_characters"]) if isinstance(metadata.get("input_characters"), int) else None),
            ("Audio sample rate", f"{metadata['sample_rate']:,} Hz" if metadata.get("sample_rate") else None),
            ("Segments", str(metadata["segments"]) if isinstance(metadata.get("segments"), int) else None),
        ]
        for label, value in fields:
            if value:
                self.paragraph(f"{label}: {value}", size=8.1, color=MUTED)

    def draw_evidence(self):
        evidence = self.record.evidence or []
        segments = [item for item in evidence if isinstance(item, dict) and isinstance(item.get("spoof_probability"), (int, float))]
        if segments:
            self.section("Audio window breakdown", "Model outputs")
            for item in segments:
                self.ensure(33)
                start = item.get("start_seconds", 0)
                end = item.get("end_seconds", 0)
                score = max(0, min(1, float(item["spoof_probability"])))
                self.text(44, self.y, f"{float(start):.1f}-{float(end):.1f} sec", 8.2, MUTED)
                self.text(489, self.y, f"{score*100:.1f}%", 8.2, AMBER, bold=True)
                self.y += 12
                self.rect(44, self.y, PAGE_W - 88, 5, LINE)
                self.rect(44, self.y, (PAGE_W - 88) * score, 5, AMBER)
                self.y += 12
        self.section("Findings and evidence", "Recorded analysis output")
        if not evidence:
            self.paragraph("No evidence items were returned by the analysis pipeline.", size=9, color=MUTED)
            return
        for item in evidence:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("type") or "Evidence item")
            quote = str(item.get("quote") or "No supporting detail was returned.")
            quote_lines = textwrap.wrap(quote, width=94, break_long_words=True) or [""]
            height = 18 + len(quote_lines) * 12
            self.ensure(height + 8)
            self.rect(40, self.y, 3, height, TEAL if item.get("type") in {"ocr", "fact_check", "classification", "audio_segment"} else LINE)
            self.text(52, self.y + 2, title, 8.7, INK, bold=True)
            for i, line in enumerate(quote_lines):
                self.text(52, self.y + 17 + i * 12, line, 8, MUTED)
            self.y += height + 8

    def draw_reviews(self):
        checks = self.record.fact_checks or []
        if not checks:
            self.section("Publisher review lookup", "Independent source check")
            self.paragraph(f"Lookup status: {(self.record.fact_check_status or 'unknown').replace('_', ' ')}. No published review records were returned with this report.", size=8.7, color=MUTED)
            return
        self.section("Published fact-check reviews", "Independent source check")
        for check in checks:
            if not isinstance(check, dict):
                continue
            self.ensure(54)
            publisher = check.get("publisher") or "Fact-check publisher"
            rating = check.get("rating") or "Rating not provided"
            self.text(44, self.y, f"{publisher}  |  {rating}", 8.5, TEAL, bold=True)
            self.y += 14
            self.paragraph(check.get("title") or "Published review", size=8.5, indent=4)
            date_url = "  |  ".join(x for x in [check.get("review_date"), check.get("url")] if x)
            if date_url:
                self.paragraph(date_url, size=7.2, color=MUTED, indent=4)
            self.y += 7

    def draw_limitations(self):
        self.section("Limitations and interpretation", "Read before relying on this report")
        self.paragraph("A model score is a prediction from the named checkpoint, not proof of authenticity or factual truth. Performance depends on the model's training data, language, recording conditions, and distribution shift. An empty score means the pipeline did not return one.", size=8.5, color=MUTED)
        if self.record.kind == "image":
            self.paragraph("Screenshot analysis evaluates OCR-recognized text. It does not determine whether the image itself was edited, synthesized, or altered.", size=8.5, color=MUTED)
        self.paragraph(f"Fact-check lookup status: {(self.record.fact_check_status or 'unknown').replace('_', ' ')}. A missing review is not evidence that a claim is true or false.", size=8.5, color=MUTED)

    def build(self) -> bytes:
        self.draw_hero()
        self.draw_metrics()
        self.draw_provenance()
        self.draw_evidence()
        self.draw_reviews()
        self.draw_limitations()
        for page_number, page in enumerate(self.pages, start=1):
            page.append(self._color(MUTED))
            footer_y = 29
            page.append(f"BT /F1 7 Tf 1 0 0 1 40 {footer_y} Tm (VOICE SHIELD  |  PRIVATE REPORT  |  PAGE {page_number}) Tj ET")
            page.append(f"{self._color(LINE, stroke=True)} 0.5 w 40 43 m {PAGE_W-40:.2f} 43 l S")
        return _serialize_pdf(self.pages)


def _serialize_pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes | None] = [None] * (6 + len(pages) * 2)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{6 + i*2} 0 R" for i in range(len(pages)))
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    objects[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"
    for index, instructions in enumerate(pages):
        page_id = 6 + index * 2
        content_id = page_id + 1
        stream = ("\n".join(instructions) + "\n").encode("cp1252", errors="replace")
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] "
                            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> /Contents {content_id} 0 R >>").encode("ascii")
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream"
    output = bytearray(b"%PDF-1.4\n% VoiceShield\n")
    offsets = [0] * len(objects)
    for object_id in range(1, len(objects)):
        offsets[object_id] = len(output)
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(objects[object_id] or b"null")
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def render_analysis_pdf(record) -> bytes:
    """Render a persisted Analysis row without inventing any score or evidence."""
    return _Report(record).build()
