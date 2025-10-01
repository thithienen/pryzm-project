"""
Context Processing Module for Pryzm Project

Handles:
- Merging adjacent chunks from the same document
- Citation formatting
- Context packing for LLM consumption
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import tiktoken
from collections import defaultdict


@dataclass
class EvidenceBlock:
    """
    Formatted evidence block for LLM consumption.
    """
    doc_id: str
    doc_title: str
    doctype: Optional[str]
    date: Optional[str]  # Document date
    page_range: List[int]  # [start_page, end_page]
    section_path: List[str]
    text: str
    source_url: str  # URL with page anchor
    chunk_ids: List[str]  # Original chunk IDs for traceability
    citation: str  # Formatted citation like "[Title p.12-13]"
    token_count: int


class ContextProcessor:
    """
    Processes search results into formatted context for LLM.
    
    Responsibilities:
    - Merge adjacent chunks from same document
    - Deduplicate by text similarity
    - Format citations
    - Pack context within token budget
    """
    
    def __init__(
        self,
        max_context_tokens: int = 32000,
        context_fill_ratio: float = 0.70,
        max_blocks_per_doc: int = 4,
        max_evidence_blocks: int = 10,
        max_block_chars: int = None,
        text_similarity_threshold: float = 0.85,
        encoding_model: str = "cl100k_base"
    ):
        """
        Initialize context processor.
        
        Args:
            max_context_tokens: Maximum tokens available for context
            context_fill_ratio: Target % of tokens to fill (0.60-0.75 recommended)
            max_blocks_per_doc: Maximum merged blocks per document
            max_evidence_blocks: Maximum total evidence blocks to include
            max_block_chars: Maximum characters per evidence block (None = no limit)
            text_similarity_threshold: Threshold for text deduplication (0.0-1.0)
            encoding_model: Tiktoken encoding model (cl100k_base for GPT-3.5/4)
        """
        self.max_context_tokens = max_context_tokens
        self.context_fill_ratio = context_fill_ratio
        self.max_blocks_per_doc = max_blocks_per_doc
        self.max_evidence_blocks = max_evidence_blocks
        self.max_block_chars = max_block_chars
        self.text_similarity_threshold = text_similarity_threshold
        
        # Initialize token encoder
        self.encoder = tiktoken.get_encoding(encoding_model)
        
        # Calculate target token budget for evidence
        self.target_tokens = int(max_context_tokens * context_fill_ratio)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoder.encode(text))
    
    def deduplicate_by_text_similarity(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove chunks with very similar text content.
        
        Uses difflib's SequenceMatcher for fast text comparison.
        Only compares first 500 chars for efficiency.
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            
        Returns:
            Deduplicated list of chunks
        """
        from difflib import SequenceMatcher
        
        if not chunks:
            return []
        
        unique_chunks = []
        duplicates_removed = 0
        
        for chunk in chunks:
            is_duplicate = False
            # Only compare first 500 chars for efficiency
            chunk_text = chunk['text'][:500]
            
            for existing in unique_chunks:
                existing_text = existing['text'][:500]
                # Calculate similarity ratio
                ratio = SequenceMatcher(None, chunk_text, existing_text).ratio()
                
                if ratio > self.text_similarity_threshold:
                    is_duplicate = True
                    duplicates_removed += 1
                    break
            
            if not is_duplicate:
                unique_chunks.append(chunk)
        
        if duplicates_removed > 0:
            print(f"[ContextProcessor] Text deduplication: {len(chunks)} → {len(unique_chunks)} chunks ({duplicates_removed} similar chunks removed)")
        
        return unique_chunks
    
    def truncate_text(self, text: str, max_chars: int) -> str:
        """
        Truncate text to maximum characters with ellipsis.
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind('. ')
        last_newline = truncated.rfind('\n')
        
        # Use the latest sentence/paragraph boundary
        cut_point = max(last_period, last_newline)
        
        if cut_point > max_chars * 0.7:  # Only use boundary if it's not too far back
            return truncated[:cut_point + 1] + "..."
        else:
            return truncated + "..."
    
    def merge_adjacent_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge adjacent chunks from the same document and contiguous pages.
        
        Args:
            chunks: List of chunk results (already ranked)
            
        Returns:
            List of merged chunks with combined text and page ranges
        """
        if not chunks:
            return []
        
        # Group chunks by document ID
        doc_groups = defaultdict(list)
        for chunk in chunks:
            doc_groups[chunk['doc_id']].append(chunk)
        
        merged_results = []
        
        for doc_id, doc_chunks in doc_groups.items():
            # Sort chunks by page and chunk_id for proper ordering
            doc_chunks.sort(key=lambda x: (x['page'], x['chunk_id']))
            
            # Merge adjacent chunks
            merged_blocks = []
            current_block = None
            
            for chunk in doc_chunks:
                if current_block is None:
                    # Start new block
                    current_block = {
                        'chunk_ids': [chunk['chunk_id']],
                        'doc_id': chunk['doc_id'],
                        'doc_title': chunk['doc_title'],
                        'doctype': chunk.get('doctype'),
                        'source_url': chunk.get('source_url', ''),
                        'page_start': chunk['page'],
                        'page_end': chunk['page'],
                        'section_path': chunk.get('section_path', []),
                        'texts': [chunk['text']],
                        'is_table': chunk.get('is_table', False),
                        # Preserve scores for reference
                        'scores': {
                            'rerank': chunk.get('rerank_score'),
                            'rrf': chunk.get('rrf_score'),
                            'bm25': chunk.get('bm25_score'),
                            'faiss': chunk.get('faiss_score')
                        },
                        'final_rank': chunk.get('final_rank')
                    }
                else:
                    # Check if this chunk is adjacent (same or next page)
                    is_adjacent = (
                        chunk['page'] == current_block['page_end'] or
                        chunk['page'] == current_block['page_end'] + 1
                    )
                    
                    if is_adjacent and len(current_block['chunk_ids']) < 10:  # Max 10 chunks per block
                        # Merge into current block
                        current_block['chunk_ids'].append(chunk['chunk_id'])
                        current_block['page_end'] = chunk['page']
                        current_block['texts'].append(chunk['text'])
                        
                        # Update source_url to end page if different
                        if chunk['page'] != current_block['page_start']:
                            base_url = current_block['source_url'].split('#')[0]
                            current_block['source_url'] = f"{base_url}#page={chunk['page']}"
                    else:
                        # Save current block and start new one
                        merged_blocks.append(current_block)
                        current_block = {
                            'chunk_ids': [chunk['chunk_id']],
                            'doc_id': chunk['doc_id'],
                            'doc_title': chunk['doc_title'],
                            'doctype': chunk.get('doctype'),
                            'date': chunk.get('date'),
                            'source_url': chunk.get('source_url', ''),
                            'page_start': chunk['page'],
                            'page_end': chunk['page'],
                            'section_path': chunk.get('section_path', []),
                            'texts': [chunk['text']],
                            'is_table': chunk.get('is_table', False),
                            'scores': {
                                'rerank': chunk.get('rerank_score'),
                                'rrf': chunk.get('rrf_score'),
                                'bm25': chunk.get('bm25_score'),
                                'faiss': chunk.get('faiss_score')
                            },
                            'final_rank': chunk.get('final_rank')
                        }
            
            # Don't forget the last block
            if current_block:
                merged_blocks.append(current_block)
            
            # Cap blocks per document
            merged_blocks = merged_blocks[:self.max_blocks_per_doc]
            
            # Combine texts in each block
            for block in merged_blocks:
                block['text'] = ' '.join(block['texts'])
                del block['texts']  # Clean up temporary list
                merged_results.append(block)
        
        # Re-sort by original ranking
        merged_results.sort(key=lambda x: x.get('final_rank', 999))
        
        return merged_results
    
    def format_citation(
        self,
        doc_title: str,
        page_start: int,
        page_end: int
    ) -> str:
        """
        Format citation for a document and page range.
        
        Args:
            doc_title: Document title
            page_start: Starting page number
            page_end: Ending page number
            
        Returns:
            Formatted citation like "[Title p.12]" or "[Title p.12-14]"
        """
        # Shorten very long titles
        max_title_length = 60
        if len(doc_title) > max_title_length:
            title = doc_title[:max_title_length-3] + "..."
        else:
            title = doc_title
        
        # Format page range
        if page_start == page_end:
            page_str = f"p.{page_start}"
        else:
            page_str = f"p.{page_start}-{page_end}"
        
        return f"[{title} {page_str}]"
    
    def create_evidence_blocks(
        self,
        merged_chunks: List[Dict[str, Any]]
    ) -> List[EvidenceBlock]:
        """
        Create formatted evidence blocks from merged chunks.
        
        Args:
            merged_chunks: List of merged chunk dictionaries
            
        Returns:
            List of EvidenceBlock objects
        """
        evidence_blocks = []
        truncated_count = 0
        
        for chunk in merged_chunks:
            citation = self.format_citation(
                chunk['doc_title'],
                chunk['page_start'],
                chunk['page_end']
            )
            
            # Get base URL without page anchor
            source_url = chunk.get('source_url', '')
            if source_url:
                base_url = source_url.split('#')[0]
                # Use starting page for the link
                source_url = f"{base_url}#page={chunk['page_start']}"
            
            # Apply text truncation if max_block_chars is set
            text = chunk['text']
            if self.max_block_chars and len(text) > self.max_block_chars:
                text = self.truncate_text(text, self.max_block_chars)
                truncated_count += 1
            
            evidence = EvidenceBlock(
                doc_id=chunk['doc_id'],
                doc_title=chunk['doc_title'],
                doctype=chunk.get('doctype'),
                date=chunk.get('date'),
                page_range=[chunk['page_start'], chunk['page_end']],
                section_path=chunk.get('section_path', []),
                text=text,
                source_url=source_url,
                chunk_ids=chunk['chunk_ids'],
                citation=citation,
                token_count=self.count_tokens(text)
            )
            
            evidence_blocks.append(evidence)
        
        if truncated_count > 0:
            print(f"[ContextProcessor] Truncated {truncated_count} evidence blocks to {self.max_block_chars} chars")
        
        return evidence_blocks
    
    def pack_context(
        self,
        evidence_blocks: List[EvidenceBlock],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pack evidence blocks into context within token budget.
        
        Args:
            evidence_blocks: List of evidence blocks (already ranked)
            query: Optional query string for reference
            
        Returns:
            Dictionary with packed context and metadata
        """
        packed_blocks = []
        total_tokens = 0
        blocks_included = 0
        
        # Limit to max_evidence_blocks
        evidence_blocks = evidence_blocks[:self.max_evidence_blocks]
        
        for block in evidence_blocks:
            # Check if adding this block would exceed budget
            if total_tokens + block.token_count <= self.target_tokens:
                packed_blocks.append(block)
                total_tokens += block.token_count
                blocks_included += 1
            else:
                # Budget exhausted
                break
        
        # Format for LLM consumption
        formatted_evidence = []
        for i, block in enumerate(packed_blocks, 1):
            formatted_evidence.append({
                'evidence_id': i,
                'citation': block.citation,
                'doc_title': block.doc_title,
                'doc_id': block.doc_id,
                'doctype': block.doctype,
                'page_range': block.page_range,
                'section_path': block.section_path,
                'text': block.text,
                'source_url': block.source_url,
                'chunk_ids': block.chunk_ids,
                'token_count': block.token_count
            })
        
        return {
            'query': query,
            'evidence': formatted_evidence,
            'metadata': {
                'total_blocks': blocks_included,
                'total_tokens': total_tokens,
                'target_tokens': self.target_tokens,
                'max_tokens': self.max_context_tokens,
                'fill_ratio': total_tokens / self.target_tokens if self.target_tokens > 0 else 0,
                'blocks_truncated': len(evidence_blocks) - blocks_included
            }
        }
    
    def process(
        self,
        search_results: List[Dict[str, Any]],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete context processing pipeline.
        
        Pipeline:
        1. Deduplicate by text similarity
        2. Merge adjacent chunks
        3. Create evidence blocks with citations (includes truncation)
        4. Pack into token budget
        
        Args:
            search_results: Raw search results from retriever
            query: Original search query
            
        Returns:
            Packed context ready for LLM
        """
        # Step 1: Deduplicate by text similarity
        deduped = self.deduplicate_by_text_similarity(search_results)
        
        # Step 2: Merge adjacent chunks
        merged = self.merge_adjacent_chunks(deduped)
        
        # Step 3: Create evidence blocks (with truncation)
        evidence_blocks = self.create_evidence_blocks(merged)
        
        # Step 4: Pack within budget
        packed_context = self.pack_context(evidence_blocks, query)
        
        return packed_context


# Helper function for easy import
def process_context(
    search_results: List[Dict[str, Any]],
    query: Optional[str] = None,
    max_context_tokens: int = 32000,
    context_fill_ratio: float = 0.70,
    max_evidence_blocks: int = 10,
    max_block_chars: int = None,
    text_similarity_threshold: float = 0.85
) -> Dict[str, Any]:
    """
    Convenience function to process search results into packed context.
    
    Args:
        search_results: Search results from retriever
        query: Original query
        max_context_tokens: Maximum tokens for context
        context_fill_ratio: Target fill ratio (0.60-0.75)
        max_evidence_blocks: Maximum total evidence blocks
        max_block_chars: Maximum characters per block (None = no limit)
        text_similarity_threshold: Threshold for text deduplication
        
    Returns:
        Packed context dictionary
    """
    processor = ContextProcessor(
        max_context_tokens=max_context_tokens,
        context_fill_ratio=context_fill_ratio,
        max_evidence_blocks=max_evidence_blocks,
        max_block_chars=max_block_chars,
        text_similarity_threshold=text_similarity_threshold
    )
    return processor.process(search_results, query)

