import os
import json
from pypdf import PdfReader

def transcribe_pdf_to_json(pdf_path, json_path):
    """
    Transcribe all pages from a PDF file and save as JSON.
    
    Args:
        pdf_path (str): Path to the input PDF file
        json_path (str): Path to the output JSON file
    """
    try:
        reader = PdfReader(pdf_path)
        pages_data = []
        
        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
                pages_data.append({
                    "page": page_num,
                    "text": text.strip()
                })
            except Exception as e:
                print(f"  Warning: Failed to extract text from page {page_num}: {e}")
                pages_data.append({
                    "page": page_num,
                    "text": "",
                    "error": str(e)
                })
        
        # Create the JSON structure
        result = {
            "filename": os.path.basename(pdf_path),
            "total_pages": len(reader.pages),
            "pages": pages_data
        }
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Write the JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"  [OK] Transcribed {len(reader.pages)} pages")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Error processing PDF: {e}")
        return False

def main():
    # Define paths
    raw_dir = "scripts/out/raw"
    transcribed_dir = "scripts/out/transcribed"
    
    # Check if raw directory exists
    if not os.path.exists(raw_dir):
        print(f"Error: Raw directory '{raw_dir}' not found!")
        return
    
    # Get all PDF files from raw directory
    pdf_files = [f for f in os.listdir(raw_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in '{raw_dir}'")
        return
    
    print(f"Found {len(pdf_files)} PDF files to transcribe...")
    
    successful = 0
    failed = 0
    
    # Process each PDF
    for pdf_filename in pdf_files:
        print(f"\nProcessing: {pdf_filename}")
        
        pdf_path = os.path.join(raw_dir, pdf_filename)
        
        # Create corresponding JSON filename
        json_filename = os.path.splitext(pdf_filename)[0] + '.json'
        json_path = os.path.join(transcribed_dir, json_filename)
        
        # Skip if JSON already exists - never overwrite existing files
        if os.path.exists(json_path):
            print(f"  [SKIP] JSON already exists, skipping...")
            continue
        
        # Transcribe the PDF
        if transcribe_pdf_to_json(pdf_path, json_path):
            successful += 1
        else:
            failed += 1
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Transcription completed!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Output directory: {transcribed_dir}")

if __name__ == "__main__":
    main()
