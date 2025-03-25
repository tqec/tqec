# THIS FILE IS CURRENTLY SIMPLY A DEMONSTRATION OF PRINCIPLE. IT WILL BE DEVELOPED FURTHER.

# User MUST enter local path to their component library
library_path = ".../Google/Google SketchUp 8/Components/Components Sampler/"
node_type = "zxz"

# A file must exist for each component, and should be located inside the folder above.
# This might happen automatically by saving a block to the library via the graphical interface.
# Else, it is also possible to take a block, place it at (0,0,0), save as zxz.skp, and dump it in the library folder.
file_path = File.join(library_path, "#{node_type}.skp")
model = Sketchup.active_model
definitions = model.definitions
component_definition = definitions.load(file_path)
if component_definition
    transformation = Geom::Transformation.new([0, 0, 0])
    instance = model.entities.add_instance(component_definition, transformation)
end
