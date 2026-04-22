# import pytest
# import networkx as nx
# import pivoterpy as pvt
# from math import comb

# BACKENDS = ["python", "rust"]


# @pytest.fixture
# def complete_graph():
#     n = 7
#     edges = [(i,j) for i in range(n) for j in range(i+1, n)]
#     g_counts = [comb(n, i) for i in range(n+1)]
#     v_counts = [[1]+[comb(n-1, i) for i in range(n)] for _ in range(n)]
#     return n, edges, g_counts, v_counts


# @pytest.fixture
# def karate_graph():
#     edges = nx.karate_club_graph().edges()
#     g_counts = [1, 34, 78, 45, 11, 2]
#     v_counts = [[1, 1, 16, 18, 7, 2], [1, 1, 9, 12, 7, 2], [1, 1, 10, 11, 7, 2], [1, 1, 6, 10, 7, 2], [1, 1, 3, 2], [1, 1, 4, 3], [1, 1, 4, 3], [1, 1, 4, 6, 4, 1], [1, 1, 5, 5, 1], [1, 1, 2], [1, 1, 3, 2], [1, 1, 1], [1, 1, 2, 1], [1, 1, 5, 6, 4, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 3, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 2, 1], [1, 1, 5, 4, 1], [1, 1, 3, 1], [1, 1, 3, 1], [1, 1, 2, 1], [1, 1, 4, 1], [1, 1, 3, 1], [1, 1, 4, 4, 1], [1, 1, 4, 3, 1], [1, 1, 6, 3], [1, 1, 12, 13, 2], [1, 1, 17, 15, 2]]
#     return 34, edges, g_counts, v_counts



# def test_python_singleton():
#     n, edges = 2, [(0,1)]
#     g_counts, v_counts = [1,2,1], [[1,1,1], [1,1,1]]
#     G = pvt.from_edge_list(edges, n=n)

#     for backend in BACKENDS:

#         P = pvt.pivoter(G, resolution="v")
#         assert P.vertex_counts == v_counts
#         assert P.global_counts == g_counts

#         for i in range(n+1):
#             P = pvt.pivoter(G, min_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == [0]*i + c2[i:]
#             assert P.global_counts == [0]*i + g_counts[i:]

#         for i in range(n+1):
#             P = pvt.pivoter(G, max_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == c2[:i+1]
#             assert P.global_counts == g_counts[:i+1]

#         for i in range(n+1):
#             for j in range(i, n+1):
#                 P = pvt.pivoter(G, min_k=i, max_k=j, resolution="v", backend=backend)
#                 for c1, c2 in zip(P.vertex_counts, v_counts):
#                     assert c1 == [0]*i + c2[i:j+1]
#                 assert P.global_counts == [0]*i + g_counts[i:j+1]


# # duplicate code? yes. do i care? no.
# def test_python_complete(complete_graph):
#     n, edges, g_counts, v_counts = complete_graph
#     G = pvt.from_edge_list(edges)

#     for backend in BACKENDS:

#         P = pvt.pivoter(G, resolution="v")
#         assert P.vertex_counts == v_counts
#         assert P.global_counts == g_counts

#         for i in range(n+1):
#             P = pvt.pivoter(G, min_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == [0]*i + c2[i:]
#             assert P.global_counts == [0]*i + g_counts[i:]

#         for i in range(n+1):
#             P = pvt.pivoter(G, max_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == c2[:i+1]
#             assert P.global_counts == g_counts[:i+1]

#         for i in range(n+1):
#             for j in range(i, n+1):
#                 P = pvt.pivoter(G, min_k=i, max_k=j, resolution="v", backend=backend)
#                 for c1, c2 in zip(P.vertex_counts, v_counts):
#                     assert c1 == [0]*i + c2[i:j+1]
#                 assert P.global_counts == [0]*i + g_counts[i:j+1]


# def test_python_karate(karate_graph):
#     n, edges, g_counts, v_counts = karate_graph
#     G = pvt.from_edge_list(edges)

#     for backend in BACKENDS:

#         P = pvt.pivoter(G, resolution="v")
#         assert P.vertex_counts == v_counts
#         assert P.global_counts == g_counts

#         for i in range(n+1):
#             P = pvt.pivoter(G, min_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == [0]*i + c2[i:]
#             assert P.global_counts == [0]*i + g_counts[i:]

#         for i in range(n+1):
#             P = pvt.pivoter(G, max_k=i, resolution="v", backend=backend)
#             for c1, c2 in zip(P.vertex_counts, v_counts):
#                 assert c1 == c2[:i+1]
#             assert P.global_counts == g_counts[:i+1]

#         for i in range(n+1):
#             for j in range(i, n+1):
#                 P = pvt.pivoter(G, min_k=i, max_k=j, resolution="v", backend=backend)
#                 for c1, c2 in zip(P.vertex_counts, v_counts):
#                     assert c1 == [0]*i + c2[i:j+1]
#                 assert P.global_counts == [0]*i + g_counts[i:j+1]