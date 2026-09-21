from __future__ import annotations

import math
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from PIL import Image, ImageEnhance, ImageOps
import pytesseract

from app.config import settings

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

from .models import BoundingBox, PageElement


@dataclass
class OCRPageResult:
    text: str
    raw_text: str = ""
    elements: List[PageElement] = field(default_factory=list)
    confidence: Optional[float] = None


class OCRService:
    def extract_page(self, file_path: str, page_number: int, document_id: str) -> OCRPageResult:
        raise NotImplementedError


class LocalTesseractOCR(OCRService):
    @staticmethod
    def build_tesseract_config() -> str:
        lang = os.getenv("TESSERACT_LANG") or settings.tesseract_lang or "eng"
        psm = os.getenv("TESSERACT_PSM") or str(settings.ocr_psm or 6)
        oem = os.getenv("TESSERACT_OEM") or str(settings.ocr_oem or 3)
        return f"--psm {psm} --oem {oem} -l {lang}"

    @staticmethod
    def normalize_ocr_text(text: str) -> str:
        """Whitespace-only normalization. OCR text is never altered, inserted
        or re-branded: byte-faithful extraction is a Responsible-AI invariant."""
        normalized = text or ""
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized).strip()
        normalized = normalized.replace("\n ", "\n")
        return normalized

    @staticmethod
    def resolve_tesseract_cmd() -> str:
        configured = os.getenv("TESSERACT_CMD") or settings.tesseract_cmd
        if configured and os.path.exists(configured):
            os.environ["TESSERACT_CMD"] = configured
            return configured

        discovered = shutil.which("tesseract")
        if discovered:
            os.environ["TESSERACT_CMD"] = discovered
            return discovered

        default_locations = [
            os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR", "tesseract.exe"),
            os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR", "tesseract.exe"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for candidate in default_locations:
            if os.path.exists(candidate):
                os.environ["TESSERACT_CMD"] = candidate
                settings.tesseract_cmd = candidate
                return candidate

        raise RuntimeError("Tesseract OCR binary is not installed or configured. Set TESSERACT_CMD to the executable path.")

    def extract_page(self, file_path: str, page_number: int, document_id: str) -> OCRPageResult:
        if fitz is None:
            raise RuntimeError("PyMuPDF is required for scanned PDF rendering.")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF not found: {file_path}")

        tess_cmd = self.resolve_tesseract_cmd()
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

        doc = fitz.open(file_path)
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Page {page_number} is out of range for PDF with {len(doc)} pages.")

        page = doc.load_page(page_number - 1)
        dpi = 300
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        gray = ImageOps.grayscale(image)
        gray = ImageOps.autocontrast(gray)
        base_variant = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        sharp_variant = ImageEnhance.Sharpness(base_variant).enhance(2.0)
        contrast_variant = ImageEnhance.Contrast(base_variant).enhance(1.8)

        candidate_images = {
            "sharp": sharp_variant,
            "contrast": contrast_variant,
            "base": base_variant,
        }

        candidate_configs = [self.build_tesseract_config(), "--psm 11 --oem 3 -l eng", "--psm 4 --oem 3 -l eng", "--psm 6 --oem 3 -l eng -c preserve_interword_spaces=1"]
        best_text = ""
        best_config = candidate_configs[0]
        best_score = -1

        for config in candidate_configs:
            for _, candidate in candidate_images.items():
                current_text = pytesseract.image_to_string(candidate, config=config)
                if not current_text:
                    continue
                # Score candidates purely by recognized word count - no branding
                # or content bonuses that would bias extraction.
                word_count = len(re.findall(r"[A-Za-z]{3,}", current_text))
                score = word_count
                if score > best_score:
                    best_score = score
                    best_text = current_text
                    best_config = config

        raw_text = best_text or pytesseract.image_to_string(sharp_variant, config=best_config)
        raw_text = raw_text.strip()
        normalized_text = self.normalize_ocr_text(raw_text)

        data = pytesseract.image_to_data(sharp_variant, output_type=pytesseract.Output.DICT, config=best_config)
        elements: List[PageElement] = []
        reading_order = 0
        text_lines: List[Dict[str, Any]] = []

        for idx, word in enumerate(data.get("text", [])):
            cleaned = (word or "").strip()
            if not cleaned:
                continue

            conf_value = data.get("conf", [None] * len(data.get("text", [])))[idx]
            confidence = None
            try:
                if conf_value not in (None, "", "-1"):
                    confidence = float(conf_value) / 100.0
            except (TypeError, ValueError):
                confidence = None

            bbox = BoundingBox(
                x1=float(data.get("left", [0])[idx]),
                y1=float(data.get("top", [0])[idx]),
                x2=float(data.get("left", [0])[idx]) + float(data.get("width", [0])[idx]),
                y2=float(data.get("top", [0])[idx]) + float(data.get("height", [0])[idx]),
            )

            text_lines.append(
                {
                    "text": cleaned,
                    "bbox": bbox,
                    "confidence": confidence,
                    "block": int(data.get("block_num", [0])[idx]),
                    "par": int(data.get("par_num", [0])[idx]),
                    "line": int(data.get("line_num", [0])[idx]),
                    "x": float(data.get("left", [0])[idx]),
                    "y": float(data.get("top", [0])[idx]),
                }
            )

        # Group words by OCR line; preserve reading order for text blocks.
        grouped_by_line: Dict[tuple[int, int, int], List[Dict[str, Any]]] = {}
        for item in text_lines:
            key = (item["block"], item["par"], item["line"])
            grouped_by_line.setdefault(key, []).append(item)

        line_keys = sorted(grouped_by_line.keys(), key=lambda key: (key[0], key[1], key[2]))
        for key in line_keys:
            items = sorted(grouped_by_line[key], key=lambda item: item["x"])
            reading_order += 1
            line_text = " ".join(item["text"] for item in items)
            if not line_text:
                continue

            bbox = BoundingBox(
                x1=min(item["bbox"].x1 for item in items if item["bbox"].x1 is not None),
                y1=min(item["bbox"].y1 for item in items if item["bbox"].y1 is not None),
                x2=max(item["bbox"].x2 for item in items if item["bbox"].x2 is not None),
                y2=max(item["bbox"].y2 for item in items if item["bbox"].y2 is not None),
            )
            confidences = [item["confidence"] for item in items if item["confidence"] is not None]
            confidence = sum(confidences) / len(confidences) if confidences else None
            elements.append(
                PageElement(
                    document_id=document_id,
                    page_number=page_number,
                    type="paragraph",
                    text=line_text,
                    bbox=bbox,
                    confidence=confidence,
                    reading_order=reading_order,
                    metadata={"source": "ocr", "ocr_block": key[0], "ocr_par": key[1], "ocr_line": key[2]},
                )
            )

        table_rows = self._extract_table_rows(elements)
        if table_rows:
            elements = self._merge_table_elements(elements, table_rows)

        text = "\n".join(element.text for element in elements if element.text and element.type == "paragraph")
        text = self.normalize_ocr_text(text) if text else ""
        return OCRPageResult(text=text, raw_text=normalized_text, elements=elements, confidence=self._aggregate_confidence(elements))

    def _aggregate_confidence(self, elements: Iterable[PageElement]) -> Optional[float]:
        values = [element.confidence for element in elements if element.confidence is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def _extract_table_rows(self, elements: Sequence[PageElement]) -> List[List[PageElement]]:
        row_groups: Dict[int, List[PageElement]] = {}
        candidate_rows: List[List[PageElement]] = []
        for element in elements:
            if element.type != "paragraph":
                continue
            if element.bbox is None:
                continue
            text = (element.text or "").strip()
            if not text:
                continue
            if "|" not in text and not re.search(r"\d+\s*\|\s*\d+", text):
                continue
            row_key = int(math.floor((element.bbox.y1 or 0) / 20.0)) if element.bbox.y1 is not None else 0
            row_groups.setdefault(row_key, []).append(element)

        for _row_key in sorted(row_groups.keys()):
            ordered = sorted(row_groups[_row_key], key=lambda item: item.bbox.x1 if item.bbox and item.bbox.x1 is not None else 0)
            candidate_rows.append(ordered)

        if len(candidate_rows) < 2:
            return []

        # Only collapse into table cells when multiple rows genuinely look tabular.
        if all(len(row) >= 1 for row in candidate_rows):
            return candidate_rows
        return []

    def _merge_table_elements(self, elements: List[PageElement], rows: List[List[PageElement]]) -> List[PageElement]:
        table_elements: List[PageElement] = []
        table_id = str(uuid.uuid4())
        for idx, row in enumerate(rows):
            if not row:
                continue
            ordered_cells = sorted(row, key=lambda item: item.bbox.x1 if item.bbox and item.bbox.x1 is not None else 0)
            table_cols = []
            current_bucket: List[PageElement] = []
            last_x = None
            for cell in ordered_cells:
                x_start = cell.bbox.x1 if cell.bbox and cell.bbox.x1 is not None else 0
                if last_x is not None and x_start - last_x > 30:
                    table_cols.append(current_bucket)
                    current_bucket = []
                current_bucket.append(cell)
                last_x = x_start
            if current_bucket:
                table_cols.append(current_bucket)

            for col_index, bucket in enumerate(table_cols):
                cell_text = " ".join(item.text for item in bucket if item.text)
                if not cell_text:
                    continue
                cell_bbox = None
                if bucket and all(item.bbox is not None for item in bucket):
                    xs = [item.bbox.x1 for item in bucket if item.bbox and item.bbox.x1 is not None]
                    ys = [item.bbox.y1 for item in bucket if item.bbox and item.bbox.y1 is not None]
                    x2s = [item.bbox.x2 for item in bucket if item.bbox and item.bbox.x2 is not None]
                    y2s = [item.bbox.y2 for item in bucket if item.bbox and item.bbox.y2 is not None]
                    if xs and ys and x2s and y2s:
                        cell_bbox = BoundingBox(x1=min(xs), y1=min(ys), x2=max(x2s), y2=max(y2s))

                table_elements.append(
                    PageElement(
                        document_id=row[0].document_id,
                        page_number=row[0].page_number,
                        type="table_cell",
                        text=cell_text,
                        bbox=cell_bbox,
                        confidence=next((item.confidence for item in bucket if item.confidence is not None), None),
                        reading_order=row[0].reading_order,
                        parent_id=table_id,
                        metadata={"row_index": idx, "column_index": col_index, "source": "ocr_table"},
                    )
                )

        if table_elements:
            table_wrapper = PageElement(
                document_id=elements[0].document_id if elements else "",
                page_number=elements[0].page_number if elements else 1,
                type="table",
                text="",
                bbox=None,
                confidence=None,
                reading_order=0,
                parent_id=None,
                metadata={"table_id": table_id, "source": "ocr_table"},
            )
            return [*elements, table_wrapper, *table_elements]

        return elements


ocr_service: OCRService = LocalTesseractOCR()
