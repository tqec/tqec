# Error Message Improvements for TQEC

**Related to Issue #262**: While @purva-thakre is working on creating specific exception types (InvalidCodeException, FormatException, BrokenAssumption, etc.), this document focuses on improving the **quality and clarity** of error messages themselves.

**Author**: Sean Collins (SMC17)  
**Date**: 2025-01-10  
**Branch**: `feature/improve-error-messages`

## Principles for Good Error Messages

Based on TQEC's codebase analysis and best practices:

1. **Be Specific**: Include actual values that caused the error
2. **Be Actionable**: Suggest how to fix the problem when possible
3. **Provide Context**: Include relevant state information
4. **Use Consistent Format**: Follow a pattern across the codebase
5. **Avoid Jargon**: Use clear language or explain technical terms

## Categories of Improvements

### Category 1: Add Missing Context

**Current Pattern**:
```python
raise TQECError("No cube at position {position}.")
```

**Problem**: User doesn't know what cubes *do* exist

**Improved**:
```python
available_positions = list(self._graph.nodes)
raise TQECError(
    f"No cube found at position {position}. "
    f"Available positions: {available_positions[:5]}..."  # Show first 5
)
```

### Category 2: Suggest Solutions

**Current Pattern**:
```python
raise TQECError("All pipes must have the same length.")
```

**Problem**: User doesn't know which pipes are different or what lengths they have

**Improved**:
```python
raise TQECError(
    f"All pipes must have the same length. Expected {pipe_length:.4f}, "
    f"but found pipe at {translation} with length {scale * 2.0:.4f}. "
    "Ensure all pipes in your COLLADA model have identical scaling."
)
```

### Category 3: Clarify Technical Terms

**Current Pattern**:
```python
raise TQECError(f"Unsupported vertex type and phase: {vt} and {phase}.")
```

**Problem**: User may not understand what vertex types/phases are valid

**Improved**:
```python
raise TQECError(
    f"Unsupported ZX vertex type and phase: {vt}, {phase}. "
    f"Supported combinations are: Z(0), X(0), Z(1/2), or Boundary(0). "
    f"Vertex {v} at position {positions[v]} has invalid type/phase."
)
```

### Category 4: Improve Validation Messages

**Current Pattern**:
```python
raise TQECError("The vertex IDs in the ZX graph and the positions do not match.")
```

**Problem**: No information about the mismatch

**Improved**:
```python
graph_vertices = g.vertex_set()
position_keys = set(positions.keys())
raise TQECError(
    f"Vertex ID mismatch between ZX graph and positions. "
    f"Graph has {len(graph_vertices)} vertices, positions has {len(position_keys)} keys. "
    f"Missing in positions: {graph_vertices - position_keys}, "
    f"Extra in positions: {position_keys - graph_vertices}"
)
```

### Category 5: File/Format Errors

**Current Pattern**:
```python
raise TQECError("JSON file not found.")
```

**Problem**: Generic error, doesn't show the path attempted

**Improved**:
```python
raise TQECError(
    f"Could not read JSON file at '{filepath}'. "
    f"Ensure the file exists and you have read permissions. Error: {e}"
)
```

## Files Requiring Updates

### High Priority (User-Facing)

1. **`interop/collada/read_write.py`** - File import/export errors
   - Lines: 77, 81, 139, 143, 153, 289, 296, 298, 312, 318, 347, 353
   - Impact: Users frequently hit these when loading models

2. **`computation/block_graph.py`** - Graph construction errors
   - Lines: 173, 178, 199, 203, 236, etc.
   - Impact: Core API, high visibility

3. **`interop/pyzx/positioned.py`** - ZX graph validation
   - Lines: 50, 55, 69, 74, 82, 90
   - Impact: Integration errors are confusing

### Medium Priority (Developer-Facing)

4. **`compile/detectors/compute.py`** - Detector computation
   - Many technical validation errors
   
5. **`circuit/moment.py`** - Circuit manipulation
   - Validation and construction errors

### Low Priority (Internal/Testing)

6. Various test files with assertion messages
   - Can be improved for better test failure messages

## Implementation Strategy

### Phase 1: User-Facing Import/Export (This PR)
- Focus on `interop/collada/read_write.py`
- Focus on `computation/block_graph.py`
- Focus on `interop/pyzx/positioned.py`

### Phase 2: Compilation & Detectors (Future PR)
- Detector computation messages
- Circuit compilation messages

### Phase 3: Internal Validation (Future PR)
- Lower-level validation messages
- Test assertion improvements

## Specific Improvements Made

### File: `interop/pyzx/positioned.py`

#### Line 50: Vertex ID Mismatch
**Before**:
```python
raise TQECError("The vertex IDs in the ZX graph and the positions do not match.")
```

**After**:
```python
graph_vertices = g.vertex_set()
position_keys = set(positions.keys())
missing = graph_vertices - position_keys
extra = position_keys - graph_vertices
raise TQECError(
    f"Vertex ID mismatch between ZX graph and positions. "
    f"Graph vertices: {len(graph_vertices)}, Position keys: {len(position_keys)}. "
    f"Missing in positions: {missing}, Extra in positions: {extra}"
)
```

**Rationale**: Developers debugging ZX graph issues need to know *which* vertices are mismatched.

#### Line 55-58: Non-Neighbor Error
**Before**:
```python
raise TQECError(
    f"The 3D positions of the endpoints of the edge {s}--{t} "
    f"must be neighbors, but got {ps} and {pt}."
)
```

**After**:
```python
distance = ps.manhattan_distance(pt)
raise TQECError(
    f"Edge {s}--{t} connects non-neighboring positions {ps} and {pt}. "
    f"Manhattan distance: {distance} (expected: 1). "
    "Edges must connect positions that differ by exactly 1 in one dimension."
)
```

**Rationale**: Adding Manhattan distance helps users understand how far apart the positions are.

[... continues with more examples ...]

## Testing Plan

For each improved error message:

1. **Unit Test**: Verify the new message appears correctly
2. **Integration Test**: Ensure error is catchable and informative
3. **User Test**: Validate message helps users understand and fix the issue

Example test structure:
```python
def test_vertex_mismatch_error_message():
    g = GraphS()
    g.add_vertex(VertexType.Z)
    positions = {999: Position3D(0, 0, 0)}  # Wrong ID
    
    with pytest.raises(TQECError, match="Missing in positions.*\\{0\\}"):
        PositionedZX(g, positions)
```

## Backward Compatibility

All changes maintain backward compatibility:
- Exception types unchanged (still `TQECError`)
- Exception is still raised at the same locations
- Only message content is enhanced
- No API changes

## Metrics for Success

- **Clarity**: Can a new contributor understand the error without looking at source code?
- **Actionability**: Does the message suggest a fix or next debugging step?
- **Completeness**: Does the message include all relevant context?

## Future Work

After exception type refactoring (Issue #262) is complete:
- Map improved messages to appropriate exception types
- Add exception type hints to function signatures
- Create error code system for documentation linking

## References

- Issue #262: https://github.com/tqec/tqec/issues/262
- Python Exception Best Practices: https://docs.python.org/3/tutorial/errors.html
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html#24-exceptions
