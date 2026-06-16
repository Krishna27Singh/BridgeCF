import requests
import ctypes
import os

# --- GRAPH MAPPINGS ---
CONCEPT_MAP = {
    0: "Arrays", 1: "Math", 2: "Prefix Sums", 
    3: "Two Pointers", 4: "Greedy", 5: "Sorting"
}

PROBLEM_TO_INT = {
    "1903_A": 1000, "1899_A": 1001, "1890_A": 1002, "1985_A": 1003
}

print("Loading C++ Graph Engine...")
# Look for engine.so in the exact same folder as this script
engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'engine.so'))
try:
    engine = ctypes.CDLL(engine_path)
    
    engine.init_graph.argtypes = [ctypes.c_int]
    engine.add_edge.argtypes = [ctypes.c_int, ctypes.c_int]
    engine.find_bottlenecks.argtypes = [
        ctypes.POINTER(ctypes.c_int), ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.c_int
    ]

    engine.init_graph(5000)
    engine.add_edge(0, 3) # Arrays -> Two Pointers
    engine.add_edge(1, 4) # Math -> Greedy
    engine.add_edge(4, 1000) # Greedy -> 1903_A
    engine.add_edge(5, 1000) # Sorting -> 1903_A
    engine.add_edge(1, 1001) # Math -> 1899_A
    engine.add_edge(3, 1003) # Two Pointers -> 1985_A
    engine.add_edge(4, 1003) # Greedy -> 1985_A
except Exception as e:
    print(f"Warning: Could not load C++ engine. Error: {e}")
    engine = None

def get_user_solved_problems(handle: str):
    """Fetches user's successfully solved problems from Codeforces API."""
    url = f"https://codeforces.com/api/user.status?handle={handle}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return []
        data = response.json()
        if data["status"] != "OK": return []
        
        solved_ids = set()
        for sub in data["result"]:
            if sub.get("verdict") == "OK":
                cid = sub["problem"].get("contestId")
                idx = sub["problem"].get("index")
                if cid and idx:
                    solved_ids.add(f"{cid}_{idx}")
        return list(solved_ids)
    except Exception as e:
        print(f"API Error: {e}")
        return []

def find_missing_concepts(handle: str, target_str: str):
    if not engine: return ["C++ Engine Offline"]
    if target_str not in PROBLEM_TO_INT:
        return ["Graph Not Mapped For This Problem Yet"]
        
    target_int = PROBLEM_TO_INT[target_str]
    solved_strings = get_user_solved_problems(handle)
    solved_ints = [PROBLEM_TO_INT[s] for s in solved_strings if s in PROBLEM_TO_INT]
    
    if not solved_ints:
        solved_ints = [9999] # Dummy data so C++ doesn't crash on empty array
        
    IntArrayType = ctypes.c_int * len(solved_ints)
    c_solved_array = IntArrayType(*solved_ints)
    
    max_bottlenecks = 5
    OutArrayType = ctypes.c_int * max_bottlenecks
    c_out_array = OutArrayType()
    
    bottleneck_count = engine.find_bottlenecks(
        c_solved_array, len(solved_ints),
        target_int,
        c_out_array, max_bottlenecks
    )
    
    missing_concepts = []
    for i in range(bottleneck_count):
        missing_concepts.append(CONCEPT_MAP.get(c_out_array[i], "Unknown"))
    return missing_concepts