# python/pivoterpy/__init__.py

# pivoterpy/__init__.py
from .graph import Graph
from .solver import pivoter

# Alias the graph constructors directly to the package level
from_edge_list = Graph.from_edge_list
from_adj_matrix = Graph.from_adj_matrix
from_networkx = Graph.from_networkx

__all__ = ["pivoter", "from_edge_list", "from_adj_matrix", "from_networkx"]