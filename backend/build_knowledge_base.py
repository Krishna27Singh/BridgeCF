import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import time
import cloudscraper

# Initialize the embedding model (downloads a lightweight, highly effective model locally)
print("Loading Transformer Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# FAISS Vector Database Initialization
# The model outputs vectors of size 384
dimension = 384 
index = faiss.IndexFlatL2(dimension)
problem_metadata = {}

def scrape_codeforces_problem(contest_id, index_letter):
    """Scrapes the problem statement text from Codeforces."""
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index_letter}"
    
    # Create a scraper instance that bypasses Cloudflare
    scraper = cloudscraper.create_scraper(browser={
        'browser': 'chrome',
        'platform': 'darwin', # Since you are on a Mac
        'desktop': True
    })
    
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch {url} - Status Code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the main problem statement div
        statement_div = soup.find('div', class_='problem-statement')
        if not statement_div:
            print(f"Could not find problem-statement div for {url}")
            return None
            
        # Extracting the pure text
        header = statement_div.find('div', class_='header')
        if header: header.decompose()
        
        sample_tests = statement_div.find('div', class_='sample-tests')
        if sample_tests: sample_tests.decompose()
            
        pure_text = statement_div.get_text(separator=' ', strip=True)
        return pure_text
        
    except Exception as e:
        print(f"An error occurred while scraping {url}: {e}")
        return None

def process_and_store_problem(problem_id, contest_id, index_letter, tags):
    """Generates embedding and stores it in FAISS."""
    print(f"Processing {problem_id}...")
    
    text = scrape_codeforces_problem(contest_id, index_letter)
    if not text:
        return False
        
    # Combine tags and text to enrich the semantic meaning
    enriched_text = f"Tags: {', '.join(tags)}. Problem: {text}"
    
    # Generate Vector Embedding
    vector = model.encode([enriched_text])[0]
    
    # Store in FAISS
    vector_np = np.array([vector]).astype('float32')
    faiss_id = index.ntotal
    index.add(vector_np)
    
    # Save metadata mapping
    problem_metadata[faiss_id] = {
        "problem_id": problem_id,
        "url": f"https://codeforces.com/problemset/problem/{contest_id}/{index_letter}",
        "tags": tags
    }
    
    # Sleep to respect rate limits
    time.sleep(1)
    return True

if __name__ == "__main__":
    # Seed data: A small subset from the CP-31 sheet to bootstrap the engine
    seed_problems = [
        {"id": "1903_A", "contest": "1903", "index": "A", "tags": ["greedy", "math", "sorting"]},
        {"id": "1899_A", "contest": "1899", "index": "A", "tags": ["math", "game trees"]},
        {"id": "1890_A", "contest": "1890", "index": "A", "tags": ["arrays", "hash_map"]}
    ]
    
    for prob in seed_problems:
        process_and_store_problem(prob["id"], prob["contest"], prob["index"], prob["tags"])
        
    # Persist the Vector Index and Metadata to disk
    faiss.write_index(index, "vector_database.index")
    with open("metadata.json", "w") as f:
        json.dump(problem_metadata, f)
        
    print(f"Successfully indexed {index.ntotal} problems.")