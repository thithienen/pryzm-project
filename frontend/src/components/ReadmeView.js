import React from 'react';
import './ReadmeView.css';

function ReadmeView() {
  return (
    <div className="readme-view">
      <div className="readme-container">
        <div className="readme-content">
          <div className="readme-header">
            <div className="readme-icon">📖</div>
            <h1 className="readme-title">README</h1>
            <p className="readme-subtitle">Most of this project is written by AI, but this page is <u><b>NOT</b></u>. No word fill or lengthy description, don't worry!</p>
          </div>
          <div className="readme-divider"></div>
          <div className="readme-body">
            <p className="readme-summary">
              <strong>High level:</strong> RAG system for defense-related content. Web search disabled by default to reduce hallucination, unless user insists.
            </p>
            
            <div className="readme-section">
              <h3>What's Done:</h3>
              <ul>
                <li><strong>Standard RAG flow:</strong> Chunking, embedding, retrieval, generation</li>
                <li><strong>Data scope:</strong> 30 core PDFs from Comptroller and other government/military websites</li>
                <li><strong>PDF processing:</strong> Transcribe PDFs to text; for image-heavy pages (org charts, diagrams), pass to LLM for description</li>
                <li><strong>Storage:</strong> Chunked and embedded in SQLite database with FAISS vector index</li>
              </ul>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReadmeView;
