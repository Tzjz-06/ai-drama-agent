"""使用 PaddleOCR 提取扫描剧本中的中文文本。"""

from __future__ import annotations

import io
import threading
from typing import Any

import numpy as np
from PIL import Image

try:
    import fitz
except ImportError:  # pragma: no cover - 仅在运行环境缺少 PyMuPDF 时触发
    fitz = None


class OCRUnavailableError(RuntimeError):
    """运行环境缺少 PaddleOCR 或其模型初始化失败。"""


class PaddleScriptOCR:
    """线程安全的 PaddleOCR 适配器，模型只在第一次 OCR 时初始化。"""

    def __init__(self) -> None:
        self._engine: Any | None = None
        self._lock = threading.Lock()

    def extract_pdf(self, raw: bytes) -> str:
        if fitz is None:
            raise OCRUnavailableError("缺少 PyMuPDF（fitz），无法解析扫描版 PDF。")
        try:
            document = fitz.open(stream=raw, filetype="pdf")
        except Exception as error:
            raise ValueError("PDF 文件无法打开，可能是文件已损坏。") from error

        pages: list[str] = []
        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pages.append(self.extract_image(pixmap.tobytes("png")))
        finally:
            document.close()
        return "\n\n".join(page for page in pages if page.strip())

    def extract_image(self, raw: bytes) -> str:
        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as error:
            raise ValueError("图片无法解析，可能是文件已损坏。") from error
        result = self._predict(np.asarray(image))
        return "\n".join(result)

    def _predict(self, image: np.ndarray[Any, Any]) -> list[str]:
        engine = self._get_engine()
        try:
            results = engine.predict(image)
        except Exception as error:
            raise OCRUnavailableError(f"PaddleOCR 识别失败：{error}") from error

        texts: list[str] = []
        for item in results:
            payload = _result_payload(item)
            recognition = payload.get("rec_texts")
            if isinstance(recognition, list):
                texts.extend(str(text).strip() for text in recognition if str(text).strip())
                continue

            legacy_lines = payload.get("rec_text") or payload.get("text")
            if isinstance(legacy_lines, list):
                texts.extend(str(text).strip() for text in legacy_lines if str(text).strip())
        return texts

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is not None:
                return self._engine
            try:
                from paddleocr import PaddleOCR

                self._engine = PaddleOCR(
                    lang="ch",
                    device="cpu",
                    enable_mkldnn=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            except Exception as error:
                raise OCRUnavailableError(
                    "PaddleOCR 初始化失败，请确认已安装 paddleocr、paddlepaddle 及中文模型依赖。"
                ) from error
        return self._engine


_OCR = PaddleScriptOCR()


def _result_payload(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        value = item.get("res")
        return value if isinstance(value, dict) else item
    for attribute in ("json", "to_json"):
        value = getattr(item, attribute, None)
        if callable(value):
            value = value()
        if isinstance(value, str):
            import json

            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                continue
        if isinstance(value, dict):
            nested = value.get("res")
            return nested if isinstance(nested, dict) else value
    return {}


def extract_scanned_script(raw: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        return _OCR.extract_pdf(raw)
    return _OCR.extract_image(raw)
