# Changelog

## `v0.2.0` (2026-03-24)

### Breaking changes:
- `find_correlation_surfaces` does not have the `roots` and `reduce_to_minimal_generators`
  parameters any more. New parameters `vertex_ordering` and `parallel` has been added.
- `BlockGraph.find_correlation_surfaces` does not have a `reduce_to_minimal_generators` parameter
  any more.
- `find_correlation_surfaces` has been moved from `tqec.interop.pyzx.correlation` to 
  `tqec.computation.correlation`.

### Improvements:
- Reimplement `with_mapped_qubit_indices` using regex matching (#857)
- Improve compile test runtime by memoizing database creation and reducing saving (#855)
- Optimize with_mapped_qubit_indices (#853)
- Add slow decorators to speed up testing (#828)
- Divide "import tqec" time by 5 (#808)
- Improve performances by x100+ on some benchmarks (#809)
- Improve `CorrelationSurface`-related efficiency and usability (#822)
- A polynomial-time algorithm for finding correlation surfaces (#707)
- Re-schedule measurements in a `LayoutLayer` (#778)

### Documentation
- Update CONTRIBUTING.md (#859)
- Address JOSS editor comments (#848)
- Address JOSS reviewer feedback (#780)
- fix: typo "hardmard" (#801)