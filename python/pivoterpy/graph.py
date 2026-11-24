from array import array as _array
from collections.abc import Sequence
from gzip import open as _gzip_open


_U32_MAX = 0xFFFFFFFF


class _EdgeView(Sequence):
    """Lazy sequence view over a flat ``uint32`` buffer of ``u, v`` pairs."""

    __slots__ = ("_data",)

    def __init__(self, data):
        self._data = data

    def __len__(self) -> int:
        return len(self._data) // 2

    def __iter__(self):
        data = self._data
        for i in range(0, len(data), 2):
            yield (data[i], data[i + 1])

    def __getitem__(self, index):
        n = len(self)
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(n))]
        if index < 0:
            index += n
        if index < 0 or index >= n:
            raise IndexError("edge index out of range")
        pos = index * 2
        return (self._data[pos], self._data[pos + 1])

    def __repr__(self) -> str:
        preview = ", ".join(repr(e) for _, e in zip(range(5), self))
        more = ", ..." if len(self) > 5 else ""
        return f"<Graph.edges [{preview}{more}] ({len(self)} edges)>"


def _new_edge_buffer() -> _array:
    buf = _array("I")
    if buf.itemsize != 4:
        raise RuntimeError("this platform does not provide 32-bit unsigned ints")
    return buf


def _unique_keys(keys: _array):
    """Return the unique encoded edge keys, using NumPy when available."""
    if not keys:
        return ()
    if keys.itemsize != 8:
        raise RuntimeError("this platform does not provide 64-bit unsigned ints")
    try:
        import numpy as np
    except ImportError:
        # Fallback: still much smaller than a set of Python tuples.
        return sorted(set(keys))
    return np.unique(np.frombuffer(keys, dtype=np.uint64))


def _pack_edges(buf: _array, keys) -> None:
    append = buf.append
    for key in keys:
        key = int(key)
        append(key >> 32)
        append(key & _U32_MAX)


class Graph:
    """
    The Graph class represents the graph data structure and provides several
    constructors for initializing from common formats. It automatically translates
    node IDs into an internal contiguous space, calculates node degrees, and
    tracks total edges and vertices.

    Edges are stored in a flat native-endian ``uint32`` buffer (a ``bytes``
    object, viewed as ``u32`` pairs) so memory stays at ``8 * m`` bytes instead
    of a Python object per edge, and the Rust backend can borrow it with no copy.
    """

    __slots__ = ("_edges", "_view", "n", "m", "degrees", "nodes", "experimental")

    def __init__(self, edges, n: int, nodes: list[int] = None):
        """
        Initializes a Graph object.

        Args:
            edges: An iterable of ``(u, v)`` pairs with internal contiguous node
                IDs, or an already-normalized flat ``array('I')``/``bytes`` buffer.
            n (int): The number of unique nodes in the graph.
            nodes (list[int], optional): A mapping of internal node IDs (index) back to
                                         their original IDs (value). If None, it's assumed
                                         internal IDs are already 0 to n-1. Defaults to None.
        """
        if isinstance(edges, bytes):
            raw = edges
        elif isinstance(edges, _array) and edges.typecode == "I":
            raw = edges.tobytes()
        else:
            buf = _new_edge_buffer()
            append = buf.append
            for u, v in edges:
                if u > v:
                    u, v = v, u
                append(u)
                append(v)
            raw = buf.tobytes()

        if len(raw) % 8:
            raise ValueError("edge buffer length is not a multiple of 8 bytes")

        self._edges = raw
        self._view = memoryview(raw).cast("I")
        self.n = n
        self.m = len(raw) // 8

        # If no mapping is provided, assume it's already contiguous 0 to N-1
        self.nodes = nodes if nodes is not None else list(range(n))
        self.degrees = [0] * self.n
        view = self._view
        for i in range(0, len(view), 2):
            u, v = view[i], view[i + 1]
            if u >= n or v >= n:
                raise ValueError("edge endpoint is outside the node range")
            self.degrees[u] += 1
            self.degrees[v] += 1

        self.experimental = None

    @property
    def edges(self) -> _EdgeView:
        """Lazy view of internal ``(u, v)`` edges (``u < v``)."""
        return _EdgeView(self._view)

    def edge_bytes(self) -> bytes:
        """Native-endian flat ``u32`` pairs, borrowed by the Rust backend."""
        return self._edges

    @classmethod
    def from_adj_matrix(cls, array: Sequence[Sequence[int | float | bool]]) -> 'Graph':
        """
        Creates a Graph from the upper triangle of a square adjacency matrix.
        Edges are inferred from entries greater than 0.

        Args:
            array (Sequence[Sequence[int | float | bool]]): A square adjacency matrix.

        Returns:
            Graph: A new Graph instance.
        """

        try:
            assert len(array) == len(array[0]), "Adjacency matrix must be square"
        except IndexError:
            assert 1==0, "go touch grass"

        n = len(array)
        buf = _new_edge_buffer()
        append = buf.append
        for i in range(n):
            for j in range(i + 1, n):
                if array[i][j] > 0:
                    append(i)
                    append(j)

        return cls(edges=buf, n=n)

    @classmethod
    def from_edge_list(cls, array: list[tuple[int, int]], deduplicate: bool = True) -> 'Graph':
        """
        Creates a Graph from a list of (u, v) edge tuples.
        Compresses non-contiguous vertex IDs into a contiguous 0 to N-1 internal space,
        ignoring self-loops and duplicate edges.

        Args:
            array (list[tuple[int, int]]): A list of edge tuples, where u and v are
                                           the original node IDs.
            deduplicate (bool): Drop duplicate edges. Set to False only when the
                                input is already known to be simple.

        Returns:
            Graph: A new Graph instance with internal contiguous IDs and a mapping
                   back to original IDs.
        """
        old_to_new = {}
        new_to_old = []
        buf = _new_edge_buffer()
        keys = _array("Q") if deduplicate else None

        for u, v in array:
            assert isinstance(u, int) and isinstance(v, int), "Node indices must be integers"

            if u == v:
                continue  # Ignore self-loops

            # Map U
            if u not in old_to_new:
                if len(new_to_old) >= _U32_MAX:
                    raise OverflowError("graph has too many vertices for a uint32 edge buffer")
                old_to_new[u] = len(new_to_old)
                new_to_old.append(u)

            # Map V
            if v not in old_to_new:
                if len(new_to_old) >= _U32_MAX:
                    raise OverflowError("graph has too many vertices for a uint32 edge buffer")
                old_to_new[v] = len(new_to_old)
                new_to_old.append(v)

            internal_u = old_to_new[u]
            internal_v = old_to_new[v]
            if internal_u > internal_v:
                internal_u, internal_v = internal_v, internal_u

            if keys is not None:
                keys.append((internal_u << 32) | internal_v)
            else:
                buf.append(internal_u)
                buf.append(internal_v)

        if keys is not None:
            _pack_edges(buf, _unique_keys(keys))

        assert len(buf) > 0, "No valid edges provided"

        return cls(edges=buf, n=len(new_to_old), nodes=new_to_old)

    @classmethod
    def from_edge_file(
        cls,
        path,
        comments: str = "#",
        delimiter: str | None = None,
        deduplicate: bool = False,
    ) -> 'Graph':
        """
        Streams a whitespace-delimited edge list from disk into compact storage.

        Comment lines and malformed/short lines are skipped. Compressed ``.gz``
        files are read transparently. Large SNAP-style files are already simple,
        so ``deduplicate`` defaults to False to avoid building a huge set.

        Args:
            path: File path (``.gz`` is detected by suffix).
            comments (str): Lines starting with this prefix are skipped.
            delimiter (str | None): Optional field delimiter; whitespace by default.
            deduplicate (bool): Drop duplicate edges (may use NumPy if available).

        Returns:
            Graph: A new Graph instance.
        """
        path = str(path)
        opener = _gzip_open if path.endswith(".gz") else open

        old_to_new = {}
        new_to_old = []
        buf = _new_edge_buffer()
        keys = _array("Q") if deduplicate else None

        with opener(path, "rt") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith(comments):
                    continue
                parts = stripped.split(delimiter) if delimiter else stripped.split()
                if len(parts) < 2:
                    continue
                try:
                    u = int(parts[0])
                    v = int(parts[1])
                except ValueError:
                    continue
                if u == v:
                    continue

                if u not in old_to_new:
                    if len(new_to_old) >= _U32_MAX:
                        raise OverflowError("graph has too many vertices for a uint32 edge buffer")
                    old_to_new[u] = len(new_to_old)
                    new_to_old.append(u)

                if v not in old_to_new:
                    if len(new_to_old) >= _U32_MAX:
                        raise OverflowError("graph has too many vertices for a uint32 edge buffer")
                    old_to_new[v] = len(new_to_old)
                    new_to_old.append(v)

                internal_u = old_to_new[u]
                internal_v = old_to_new[v]
                if internal_u > internal_v:
                    internal_u, internal_v = internal_v, internal_u

                if keys is not None:
                    keys.append((internal_u << 32) | internal_v)
                else:
                    buf.append(internal_u)
                    buf.append(internal_v)

        if keys is not None:
            _pack_edges(buf, _unique_keys(keys))

        assert len(buf) > 0, "No valid edges provided"

        return cls(edges=buf, n=len(new_to_old), nodes=new_to_old)

    @classmethod
    def from_networkx(cls, G: 'object') -> 'Graph':
        """
        Creates a Graph from an existing NetworkX graph object.
        Note: This constructor assumes NetworkX node IDs are already contiguous
        or will be handled by the `Graph` constructor's default `nodes` mapping.

        Args:
            G (object): A NetworkX graph object.

        Returns:
            Graph: A new Graph instance.
        """
        return cls(((u, v) for u, v in G.edges), n=G.number_of_nodes())
