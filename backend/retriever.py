import json
import math
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import re


class TFIDFRetriever:
    """TF-IDF based document retriever for the docs.json corpus."""
    
    def __init__(self, docs_path: str = None):
        """Initialize the retriever with the document corpus."""
        if docs_path is None:
            # Try to find docs.json in current directory or backend directory
            import os
            if os.path.exists("docs.json"):
                docs_path = "docs.json"
            elif os.path.exists("backend/docs.json"):
                docs_path = "backend/docs.json"
            elif os.path.exists("../docs.json"):
                docs_path = "../docs.json"
            else:
                docs_path = "docs.json"  # fallback, will raise FileNotFoundError
        
        self.docs_path = docs_path
        self.documents = []
        self.doc_index = {}  # Maps (doc_id, page_no) to document index
        self.vocabulary = set()
        self.idf_scores = {}
        self.tf_idf_vectors = []
        
        self._load_documents()
        self._build_index()
    
    def _load_documents(self):
        """Load documents from the JSON file."""
        try:
            with open(self.docs_path, 'r', encoding='utf-8') as f:
                docs_data = json.load(f)
            
            # Flatten the documents by pages
            for doc in docs_data:
                doc_id = doc['id']
                title = doc['title']
                url = doc.get('url', '')
                doc_date = doc['doc_date']
                
                for page in doc['pages']:
                    page_no = page['pageno']
                    text = page['text']
                    
                    document = {
                        'doc_id': doc_id,
                        'title': title,
                        'url': url,
                        'doc_date': doc_date,
                        'pageno': page_no,
                        'text': text,
                        'tokens': self._tokenize(text)
                    }
                    
                    self.documents.append(document)
                    self.doc_index[(doc_id, page_no)] = len(self.documents) - 1
                    
        except FileNotFoundError:
            raise FileNotFoundError(f"Could not find documents file: {self.docs_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in documents file: {self.docs_path}")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization - convert to lowercase and split on non-alphanumeric."""
        # Remove special characters and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split on whitespace and filter out empty strings
        tokens = [token for token in text.split() if token and len(token) > 2]
        return tokens
    
    def _build_index(self):
        """Build the TF-IDF index."""
        if not self.documents:
            return
        
        # Build vocabulary
        for doc in self.documents:
            self.vocabulary.update(doc['tokens'])
        
        # Calculate document frequencies
        doc_frequencies = defaultdict(int)
        for doc in self.documents:
            unique_tokens = set(doc['tokens'])
            for token in unique_tokens:
                doc_frequencies[token] += 1
        
        # Calculate IDF scores
        total_docs = len(self.documents)
        for token in self.vocabulary:
            df = doc_frequencies[token]
            self.idf_scores[token] = math.log(total_docs / df) if df > 0 else 0
        
        # Calculate TF-IDF vectors for each document
        for doc in self.documents:
            tf_counts = Counter(doc['tokens'])
            total_tokens = len(doc['tokens'])
            
            tf_idf_vector = {}
            for token in self.vocabulary:
                tf = tf_counts[token] / total_tokens if total_tokens > 0 else 0
                idf = self.idf_scores[token]
                tf_idf_vector[token] = tf * idf
            
            self.tf_idf_vectors.append(tf_idf_vector)
    
    def _calculate_query_vector(self, query: str) -> Dict[str, float]:
        """Calculate TF-IDF vector for the query."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return {}
        
        tf_counts = Counter(query_tokens)
        total_tokens = len(query_tokens)
        
        query_vector = {}
        for token in self.vocabulary:
            tf = tf_counts[token] / total_tokens if total_tokens > 0 else 0
            idf = self.idf_scores.get(token, 0)
            query_vector[token] = tf * idf
        
        return query_vector
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two vectors."""
        # Calculate dot product
        dot_product = sum(vec1.get(token, 0) * vec2.get(token, 0) for token in self.vocabulary)
        
        # Calculate magnitudes
        mag1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
        mag2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def retrieve(self, query: str, top_k: int = 5, min_score: float = 0.01) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant documents for a query.
        
        Args:
            query: The search query
            top_k: Maximum number of results to return
            min_score: Minimum similarity score threshold
            
        Returns:
            List of relevant documents with similarity scores
        """
        if not query.strip():
            return []
        
        query_vector = self._calculate_query_vector(query)
        if not query_vector:
            return []
        
        # Calculate similarities
        similarities = []
        for i, doc_vector in enumerate(self.tf_idf_vectors):
            similarity = self._cosine_similarity(query_vector, doc_vector)
            if similarity >= min_score:
                similarities.append((i, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get top-k results
        results = []
        for i, (doc_idx, score) in enumerate(similarities[:top_k]):
            doc = self.documents[doc_idx]
            
            # Create snippet (first ~600-900 chars)
            text = doc['text']
            snippet_length = min(900, max(600, len(text) // 2))
            snippet = text[:snippet_length]
            if len(text) > snippet_length:
                snippet += "..."
            
            result = {
                'rank': i + 1,
                'doc_id': doc['doc_id'],
                'title': doc['title'],
                'url': doc['url'],
                'doc_date': doc['doc_date'],
                'pageno': doc['pageno'],
                'snippet': snippet,
                'similarity_score': score
            }
            results.append(result)
        
        return results


# Global retriever instance
_retriever_instance = None

def get_retriever() -> TFIDFRetriever:
    """Get the global retriever instance (singleton pattern)."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = TFIDFRetriever()
    return _retriever_instance
