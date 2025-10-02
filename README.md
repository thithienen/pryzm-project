# README

Most of this project is written by AI, but this page is **NOT**. No word fill or lengthy description, don't worry!

## What is it?

Chatbot to answer defense-related questions.

## What does it do?

- Gives you responses based on its knowledge base (30 PDFs)
- Shows the PDFs it's citing in the right panel
- Allows you to expand to read small relevant snippets
- Has a button to direct you to the original source (page aware)
- Has a button to make it search the web for answers

## What is done?

- **Standard RAG system:** chunking, embedding, retrieval, and generation
- **Preprocessing / chunking / embedding:**
  - Download 30 cores PDFs (suggested by chatGPT) mostly from Comptroller and other sources
  - Transcribe PDFs to text, for image-heavy pages, use OCR and pass text along with the image to LLM for detail description
  - Chunk and use OpenAI to embed and store in SQLite database
- **Retrieval:**
  - Hybrid search: BM25 + vector
  - I put in a reranker but it's cpu intensive so I threw it out the window
  - Implement simple deduplication and limit the context for faster response
- **Generation:**
  - Settle with claude-3.5-sonnet because it's cheap and fast. Plus using a highly intelligent model feels kinda like cheating 😅
  - Retrieve, append some additional instructions, and call OpenRouter
  - Stream the response for better user experience
  - If user select to search the web, OpenRouter handles that, I take no credit

## What is wrong?

- In short, a lot 🥲
- I asked chatGPT for a list of questions to evaluate. The results are pretty bad, it hallucinates, especially bad with numbers and dates.
- Even for questions that's straight in the PDF knowledge base, it's not good.
  - For example, "tell me about Col Michelle Idle" it knows she's the Deputy Commander.
  - But, "tell me about Mr. Noble Smith" it says no information, and they appear on the same org chart.
  - I suspect OCR got the names wrong, but I checked and the names are correctly transcribed, so the hybrid search is probably bugged.
- For web search, I rely entirely on OpenRouter, so not much control over the results.
  - The only touch I put in is a small instruction to tell it to prioritize reliable sources. like .org and .gov.
  - It finds most of the info on wikipedia.org, which is extremely unreliable 🥲
  - A web search API is definitely needed for fine-grained control
- Didn't have a lot of time to worry about design and responsiveness, might look like a total mess on mobile, idk.
- No security, no password, no rate throttling, nothing, but technically nothing is at risk though, there's $3 in my OpenRouter account, worst case is someone spamming 13,000 questions and deplete my account 🤣

## Note

I push the db to git as well as it's relatively small, if you pull no need to do ingestion again