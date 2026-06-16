import cloudscraper
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "vector_database.index")
METADATA_FILE = os.path.join(BASE_DIR, "metadata.json")

MODEL_NAME = 'all-MiniLM-L6-v2'
INDEX_FILE = "vector_database.index"
METADATA_FILE = "metadata.json"

print("Loading Semantic Engine (Vector DB & Transformer)...")
model = SentenceTransformer(MODEL_NAME)
index = None
problem_metadata = {}

def load_database():
    global index, problem_metadata
    if os.path.exists(INDEX_FILE) and os.path.exists(METADATA_FILE):
        index = faiss.read_index(INDEX_FILE)
        with open(METADATA_FILE, "r") as f:
            problem_metadata = json.load(f)
        print(f"Vector DB loaded with {index.ntotal} problems.")
    else:
        print("Vector DB missing. Run build_knowledge_base.py first.")
        index = faiss.IndexFlatL2(384)
        problem_metadata = {}

load_database()

def scrape_codeforces_problem(contest_id: str, index_letter: str):
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index_letter}"
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        statement_div = soup.find('div', class_='problem-statement')
        if not statement_div: return None
        header = statement_div.find('div', class_='header')
        if header: header.decompose()
        sample_tests = statement_div.find('div', class_='sample-tests')
        if sample_tests: sample_tests.decompose()
        return statement_div.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"JIT Scraping error: {e}")
        return None

def jit_ingest_problem(problem_id: str):
    global index, problem_metadata
    parts = problem_id.split('_')
    if len(parts) != 2: return None
    
    print(f"[JIT Pipeline] Fetching {problem_id} dynamically...")
    text = scrape_codeforces_problem(parts[0], parts[1])
    if not text: return None
        
    vector = model.encode([text])[0]
    vector_np = np.array([vector]).astype('float32')
    
    faiss_id = str(index.ntotal)
    index.add(vector_np)
    
    problem_metadata[faiss_id] = {
        "problem_id": problem_id,
        "url": f"https://codeforces.com/problemset/problem/{parts[0]}/{parts[1]}",
        "tags": ["dynamically_ingested"]
    }
    
    # Persist to disk
    faiss.write_index(index, INDEX_FILE)
    with open(METADATA_FILE, "w") as f:
        json.dump(problem_metadata, f)
        
    print(f"[JIT Pipeline] Successfully saved {problem_id} to disk at {METADATA_FILE}")
    return faiss_id

def get_bridge_problem(target_id: str):
    """Returns the URL and ID of the closest semantic bridge problem."""
    global index, problem_metadata
    
    target_faiss_id = None
    for fid, meta in problem_metadata.items():
        if meta["problem_id"] == target_id:
            target_faiss_id = fid
            break
            
    if target_faiss_id is None:
        target_faiss_id = jit_ingest_problem(target_id)
        if target_faiss_id is None:
            return None, None

    target_vector = index.reconstruct(int(target_faiss_id))
    target_vector_np = np.array([target_vector]).astype('float32')
    
    k = min(2, index.ntotal)
    distances, indices = index.search(target_vector_np, k)
    
    for matched_idx in indices[0]:
        matched_fid = str(matched_idx)
        # Skip returning itself as a bridge problem
        if matched_fid in problem_metadata and problem_metadata[matched_fid]["problem_id"] != target_id:
            return problem_metadata[matched_fid]["url"], problem_metadata[matched_fid]["problem_id"]
            
    return None, None