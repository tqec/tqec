#########################
# HOW TO SET THIS FILE UP.
#########################
# To enable this file as a SketchUp plugin/extension:
#   1. Locate your Sketchup component library and write it in the COMPONENT_FOLDER variable.
#      Example location (Windows computer): "C:/Program Files (x86)/Google/Google SketchUp 8/Components/"
#   2. Find files for all primitives on TQEC shared folder https://....//
#      Place the files from (a) on your SketchUp COMPONENT_FOLDER.
#   3. Save this file to your SketchUp plugins library
#      Example location (Windows computer): "C:/Program Files (x86)/Google/Google SketchUp 8/Plugins")


#########################
# HOW TO USE tHIS FILE.
#########################
# In SketchUp:
#    1. Toolbar: Plugins (or extensions) > Load TQEC BlockGraph.
#    2. Select JSON file to import.


# Required modules
require "sketchup.rb"

# Helper variables
COMPONENT_FOLDER = "C:/Program Files (x86)/Google/Google SketchUp 8/Components/"
GRID_SIZE = 3.0  # inches per grid unit

module TQEC
  module BackupParser
    def self.backup_json_parser(raw_json)

      # Clean raw JSON (indents)
      json_str = raw_json.gsub(/\s+/, '')

      # Find indexes for cubes, pipes, and ports sections
      cubes_start_idx = json_str.index('"cubes":')
      pipes_start_idx = json_str.index('"pipes":')
      ports_start_idx = json_str.index('"ports":')

      # Stringify sections
      cubes_str = json_str[(cubes_start_idx + '"cubes":'.length)...pipes_start_idx].chomp(',')
      pipes_str = json_str[(pipes_start_idx + '"pipes":'.length)...ports_start_idx].chomp(',')
      ports_str = json_str[(ports_start_idx + '"ports":'.length)...json_str.length].chomp(',').gsub(/\}$/, '')

      # Clean section strings
      cubes_str = cubes_str.gsub(/^\[/, '').gsub(/^\{/, '').gsub(/^\[\{/, '')
      cubes_str = cubes_str.gsub(/\]$/, '').gsub(/\}$/, '').gsub(/\}\]$/, '')
      pipes_str = pipes_str.gsub(/^\[/, '').gsub(/^\{/, '').gsub(/^\[\{/, '')
      pipes_str = pipes_str.gsub(/\]$/, '').gsub(/\}$/, '').gsub(/\}\]$/, '')
      ports_str = ports_str.gsub(/^\[/, '').gsub(/^\{/, '').gsub(/^\[\{/, '')
      ports_str = ports_str.gsub(/\]$/, '').gsub(/\}$/, '').gsub(/\}\]$/, '')

      # Break sections into arrays
      cubes_str_array = cubes_str.split("},{")
      cubes_str_array[-1] = cubes_str_array.last.gsub(/\}$/, '') if cubes_str_array.last

      pipes_str_array = pipes_str.split("},{")
      pipes_str_array[-1] = pipes_str_array.last.gsub(/\}$/, '') if pipes_str_array.last

      ports_str_array = ports_str.split("},{")
      ports_str_array[-1] = ports_str_array.last.gsub(/\}$/, '') if ports_str_array.last

      # Parse cubes and pipes info into arrays
      cubes = cubes_str_array.map { |cube_str| self.parse_from_string(cube_str) }
      pipes = pipes_str_array.map { |pipe_str| self.parse_from_string(pipe_str) }

      # Return hashes of cubes and pipes
      { "cubes" => cubes, "pipes" => pipes }
    end

    def self.parse_from_string(item_str)

      item_hash = {}

      position_idx = item_str.index('"position"')
      kind_idx = item_str.index('"kind"')
      label_idx = item_str.index('"label"')
      transform_idx = item_str.index('"transform"')
      u_idx = item_str.index('"u"')
      v_idx = item_str.index('"v"')
      in_idx = item_str.index('"In"')
      out_idx = item_str.index('"Out"')

      if position_idx
        next_key_start_idx = kind_idx
        position_str = item_str[(position_idx + '"position":'.length)...kind_idx].chomp(',').strip
        item_hash["position"] = self.parse_positions(position_str, :integer)
      end

      if u_idx
        next_key_start_idx = v_idx
        u = item_str[(u_idx + '"u":'.length)...next_key_start_idx].chomp(',').strip
        item_hash["u"] = self.parse_positions(u, :integer)
      end

      if v_idx
        next_key_start_idx = kind_idx
        v = item_str[(v_idx + '"v":'.length)...next_key_start_idx].chomp(',').strip
        item_hash["v"] = self.parse_positions(v, :integer)
      end

      if kind_idx
        position_idx ? next_key_start_idx = label_idx : next_key_start_idx = transform_idx
        kind = item_str[(kind_idx + '"kind":'.length)...next_key_start_idx].chomp(',').strip
        item_hash["kind"] = kind.empty? ? "" : kind.gsub(/^"|"$/, '')
      end

      if label_idx
        next_key_start_idx = transform_idx
        label = item_str[(label_idx + '"label":'.length)...next_key_start_idx].chomp(',').strip
        item_hash["label"] = label.empty? ? "" : label.gsub(/^"|"$/, '')
      end

      if transform_idx
        next_key_start_idx = item_str.length
        transform = item_str[(transform_idx + '"transform":'.length)...next_key_start_idx].strip
        item_hash["transform"] = self.parse_transformation(transform, :integer)
      end

      item_hash
    end

    def self.parse_positions(str, numeric_type = :float)

      # Remove absolutely everything that's not a digit
      cleaned_content = str.gsub(/[^\d]/, '')

      if cleaned_content.length == 3
        # Split into individual number items
        elements = cleaned_content.split('').map do |s|
          begin
            Integer(s)
          rescue ArgumentError
            return []
          end
        end
      else
        UI.messagebox("Malformed positional information. Check cube cube positions and u-v edges (start-end positions for pipes).")
        return []
      end

      elements
    end

    def self.parse_transformation(str, numeric_type = :float)

      # Trim aggressively to avoid problems with extra characters
      cleaned_content = str.gsub(/[^\d]/, '')

      if cleaned_content.length == 9
        # Split into individual number items
        elements_flat = cleaned_content.split('').map do |s|
          begin
            Integer(s)
          rescue ArgumentError
            return []
          end
        end

        # Organise as matrix
        elements = []
        (0...elements_flat.length).step(3) do |i|
          elements << elements_flat[i, 3]
        end
      else
        UI.messagebox("Malformed transformation matrix. Check transformation matrices for cubes and pipes.")
        return []
      end

      # Return elements or empty array
      elements || []
    end
  end # Ends module BackupParser

  module BlockGraphLoader


    # Actions
    def self.load_from_json

      version_flag = false
      begin
        require "json"
      rescue LoadError
        version_flag = true
      end

      model    = Sketchup.active_model
      entities = model.active_entities

      json_path = UI.openpanel("Select TQEC blockgraph JSON", "", "JSON Files|*.json||")
      return unless json_path

      # Get raw JSON data from file
      begin
        raw  = File.read(json_path)
      rescue => e
        UI.messagebox("Failed to read JSON:\n#{e.message}")
        return
      end

      if version_flag == false
        data = JSON.parse(raw)
      else
        data = TQEC::BackupParser.backup_json_parser(raw)
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

  end  # Ends module BlockGraphLoader
end
