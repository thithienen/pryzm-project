import json
import os
from typing import Dict, List, Optional, Iterator, Tuple
from settings import DATA_PATH


class DocumentRepository:
    """Centralized document repository for consistent data access."""
    
    def __init__(self, data_path: str = None):
        """Initialize the document repository."""
        self.data_path = data_path or DATA_PATH
        self.documents = []
        self.doc_index = {}  # Maps doc_id to document
        self.page_index = {}  # Maps (doc_id, pageno) to page data
        
        self._load_documents()
    
    def _load_documents(self):
        """Load documents from the JSON file."""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.documents = json.load(f)
            
            # Build indexes for fast lookups
            for doc in self.documents:
                doc_id = doc['id']
                self.doc_index[doc_id] = doc
                
                for page in doc['pages']:
                    pageno = page['pageno']
                    self.page_index[(doc_id, pageno)] = {
                        'doc_id': doc_id,
                        'title': doc['title'],
                        'url': doc.get('url', ''),
                        'doc_date': doc['doc_date'],
                        'pageno': pageno,
                        'text': page['text']
                    }
                    
        except FileNotFoundError:
            raise FileNotFoundError(f"Document file not found: {self.data_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in document file: {e}")
    
    def get_page(self, doc_id: str, pageno: int) -> Optional[Dict]:
        """
        Get a specific page by document ID and page number.
        
        Args:
            doc_id: The document ID
            pageno: The 1-indexed page number (must be >= 1)
            
        Returns:
            Dictionary with page data or None if not found
        """
        if pageno < 1:
            return None
            
        return self.page_index.get((doc_id, pageno))
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get a document by ID."""
        return self.doc_index.get(doc_id)
    
    def iter_pages(self) -> Iterator[Dict]:
        """
        Iterate over all pages in all documents.
        Yields dictionaries with doc_id, title, url, doc_date, pageno, text.
        """
        for doc in self.documents:
            doc_id = doc['id']
            title = doc['title']
            url = doc.get('url', '')
            doc_date = doc['doc_date']
            
            for page in doc['pages']:
                yield {
                    'doc_id': doc_id,
                    'title': title,
                    'url': url,
                    'doc_date': doc_date,
                    'pageno': page['pageno'],
                    'text': page['text']
                }
    
    def get_all_documents(self) -> List[Dict]:
        """Get all documents."""
        return self.documents.copy()


# Global instance
_doc_repo = None

def get_doc_repo() -> DocumentRepository:
    """Get the global document repository instance."""
    global _doc_repo
    if _doc_repo is None:
        _doc_repo = DocumentRepository()
    return _doc_repo
