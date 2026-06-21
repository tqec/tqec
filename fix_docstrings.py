
def fix_file(filename):
    with open(filename) as f:
        content = f.read()

    # Apply fixes
    content = content.replace("more efficient by manipulating text files directly and not creating ``BlockGraph`` objects.", "more efficient by manipulating text files directly without creating ``BlockGraph`` objects.")
    content = content.replace("File reading functions recover the integer position via int_position_before_scale, whose atol=0.35", "File reading functions recover the integer position via int_position_before_scale (atol=0.35)")
    content = content.replace("When writing visual files like COLLADA, pipe_direction is deduced by relative pos of Y half cube to neighbor. It shifts pos by 0.5 * pipe_direction along Z to place Y half-cube flush to pipe.", "When writing visual files like COLLADA, pipe_direction is deduced by relative pos to neighbor.\n    It shifts pos by 0.5 * pipe_direction along Z to place Y half-cube flush to pipe.")
    content = content.replace("Currently configured only for the collada writer. +1 shifts Y half cube toward pipe above (init), -1 toward", "For collada writer. +1 shifts Y half cube toward pipe above (init), -1 toward pipe below (meas).")
    content = content.replace("visual coordinate scaling factor--it has no meaning inside the compiler. It serves for 3D tools (primarily ``SketchUp``) to store positions in a visual coordinate space where blocks are separated by visible pipe gaps.", "visual coordinate scaling factor--it has no meaning inside the compiler.\n    It serves for 3D tools to store positions in visual space where blocks are separated by pipe gaps.")

    with open(filename, 'w') as f:
        f.write(content)

fix_file('src/tqec/interop/converters.py')
fix_file('src/tqec/interop/shared.py')
