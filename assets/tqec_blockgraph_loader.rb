require 'sketchup.rb'
require 'json'

# adjust the route
COMPONENT_FOLDER  ||= 'route_to_your_components_folder'
GRID_SIZE         ||= 3.0  # inches per grid unit

module TQEC
  module BlockGraphLoader

    def self.load_from_json
      model    = Sketchup.active_model
      entities = model.active_entities

      json_path = UI.openpanel("Select TQEC blockgraph JSON", "", "JSON Files|*.json||")
      return unless json_path

      begin
        raw  = File.read(json_path)
        data = JSON.parse(raw)
      rescue => e
        UI.messagebox("Failed to read or parse JSON:\n#{e.message}")
        return
      end

      # Place the cubes on a 3″ grid
      data["cubes"].each do |cube|
        kind      = cube["kind"]
        comp_file = File.join(COMPONENT_FOLDER, "#{kind.downcase}.skp")
        unless File.exist?(comp_file)
          UI.messagebox("Cube component not found:\n#{comp_file}")
          next
        end
        comp_def = model.definitions.load(comp_file)
        # scale grid position by 3″
        pos = cube["position"].map { |c| c * GRID_SIZE }
        tr  = Geom::Transformation.new(pos)
        entities.add_instance(comp_def, tr)
      end

      # Place the pipes between those grid-spaced cubes
      data["pipes"].each do |pipe|
        kind      = pipe["kind"]
        comp_file = File.join(COMPONENT_FOLDER, "#{kind.downcase}.skp")
        unless File.exist?(comp_file)
          UI.messagebox("Pipe component not found:\n#{comp_file}")
          next
        end
        comp_def = model.definitions.load(comp_file)
      
        # 1) scale both endpoints by GRID_SIZE
        u_scaled = pipe["u"].map { |c| c * GRID_SIZE }
        v_scaled = pipe["v"].map { |c| c * GRID_SIZE }

        # 2) midpoint between cube centers
        mid = u_scaled.zip(v_scaled).map { |u,v| (u + v) / 2.0 }

        # 3) unit-direction from u → v
        diff   = v_scaled.zip(u_scaled).map { |v,u| v - u }
        length = Math.sqrt(diff.inject(0){|sum,e| sum + e*e})
        dir    = diff.map { |d| d / length }  # e.g. [1,0,0] or [0,1,0], etc.

        # 4) offset so the 2″ pipe sits exactly between the 1″ cube faces:
        #    (2″/2 − 1″/2) = 0.5″
        face_offset = (2.0/2) - (1.0/2)  # => 0.5
        offset      = dir.map { |d| d * face_offset }

        # 5) final origin = midpoint minus that offset
        origin = mid.zip(offset).map { |m,o| m - o }
        tr     = Geom::Transformation.new(origin)

        entities.add_instance(comp_def, tr)
      end

      UI.messagebox("Blockgraph loaded")
    end

    unless file_loaded?(__FILE__)
      UI.menu("Plugins").add_item("Load TQEC BlockGraph") {
        self.load_from_json
      }
      file_loaded(__FILE__)
    end

  end
end
