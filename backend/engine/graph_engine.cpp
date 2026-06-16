#include <vector>
#include <queue>
#include <unordered_set>

using namespace std;

// ---------------------------------------------------------
// MEMORY LAYOUT: 
// We use an Adjacency List representing the REVERSE graph.
// If Concept A -> Concept B, we store adj_rev[B] = {A}.
// This makes tracing dependencies (finding parents) O(1).
// ---------------------------------------------------------
vector<vector<int>> adj_rev;

// extern "C" prevents C++ Name Mangling so Python can find these exact function names
extern "C" {

    // 1. Initialize the contiguous array size
    void init_graph(int max_nodes) {
        adj_rev.clear();
        adj_rev.resize(max_nodes + 1);
    }

    // 2. Build the graph edges
    void add_edge(int prereq, int target) {
        if (target < adj_rev.size()) {
            adj_rev[target].push_back(prereq);
        }
    }

    // 3. The Core Algorithm: Frontier Reachability Search
    // Takes pure pointers arrays from Python to bypass serialization overhead
    int find_bottlenecks(int* solved_ids, int num_solved, int target_id, int* out_bottlenecks, int max_out) {
        
        unordered_set<int> mastered;
        queue<int> q;

        // --- PHASE 1: Forward Pass (Mastery Propagation) ---
        // Seed the queue with what the user already solved
        for (int i = 0; i < num_solved; i++) {
            q.push(solved_ids[i]);
            mastered.insert(solved_ids[i]);
        }

        // BFS up the dependency tree to find all implicitly mastered concepts
        while (!q.empty()) {
            int curr = q.front();
            q.pop();
            
            for (int parent : adj_rev[curr]) {
                if (mastered.find(parent) == mastered.end()) {
                    mastered.insert(parent);
                    q.push(parent);
                }
            }
        }

        // --- PHASE 2: Backward Pass (Requirement Trace) ---
        unordered_set<int> required;
        queue<int> req_q;
        req_q.push(target_id);

        // BFS up from the target problem to find ALL required concepts
        while (!req_q.empty()) {
            int curr = req_q.front();
            req_q.pop();
            
            for (int parent : adj_rev[curr]) {
                if (required.find(parent) == required.end()) {
                    required.insert(parent);
                    req_q.push(parent);
                }
            }
        }

        // --- PHASE 3: Set Difference & Frontier Intersection ---
        int bottleneck_count = 0;
        
        for (int req_concept : required) {
            // Is it required but NOT mastered? (The Set Difference: Required \ Mastered)
            if (mastered.find(req_concept) == mastered.end()) {
                
                // FRONTIER CHECK: Are all of its prerequisites mastered?
                // We only want the *immediate* next step, not a concept 5 steps ahead.
                bool all_prereqs_mastered = true;
                for (int p : adj_rev[req_concept]) {
                    if (mastered.find(p) == mastered.end()) {
                        all_prereqs_mastered = false;
                        break;
                    }
                }

                // If it is right on the learning edge, add it to the output buffer
                if (all_prereqs_mastered) {
                    if (bottleneck_count < max_out) {
                        out_bottlenecks[bottleneck_count] = req_concept;
                    }
                    bottleneck_count++;
                }
            }
        }

        // Return the number of bottleneck concepts successfully loaded into the C-Array
        return bottleneck_count;
    }
}