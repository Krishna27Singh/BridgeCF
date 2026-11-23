.PHONY: all clean

CXX ?= g++
CXXFLAGS := -O3 -std=c++17 -fPIC -shared -Wall -Wextra -Wpedantic

all: engine.so

engine.so: engine/graph_engine.cpp
	$(CXX) $(CXXFLAGS) engine/graph_engine.cpp -o engine.so

clean:
	rm -f engine.so
