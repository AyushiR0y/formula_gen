🧠 Formula Extractor AI
This is a full-stack AI-powered tool that lets users upload product specification files (PDF, Word, text, or image). It uses Google Gemini and HuggingFace models to extract structured mathematical formulas related to insurance and finance, and also has a fallback local parser for offline use.

🛠️ Tech Stack
Frontend: Angular

Backend: Flask (Python)

LLM Providers: Google Gemini API + HuggingFace API

Local Parser: Regex-based formula extractor

Text Extraction: pdfminer, docx, pytesseract, Pillow

CORS & File Uploads: Enabled

Export: Formulas viewable and downloadable in Excel (from Angular)

📁 Supported File Formats
.pdf, .docx, .doc, .txt

.png, .jpg, .jpeg, .tiff, .bmp (via OCR)
