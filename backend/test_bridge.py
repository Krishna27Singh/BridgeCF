import graph_engine
import vector_engine

print("\n--- Running Local Integration Test ---")
target = "1985_A"
handle = "tourist" # Uses an active handle to fetch real CF history

print(f"Testing target problem {target} for handle '{handle}'...")
missing = graph_engine.find_missing_concepts(handle, target)
print(f"Calculated Missing Concepts: {missing}")

url, b_id = vector_engine.get_bridge_problem(target)
print(f"Calculated Bridge Problem: ID={b_id}, URL={url}")