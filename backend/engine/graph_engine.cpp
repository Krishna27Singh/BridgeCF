#include <vector>
#include <thread>
#include <shared_mutex>
#include <mutex>
#include <atomic>
#include <algorithm>
#include <memory>

using namespace std;

// ---------------------------------------------------------
// MEMORY LAYOUT: 
// Adjacency List representing the REVERSE graph.
// ---------------------------------------------------------
vector<vector<int>> adj_rev;
shared_mutex graph_mutex; // Readers-Writer lock for thread-safe concurrent FFI calls

extern "C" {

    // 1. Initialize the contiguous array size (Exclusive Write Lock)
    int init_graph(int max_nodes) {
        if (max_nodes <= 0) {
            unique_lock<shared_mutex> lock(graph_mutex);
            adj_rev.clear();
            return -1;
        }
        unique_lock<shared_mutex> lock(graph_mutex);
        adj_rev.clear();
        adj_rev.resize(max_nodes + 1);
        return 0;
    }

    // 2. Build the graph edges (Exclusive Write Lock)
    int add_edge(int prereq, int target) {
        unique_lock<shared_mutex> lock(graph_mutex);
        if (prereq < 0 || target < 0 ||
            static_cast<size_t>(prereq) >= adj_rev.size() ||
            static_cast<size_t>(target) >= adj_rev.size()) {
            return -1;
        }
        adj_rev[target].push_back(prereq);
        return 0;
    }

    // 3. The Core Algorithm: Parallel Frontier Reachability Search (Shared Read Lock)
    int find_bottlenecks(int* solved_ids, int num_solved, int target_id, int* out_bottlenecks, int max_out) {
        if (adj_rev.empty() || target_id < 0 ||
            static_cast<size_t>(target_id) >= adj_rev.size() ||
            num_solved < 0 || max_out <= 0 || out_bottlenecks == nullptr ||
            (num_solved > 0 && solved_ids == nullptr)) {
            return -1;
        }
        // Allow multiple concurrent Python threads to read the graph simultaneously
        shared_lock<shared_mutex> lock(graph_mutex);
        int n = adj_rev.size();

        // Lock-free atomic arrays to track state across thread pools (faster than unordered_set)
        auto mastered = make_unique<atomic<bool>[]>(n);
        auto required = make_unique<atomic<bool>[]>(n);
        for(int i = 0; i < n; ++i) {
            mastered[i] = false;
            required[i] = false;
        }

        // --- PHASE 1: Forward Pass (Parallel Mastery Propagation) ---
        vector<int> current_level;
        for (int i = 0; i < num_solved; i++) {
            if (solved_ids[i] >= 0 && solved_ids[i] < n) {
                current_level.push_back(solved_ids[i]);
                mastered[solved_ids[i]] = true;
            }
        }

        while (!current_level.empty()) {
            vector<int> next_level;
            mutex next_level_mutex;
            
            // Determine thread count based on hardware and current frontier size
            unsigned int num_threads = min((unsigned int)current_level.size(), thread::hardware_concurrency());
            
            if (num_threads <= 1) {
                // Sequential fallback for small frontiers (avoids thread creation overhead)
                for (int curr : current_level) {
                    for (int parent : adj_rev[curr]) {
                        bool expected = false;
                        if (mastered[parent].compare_exchange_strong(expected, true)) {
                            next_level.push_back(parent);
                        }
                    }
                }
            } else {
                // Thread pool execution for wide frontiers
                vector<thread> workers;
                size_t chunk_size = (current_level.size() + num_threads - 1) / num_threads;
                
                for (unsigned int t = 0; t < num_threads; ++t) {
                    size_t start = t * chunk_size;
                    size_t end = min(start + chunk_size, current_level.size());
                    if (start >= end) break;
                    
                    workers.emplace_back([&, start, end]() {
                        vector<int> local_next;
                        for (size_t i = start; i < end; ++i) {
                            int curr = current_level[i];
                            for (int parent : adj_rev[curr]) {
                                // Atomic test-and-set: Prevents race conditions without heavy mutexes
                                bool expected = false; 
                                if (mastered[parent].compare_exchange_strong(expected, true)) {
                                    local_next.push_back(parent);
                                }
                            }
                        }
                        // Merge local frontier into global next level
                        if (!local_next.empty()) {
                            lock_guard<mutex> nl_lock(next_level_mutex);
                            next_level.insert(next_level.end(), local_next.begin(), local_next.end());
                        }
                    });
                }
                for (auto& w : workers) w.join();
            }
            current_level = move(next_level);
        }

        // --- PHASE 2: Backward Pass (Parallel Requirement Trace) ---
        vector<int> req_level;
        if (target_id < n) {
            req_level.push_back(target_id);
            required[target_id] = true;
        }

        while (!req_level.empty()) {
            vector<int> next_level;
            mutex next_level_mutex;
            unsigned int num_threads = min((unsigned int)req_level.size(), thread::hardware_concurrency());
            
            if (num_threads <= 1) {
                for (int curr : req_level) {
                    for (int parent : adj_rev[curr]) {
                        bool expected = false;
                        if (required[parent].compare_exchange_strong(expected, true)) {
                            next_level.push_back(parent);
                        }
                    }
                }
            } else {
                vector<thread> workers;
                size_t chunk_size = (req_level.size() + num_threads - 1) / num_threads;
                
                for (unsigned int t = 0; t < num_threads; ++t) {
                    size_t start = t * chunk_size;
                    size_t end = min(start + chunk_size, req_level.size());
                    if (start >= end) break;
                    
                    workers.emplace_back([&, start, end]() {
                        vector<int> local_next;
                        for (size_t i = start; i < end; ++i) {
                            int curr = req_level[i];
                            for (int parent : adj_rev[curr]) {
                                bool expected = false;
                                if (required[parent].compare_exchange_strong(expected, true)) {
                                    local_next.push_back(parent);
                                }
                            }
                        }
                        if (!local_next.empty()) {
                            lock_guard<mutex> nl_lock(next_level_mutex);
                            next_level.insert(next_level.end(), local_next.begin(), local_next.end());
                        }
                    });
                }
                for (auto& w : workers) w.join();
            }
            req_level = move(next_level);
        }

        // --- PHASE 3: Set Difference & Frontier Intersection ---
        // (This phase is extremely fast O(V+E) and runs sequentially)
        int bottleneck_count = 0;
        
        for (int i = 0; i < n; i++) {
            if (required[i] && !mastered[i]) {
                bool all_prereqs_mastered = true;
                for (int p : adj_rev[i]) {
                    if (!mastered[p]) {
                        all_prereqs_mastered = false;
                        break;
                    }
                }

                if (all_prereqs_mastered) {
                    if (bottleneck_count < max_out) {
                        out_bottlenecks[bottleneck_count] = i;
                    }
                    bottleneck_count++;
                }
            }
        }

        return min(bottleneck_count, max_out);
    }
}
