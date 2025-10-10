# TQEC Topologiq Integration: Potential Improvements

**Author**: Sean Collins  
**Date**: October 10, 2025  
**Purpose**: Identify opportunities for enhancement based on deep understanding of the codebase

---

## Executive Summary

After thoroughly analyzing the topologiq integration, I've identified several improvement opportunities. These range from simple usability enhancements to more ambitious feature additions. All suggestions are informed by:
- The bug I fixed (coordinate transformation)
- Patterns observed in other TQEC interop modules
- Open GitHub issues and community discussions
- The architecture document I created

**Key principle**: Start small, prove value, then expand.

---

## Category 1: Error Messages and Debugging (HIGH IMPACT, LOW EFFORT)

### Improvement 1.1: Enhanced Coordinate Mismatch Error Messages

**Current Problem**:
When `read_from_lattice_dicts()` receives coordinates that don't align with `pipe_length`, users get a generic "round_or_fail" error that doesn't explain what went wrong or how to fix it.

**Proposed Solution**:
```python
def read_from_lattice_dicts(lattice_nodes, lattice_edges, graph_name=""):
    # ... existing validation...
    
    try:
        for pos, cube_kind in parsed_cubes:
            if isinstance(cube_kind, YHalfCube):
                block_graph.add_cube(
                    int_position_before_scale(
                        offset_y_cube_position(pos, pipe_length),
                        pipe_length
                    ),
                    cube_kind
                )
            else:
                block_graph.add_cube(int_position_before_scale(pos, pipe_length), cube_kind)
    except ValueError as e:
        raise ValueError(
            f"Coordinate transformation failed for position {pos}. "
            f"Expected coordinates at multiples of {1 + pipe_length} (pipe_length={pipe_length}). "
            f"Received: {pos}. "
            f"This might indicate a version mismatch between topologiq output and TQEC expectations. "
            f"Original error: {e}"
        ) from e
```

**Benefits**:
- Users immediately understand what went wrong
- Provides actionable information (expected vs actual coordinates)
- Hints at likely causes (version mismatch)
- Minimal code change (just better error wrapping)

**Estimated Effort**: 2-4 hours

**Risk**: Very low - only changes error messages, not logic

---

### Improvement 1.2: Optional Validation Mode

**Current Problem**:
`read_from_lattice_dicts()` performs minimal validation. Subtle issues (like disconnected components or invalid graph structures) only surface later during compilation or simulation.

**Proposed Solution**:
```python
def read_from_lattice_dicts(
    lattice_nodes,
    lattice_edges,
    graph_name="",
    validate=False  # New parameter, default=False for backward compatibility
):
    # ... existing conversion code...
    
    if validate:
        _validate_block_graph(block_graph, lattice_nodes, lattice_edges)
    
    return block_graph


def _validate_block_graph(
    block_graph: BlockGraph,
    original_nodes: dict,
    original_edges: dict
) -> None:
    """Perform optional deep validation of converted BlockGraph."""
    
    # Check 1: Connectivity
    if block_graph.num_cubes > 1 and not is_connected(block_graph._graph):
        warnings.warn(
            f"BlockGraph has {len(list(nx.connected_components(block_graph._graph)))} "
            f"disconnected components. This might indicate missing pipes or incorrect topology."
        )
    
    # Check 2: Port consistency
    port_count = sum(1 for cube in block_graph.cubes if isinstance(cube.kind, Port))
    if port_count != block_graph.num_ports:
        raise ValueError(f"Port count mismatch: {port_count} Port cubes but {block_graph.num_ports} in registry")
    
    # Check 3: Coordinate distribution sanity
    positions = block_graph.occupied_positions
    if positions:
        max_coord = max(max(p.x, p.y, p.z) for p in positions)
        if max_coord > len(original_nodes) * 2:
            warnings.warn(
                f"Maximum coordinate {max_coord} seems unusually large for {len(original_nodes)} nodes. "
                f"This might indicate coordinate transformation issues."
            )
    
    # Check 4: All pipes have valid endpoints
    for pipe in block_graph.pipes:
        # Pipes should connect to cubes that exist
        if pipe.u not in block_graph or pipe.v not in block_graph:
            raise ValueError(f"Pipe connects non-existent cubes: {pipe.u} -> {pipe.v}")
```

**Benefits**:
- Catch errors early with clear diagnostics
- Opt-in (doesn't break existing code)
- Helpful for debugging new topologiq versions
- Could save hours of debugging time

**Estimated Effort**: 4-8 hours (including tests)

**Risk**: Low - opt-in feature doesn't affect default behavior

---

## Category 2: Logging and Observability (MEDIUM IMPACT, LOW EFFORT)

### Improvement 2.1: Structured Logging

**Current Problem**:
No logging during conversion. When things go wrong (especially with large circuits), it's hard to understand what happened.

**Proposed Solution**:
```python
import logging

logger = logging.getLogger(__name__)

def read_from_lattice_dicts(lattice_nodes, lattice_edges, graph_name=""):
    logger.info(
        f"Converting topologiq lattice to BlockGraph",
        extra={
            "graph_name": graph_name,
            "num_nodes": len(lattice_nodes),
            "num_edges": len(lattice_edges),
            "pipe_length": 2.0  # or determined value
        }
    )
    
    # ... conversion logic...
    
    logger.info(
        f"BlockGraph created successfully",
        extra={
            "graph_name": graph_name,
            "num_cubes": block_graph.num_cubes,
            "num_pipes": block_graph.num_pipes,
            "num_ports": block_graph.num_ports,
            "spacetime_volume": block_graph.spacetime_volume
        }
    )
    
    if block_graph.num_ports > 0:
        logger.debug(f"Automatically created {block_graph.num_ports} Port cubes")
    
    return block_graph
```

**Benefits**:
- Easy debugging of large circuit conversions
- Performance profiling (can log timestamps)
- Helpful for users and developers
- Follows Python logging best practices

**Estimated Effort**: 2-3 hours

**Risk**: Very low - logging is non-invasive

---

## Category 3: Compatibility and Interop (MEDIUM-HIGH IMPACT, MEDIUM EFFORT)

### Improvement 3.1: Support for topologiq Metadata Preservation

**Context**:
topologiq creates beautiful 3D visualizations with additional metadata (colors, labels, etc.). Currently, this metadata is lost during conversion.

**Proposed Solution**:
```python
def read_from_lattice_dicts(
    lattice_nodes,
    lattice_edges,
    graph_name="",
    preserve_metadata=False  # New parameter
):
    # ... existing conversion...
    
    if preserve_metadata:
        # Store original topologiq coordinates as cube metadata
        for cube in block_graph.cubes:
            topo_node_id = _find_node_id_for_position(cube.position, lattice_nodes, pipe_length)
            if topo_node_id is not None:
                original_coords, original_kind = lattice_nodes[topo_node_id]
                cube.metadata = {
                    "topologiq_id": topo_node_id,
                    "topologiq_position": original_coords,
                    "topologiq_kind": original_kind
                }
    
    return block_graph
```

**Benefits**:
- Better round-trip fidelity
- Easier debugging (can compare TQEC vs topologiq coordinates)
- Potential for future visualization improvements
- Helps with integration testing

**Estimated Effort**: 6-10 hours (including tests and documentation)

**Risk**: Low - opt-in feature

**Note**: This might require adding a `metadata` field to the `Cube` class, which is a more invasive change. Alternative: store metadata in BlockGraph itself.

---

### Improvement 3.2: Compatibility Layer for Different topologiq Versions

**Context**:
topologiq is actively developed. Output format might change between versions. The coordinate bug I fixed might have been caused by a version mismatch.

**Proposed Solution**:
```python
def read_from_lattice_dicts(
    lattice_nodes,
    lattice_edges,
    graph_name="",
    topologiq_version=None  # Auto-detect or specify
):
    # Auto-detect version from data structure if not specified
    if topologiq_version is None:
        topologiq_version = _detect_topologiq_version(lattice_nodes, lattice_edges)
    
    logger.info(f"Using topologiq version compatibility: {topologiq_version}")
    
    # Version-specific handling
    if topologiq_version >= "2.0":
        # Newer format (if it changes)
        pipe_length = 2.0
    elif topologiq_version >= "1.0":
        # Current format
        pipe_length = 2.0
    else:
        # Legacy format (if needed)
        pipe_length = 1.0
        logger.warning(f"Using legacy topologiq format (version {topologiq_version})")
    
    # ... rest of conversion with version-aware logic...
```

**Benefits**:
- Future-proof against topologiq changes
- Clear error messages for incompatible versions
- Supports users with different topologiq installations
- Documents assumptions about topologiq output

**Estimated Effort**: 8-12 hours (requires understanding topologiq versioning)

**Risk**: Medium - requires coordination with topologiq maintainers

---

## Category 4: Documentation and Examples (HIGH IMPACT, MEDIUM EFFORT)

### Improvement 4.1: Comprehensive Integration Guide

**Current Problem**:
The topologiq integration is documented in docstrings, but there's no comprehensive guide showing the full pipeline with real examples.

**Proposed Solution**:
Create `docs/guides/topologiq_integration.md` with:
1. Overview of the pipeline (QASM → PyZX → topologiq → TQEC → Stim)
2. Step-by-step tutorial with Steane code example
3. Troubleshooting common issues
4. Explanation of coordinate systems
5. Performance tips for large circuits
6. Integration with Qiskit and Qrisp

**Benefits**:
- Lower barrier to entry for new users
- Reduces support burden
- Showcases TQEC's capabilities
- Complements existing notebook examples

**Estimated Effort**: 12-16 hours (writing + examples)

**Risk**: Low - documentation-only change

---

## Category 5: Performance (MEDIUM IMPACT, MEDIUM-HIGH EFFORT)

### Improvement 5.1: Batch Processing for Large Circuits

**Context**:
Current implementation processes nodes and edges sequentially. For circuits with 1000+ nodes, this could be slow.

**Proposed Solution**:
```python
def read_from_lattice_dicts(lattice_nodes, lattice_edges, graph_name=""):
    # Auto-select strategy based on size
    if len(lattice_nodes) > 1000:
        return _read_from_lattice_dicts_batched(lattice_nodes, lattice_edges, graph_name)
    else:
        return _read_from_lattice_dicts_sequential(lattice_nodes, lattice_edges, graph_name)


def _read_from_lattice_dicts_batched(lattice_nodes, lattice_edges, graph_name):
    """Optimized batch processing for large circuits."""
    block_graph = BlockGraph(graph_name)
    pipe_length = 2.0
    
    # Pre-allocate and batch-transform all positions
    all_positions = {}
    for node_id, (coords, kind_str) in lattice_nodes.items():
        if kind_str != "ooo":
            pos = FloatPosition3D(*coords)
            all_positions[node_id] = int_position_before_scale(pos, pipe_length)
    
    # Batch add all cubes
    cubes_to_add = []
    for node_id, (coords, kind_str) in lattice_nodes.items():
        if kind_str != "ooo":
            kind = block_kind_from_str(kind_str.upper())
            if isinstance(kind, CubeKind):
                cubes_to_add.append((all_positions[node_id], kind))
    
    for pos, kind in cubes_to_add:
        block_graph.add_cube(pos, kind)
    
    # Batch add all pipes
    # ... similar batching logic...
    
    return block_graph
```

**Benefits**:
- Faster processing of large circuits
- Better scalability
- Can leverage NumPy vectorization if needed
- Automatic selection (no API change)

**Estimated Effort**: 16-24 hours (including benchmarking)

**Risk**: Medium - needs careful testing to ensure correctness

---

## Recommended Implementation Order

Based on impact, effort, and risk, I recommend this order:

### Phase 1: Quick Wins (Week 1-2)
1. **Enhanced error messages** (Improvement 1.1) - 2-4 hours
2. **Structured logging** (Improvement 2.1) - 2-3 hours
3. **Start documentation guide** (Improvement 4.1) - initial draft 4-6 hours

**Rationale**: High impact, low risk, immediate value for users.

### Phase 2: Validation and Robustness (Week 3-4)
1. **Optional validation mode** (Improvement 1.2) - 4-8 hours
2. **Finish documentation guide** (Improvement 4.1) - polish and examples 8-10 hours

**Rationale**: Builds on Phase 1, improves reliability.

### Phase 3: Advanced Features (Month 2+)
1. **topologiq metadata preservation** (Improvement 3.1) - 6-10 hours
2. **Version compatibility layer** (Improvement 3.2) - 8-12 hours
3. **Batch processing optimization** (Improvement 5.1) - 16-24 hours

**Rationale**: More ambitious features, requires more coordination with community.

---

## Alternative: Integration with Existing Issues

Rather than implementing these independently, many align with existing GitHub issues:

- **Issue #449 (PyZX → TQEC)**: Improvements 3.1, 3.2, 4.1 directly support this
- **Issue #523 (Greedy ZX → 3D algorithm)**: Improvement 4.1 could document this
- **Issue #720 (Framework integration PR)**: Improvements 1.1, 1.2, 2.1 would help this PR
- **Issue #723 (topologiq integration)**: All improvements are relevant!

**Suggestion**: Frame these improvements as supporting/fixing existing issues rather than creating new feature requests.

---

## Summary: Top 3 Recommendations

If I could only implement three improvements, it would be:

### 1. Enhanced Error Messages (Improvement 1.1)
- **Why**: Immediate user-facing impact
- **Effort**: 2-4 hours
- **Risk**: Very low
- **Benefit**: Saves debugging time for everyone

### 2. Optional Validation Mode (Improvement 1.2)
- **Why**: Catches errors early, high debugging value
- **Effort**: 4-8 hours
- **Risk**: Low (opt-in)
- **Benefit**: Prevents hard-to-debug issues downstream

### 3. Comprehensive Integration Guide (Improvement 4.1)
- **Why**: Lowers barrier to entry, showcases TQEC
- **Effort**: 12-16 hours
- **Risk**: Low (documentation only)
- **Benefit**: Helps onboard new users and contributors

**Total estimated effort**: 18-28 hours spread over 2-3 weeks

---

## How to Propose These

**Strategy**: Don't open new issues immediately. Instead:

1. Wait for feedback on current PR #720 comment
2. If positive, offer to implement 1-2 small improvements as follow-up PRs
3. Frame them as "noticed while fixing the coordinate bug"
4. Keep PRs small and focused (one improvement per PR)
5. Always include tests and documentation

**Example approach**:
> "While fixing the coordinate transformation bug, I noticed error messages could be more helpful. Would it be valuable if I opened a PR to enhance error messages in read_from_lattice_dicts()? Happy to keep it small and focused."

---

**End of Potential Improvements Document**
