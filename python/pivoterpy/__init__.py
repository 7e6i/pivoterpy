# python/pivoterpy/__init__.py

from .core import Pivoter


from_adj_matrix = Pivoter.from_adj_matrix
from_edge_list = Pivoter.from_edge_list

__all__ = ["Pivoter", "from_adj_matrix", "from_edge_list"]