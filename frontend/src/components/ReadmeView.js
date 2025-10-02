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
            <div className="readme-section">
              <h3>What is it?</h3>
              <p>
                Chatbot to answer defense-related questions.    
            </p>
            </div>
            
            <div className="readme-section">
              <h3>What does it do?</h3>
              <ul>
                <li>Gives you responses based on its knowledge base (30 PDFs)</li>
                <li>Shows the PDFs it's citing in the right panel</li>
                <li>Allows you to expand to read small relevant snippets</li>
                <li>Has a button to direct you to the original source (page aware)</li>
                <li>Has a button to make it search the web for answers</li>
              </ul>
            </div>
            
            <div className="readme-section">
              <h3>What is done?</h3>
              <ul>
                <li><strong>Standard RAG system:</strong> chunking, embedding, retrieval, and generation</li>
                <li><strong>Preprocessing / chunking / embedding:</strong>
                  <ul>
                    <li>Download 30 cores PDFs (suggested by chatGPT) mostly from Comptroller and other sources</li>
                    <li>Transcribe PDFs to text, for image-heavy pages, use OCR and pass text along with the image to LLM for detail description</li>
                    <li>Chunk and use OpenAI to embed and store in SQLite database</li>
                  </ul>
                </li>
                <li><strong>Retrieval:</strong>
                  <ul>
                    <li>Hybrid search: BM25 + vector</li>
                    <li>I put in a reranker but it's cpu intensive so I threw it out the window</li>
                    <li>Implement simple deduplication and limit the context for faster response</li>
                  </ul>
                </li>
                <li><strong>Generation:</strong>
                  <ul>
                    <li>Settle with claude-3.5-sonnet because it's cheap and fast. Plus using a highly intelligent model feels kinda like cheating 😅</li>
                    <li>Retrieve, append some additional instructions, and call OpenRouter</li>
                    <li>Stream the response for better user experience</li>
                    <li>If user select to search the web, OpenRouter handles that, I take no credit</li>
                  </ul>
                </li>
              </ul>
            </div>
            
            <div className="readme-section">
              <h3>What is wrong?</h3>
              <ul>
                <li>In short, a lot 🥲</li>
                <li>I asked chatGPT for a list of questions to evaluate. The results are pretty bad, it hallucinates, especially bad with numbers and dates.</li>
                <li>Even for questions that's straight in the PDF knowledge base, it's not good.
                  <ul>
                    <li>For example, "tell me about Col Michelle Idle" it knows she's the Deputy Commander.</li>
                    <li>But, "tell me about Mr. Noble Smith" it says no information, and they appear on the same org chart.</li>
                    <li>I suspect OCR got the names wrong, but I checked and the names are correctly transcribed, so the hybrid search is probably bugged.</li>
                  </ul>
                </li>
                <li>For web search, I rely entirely on OpenRouter, so not much control over the results.
                  <ul>
                    <li>The only touch I put in is a small instruction to tell it to prioritize reliable sources. like .org and .gov.</li>
                    <li>It finds most of the info on wikipedia.org, which is extremely unreliable 🥲</li>
                    <li>A web search API is definitely needed for fine-grained control</li>
                  </ul>
                </li>
                <li>Didn't have a lot of time to worry about design and responsiveness, might look like a total mess on mobile, idk.</li>
                <li>No security, no password, no rate throttling, nothing, but technically nothing is at risk though, there's $3 in my OpenRouter account, worst case is someone spamming 13,000 questions and deplete my account 🤣</li>
                <li>And debug messages everywhere, haven't cleaned them up yet...</li>
              </ul>
            </div>
            
            <div className="readme-section">
              <h3>Note</h3>
              <p>I push the db to git as well as it's relatively small, if you pull no need to do ingestion again</p>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReadmeView;
