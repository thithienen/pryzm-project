#!/usr/bin/env python3
"""
Document chunking script for Pryzm project.

Reads transcribed JSON files, chunks text into ~800 token pieces with overlap,
and outputs JSONL format ready for database ingestion.
"""

import json
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Iterator
from dataclasses import dataclass
import tiktoken


@dataclass
class DocumentMetadata:
    """Metadata for a document from raw_docs.json"""
    title: str
    url: str
    file_name: str
    
    @property
    def doc_id(self) -> str:
        """Generate doc_id from filename"""
        # Remove extension and clean up
        base = self.file_name.replace('.pdf', '').replace(' ', '_')
        return base
    
    @property 
    def doctype(self) -> str:
        """Infer document type from title/filename"""
        title_lower = self.title.lower()
        if 'org chart' in title_lower or 'org overview' in title_lower:
            return 'org_chart'
        elif 'budget' in title_lower:
            return 'budget'
        elif 'executive order' in title_lower:
            return 'executive_order'
        elif 'gao' in title_lower:
            return 'gao_report' 
        elif 'crs' in title_lower:
            return 'crs_report'
        else:
            return 'document'


class TextChunker:
    """Handles text chunking with token-based splitting"""
    
    def __init__(self, target_tokens: int = 800, overlap_tokens: int = 180):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        # Use tiktoken for accurate token counting (OpenAI compatible)
        self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-3.5/GPT-4 encoding
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def chunk_text(self, text: str, doc_id: str, page: int) -> Iterator[Dict[str, Any]]:
        """
        Chunk text into target_tokens sized pieces with overlap.
        
        Args:
            text: Text to chunk
            doc_id: Document identifier 
            page: Page number
            
        Yields:
            Chunk dictionaries with metadata
        """
        # Clean up text
        text = self._clean_text(text)
        
        if not text.strip():
            return
            
        # Split into sentences for better chunk boundaries
        sentences = self._split_sentences(text)
        
        chunk_num = 1
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If adding this sentence would exceed target, finalize current chunk
            if current_tokens + sentence_tokens > self.target_tokens and current_chunk:
                yield self._create_chunk(current_chunk, doc_id, page, chunk_num)
                chunk_num += 1
                
                # Start new chunk with overlap from previous chunk
                current_chunk, current_tokens = self._create_overlap_chunk(current_chunk)
            
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            yield self._create_chunk(current_chunk, doc_id, page, chunk_num)
    
    def _clean_text(self, text: str) -> str:
        """Clean up text formatting"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove page numbers at start of lines
        text = re.sub(r'^\d+\s*\n', '', text, flags=re.MULTILINE)
        return text.strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting - could be improved with proper NLP
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _create_chunk(self, sentences: List[str], doc_id: str, page: int, chunk_num: int) -> Dict[str, Any]:
        """Create chunk dictionary"""
        text = ' '.join(sentences)
        chunk_id = f"{doc_id}:p{page:03d}:c{chunk_num:03d}"
        
        return {
            'chunk_id': chunk_id,
            'text': text,
            'tokens': self.count_tokens(text),
            'page': page,
            'chunk_num': chunk_num
        }
    
    def _create_overlap_chunk(self, previous_chunk: List[str]) -> tuple[List[str], int]:
        """Create overlap for next chunk from previous chunk"""
        if not previous_chunk:
            return [], 0
            
        # Take sentences from end of previous chunk for overlap
        overlap_chunk = []
        overlap_tokens = 0
        
        for sentence in reversed(previous_chunk):
            sentence_tokens = self.count_tokens(sentence)
            if overlap_tokens + sentence_tokens <= self.overlap_tokens:
                overlap_chunk.insert(0, sentence)
                overlap_tokens += sentence_tokens
            else:
                break
                
        return overlap_chunk, overlap_tokens


def load_document_metadata(raw_docs_path: str) -> Dict[str, DocumentMetadata]:
    """Load document metadata from raw_docs.json"""
    metadata_map = {}
    
    with open(raw_docs_path, 'r', encoding='utf-8') as f:
        raw_docs = json.load(f)
    
    for doc in raw_docs:
        if 'file_name' in doc:  # Some entries might not have file_name
            metadata = DocumentMetadata(
                title=doc['title'],
                url=doc['url'], 
                file_name=doc['file_name']
            )
            metadata_map[doc['file_name']] = metadata
            
    return metadata_map


def process_transcribed_file(
    transcribed_path: str, 
    metadata: DocumentMetadata,
    chunker: TextChunker
) -> Iterator[Dict[str, Any]]:
    """Process a single transcribed JSON file into chunks"""
    
    with open(transcribed_path, 'r', encoding='utf-8') as f:
        transcribed = json.load(f)
    
    filename = transcribed['filename']
    total_pages = transcribed['total_pages']
    
    print(f"Processing {filename} ({total_pages} pages)...")
    
    for page_data in transcribed['pages']:
        page_num = page_data['page']
        page_text = page_data['text']
        
        # Generate chunks for this page
        for chunk_data in chunker.chunk_text(page_text, metadata.doc_id, page_num):
            # Create final chunk record matching the schema
            chunk_record = {
                'doc_id': metadata.doc_id,
                'doc_title': metadata.title,
                'source_url': f"{metadata.url}#page={page_num}",  # Add page anchor
                'date': None,  # Could extract from title/filename if needed
                'doctype': metadata.doctype,
                'page': page_num,
                'chunk_id': chunk_data['chunk_id'],
                'section_path': [],  # TODO: Could parse headings later
                'text': chunk_data['text'],
                'tokens': chunk_data['tokens'],
                'is_table': False,  # TODO: Could detect tables later
                'table_html': None
            }
            
            yield chunk_record


def main():
    """Main processing function"""
    # Paths
    project_root = Path(__file__).parent.parent
    raw_docs_path = project_root / "scripts" / "out" / "raw" / "raw_docs.json"
    transcribed_dir = project_root / "scripts" / "out" / "transcribed"
    output_path = project_root / "data" / "chunks.jsonl"
    
    print(f"Loading document metadata from {raw_docs_path}")
    metadata_map = load_document_metadata(str(raw_docs_path))
    print(f"Loaded metadata for {len(metadata_map)} documents")
    
    # Initialize chunker
    chunker = TextChunker(target_tokens=800, overlap_tokens=180)
    
    # Process all transcribed files
    total_chunks = 0
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for transcribed_file in transcribed_dir.glob("*.json"):
            # Match transcribed filename to raw document
            transcribed_filename = transcribed_file.name.replace('.json', '.pdf')
            
            if transcribed_filename in metadata_map:
                metadata = metadata_map[transcribed_filename] 
                
                # Process this file
                for chunk_record in process_transcribed_file(
                    str(transcribed_file), metadata, chunker
                ):
                    # Write JSONL
                    outfile.write(json.dumps(chunk_record, ensure_ascii=False) + '\n')
                    total_chunks += 1
                    
                    if total_chunks % 100 == 0:
                        print(f"  Processed {total_chunks} chunks...")
            else:
                print(f"Warning: No metadata found for {transcribed_filename}")
    
    print(f"\nCompleted! Generated {total_chunks} chunks in {output_path}")


if __name__ == "__main__":
    main()
