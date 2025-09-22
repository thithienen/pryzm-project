import os, re, json, argparse, datetime as dt, hashlib, shutil
from pypdf import PdfReader, PdfWriter
import yaml

def normspace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def should_keep(text: str, keywords_ci):
    t = (text or "").lower()
    return any(k in t for k in keywords_ci)

def extract_matching_pages(pdf_path: str, keywords_ci, max_keep=None):
    reader = PdfReader(pdf_path)
    keep = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if should_keep(text, keywords_ci):
            keep.append((i, text))
            if max_keep and len(keep) >= max_keep:
                break
    return keep

def write_trimmed_pdf(src_pdf: str, page_pairs, out_pdf: str):
    writer = PdfWriter()
    reader = PdfReader(src_pdf)
    for i, _ in page_pairs:
        writer.add_page(reader.pages[i])
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    with open(out_pdf, "wb") as f:
        writer.write(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="scripts/sources.yml")
    ap.add_argument("--max-keep", type=int, default=None, help="cap pages per PDF")
    ap.add_argument("--fallback-first-page", action="store_true",
                    help="if no pages match, include page 1 to ensure minimal context")
    ap.add_argument("--backend-docs", default="backend/docs.json",
                    help="where to also write a copy of docs.json for the backend")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.manifest, "r", encoding="utf-8"))
    out_dir = cfg.get("out_dir", "out")
    trimmed_dir = os.path.join(out_dir, "trimmed")
    docs_out = os.path.join(out_dir, "docs.json")
    os.makedirs(trimmed_dir, exist_ok=True)

    default_keywords = cfg.get("default_keywords", [])
    sources = cfg["sources"]

    entries = []
    today = dt.date.today().isoformat()

    for s in sources:
        title = s["title"]
        local_path = s.get("local_path")
        if not local_path:
            raise ValueError(f"Missing local_path for source: {title}")
        if not os.path.isabs(local_path):
            local_path = os.path.normpath(os.path.join(os.getcwd(), local_path))
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"PDF not found: {local_path}")

        doc_date = s.get("doc_date", today)
        keywords = [k.lower() for k in (s.get("keywords") or default_keywords)]

        hid = hashlib.md5((title + local_path).encode("utf-8")).hexdigest()[:10]

        print(f"[scan] {title}  ({os.path.basename(local_path)})")
        matches = extract_matching_pages(local_path, keywords, max_keep=args.max_keep)

        if not matches and args.fallback_first_page:
            print("  ! no keyword matches; including first page as fallback")
            reader = PdfReader(local_path)
            txt = normspace(reader.pages[0].extract_text() or "")
            matches = [(0, txt)]

        if not matches:
            print("  ! no pages kept; skipping this document")
            continue

        trimmed_pdf = os.path.join(trimmed_dir, f"{hid}.pdf")
        write_trimmed_pdf(local_path, matches, trimmed_pdf)

        pages = [{"pageno": i + 1, "text": normspace(txt)} for (i, txt) in matches]
        entries.append({
            "id": hid,
            "title": title,
            "url": "",                 # local source
            "doc_date": doc_date,
            "pages": pages
        })

    # Write primary docs.json
    os.makedirs(out_dir, exist_ok=True)
    with open(docs_out, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # Copy to backend/docs.json (or custom path)
    backend_docs = args.backend_docs
    os.makedirs(os.path.dirname(backend_docs), exist_ok=True)
    shutil.copyfile(docs_out, backend_docs)

    print(f"\nWrote corpus: {docs_out}")
    print(f"Copied to   : {backend_docs}")
    print(f"Trimmed PDFs: {trimmed_dir}")
    print(f"Entries     : {len(entries)}")

if __name__ == "__main__":
    main()
