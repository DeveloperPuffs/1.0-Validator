import sys
import argparse
import json
import base64
import gzip
import csv

parser = argparse.ArgumentParser(description="Open and display content of a specified file.")
parser.add_argument("file_path", help="The path to the \"player_levels.json\" file to open.")
parser.add_argument("level_name", help="The name of the level to validate.")

parsed_arguments = parser.parse_args()
file_path = parsed_arguments.file_path
level_name = parsed_arguments.level_name

try:
    file = open(file_path, "r")
    data = json.load(file)
    file.close()
except FileNotFoundError:
    print(f"File not found: \"{file_path}\"")
    sys.exit(1)
except Exception as error:
    print(f"An error occurred: {error}")
    sys.exit(1)

chosen_level = None
for level in data:
    if level["name"] == level_name:
        chosen_level = level
        break

if chosen_level == None:
    print(f"No level named \"{level_name}\" found in levels.")
    sys.exit(1)


def decode_level(level_data, official_level=False):
    if official_level:
        level_data = "H4sIAAAAAAAAA" + level_data
    base64_decoded = base64.urlsafe_b64decode(level_data.encode())
    decompressed = gzip.decompress(base64_decoded)
    return decompressed.decode()


decoded_level_data = decode_level(chosen_level["levelData"])
level_objects = decoded_level_data.split(";")
level_objects.pop()
level_objects.pop(0)

schema_file = open("schema.json", "r")
schema_data = json.load(schema_file)
schema_file.close()

# Parse the object properties into a dictionary with the property ID as the keys
object_properties = {}
for field in schema_data["classes"]["Common"]["fields"]:
    object_properties[str(field["id"])] = {
        "name": field["name"],
        "type": field["type"]
    }

objects_file = open("objects.csv", "r")
objects_data = dict(csv.reader(objects_file))
objects_file.close()

object_identifier_whitelist = list(range(1, 42))  # Most 1.0 object IDs
object_identifier_whitelist.pop(13)  # The object ID of 14 dosen't seem to exist
object_identifier_whitelist.append(899)  # Color Trigger (a different type of color trigger was used in 1.0)
object_identifier_whitelist.append(1715)  # Spike Black Pit Hazard
object_identifier_whitelist.append(1903)  # Colored Gradient Single Slab

object_identifier_whitelist.append(83)  # Grid Patterned Square (not from 1.0 but allowed?)
object_identifier_whitelist.append(1934)  # Song Trigger (used to splice the song)

# These non-1.0 objects were found in the level
"""
object_identifier_whitelist.append(502) # Decorative Grid Patterned Inner Corner
object_identifier_whitelist.append(1716) # Spike Black Hazard
object_identifier_whitelist.append(110) # Small chain
object_identifier_whitelist.append(914) # Text
object_identifier_whitelist.append(1904) # Colored Gradient Slab Middle
object_identifier_whitelist.append(507) # 3DL Top Middle
object_identifier_whitelist.append(93) # Black Inner Corner Square
"""

invalid_object_identifier_frequencies = {}

invalid_objects = []


class ObjectReport:
    def __init__(self, raw_object):
        self.raw_object = raw_object
        self.invalid_reasons = []
        self.location_x = None
        self.location_y = None
        self.location_layer_1 = 0
        self.location_layer_2 = 0
        self.valid = True

    def mark_invalid(self, reason):
        if self.valid:
            self.valid = False
            invalid_objects.append(self)
        self.invalid_reasons.append(reason)


for level_object in level_objects:
    report = ObjectReport(level_object)

    split = level_object.split(",")
    if len(split) % 2 != 0:
        report.mark_invalid("Object cannot be split into pairs of keys and values")
        continue

    for index in range(0, len(split), 2):
        key, value = split[index], split[index + 1]

        if key == "1":
            identifier = int(value)
            if identifier not in object_identifier_whitelist:
                object_name = objects_data.get(value, "Unknown")
                report.mark_invalid(f"Object \"{object_name}\" with identifier of {identifier} isn't allowed")

                if invalid_object_identifier_frequencies.get(object_name, None) is None:
                    invalid_object_identifier_frequencies[object_name] = 0
                invalid_object_identifier_frequencies[object_name] += 1

            continue

        object_property = object_properties.get(key, None)
        if object_property is None:
            continue

        if object_property["name"] == "x":
            report.location_x = float(value)
            continue

        if object_property["name"] == "y":
            report.location_y = float(value)
            continue

        if object_property["name"] == "editor_layer":
            editor_layer_1 = int(value)
            report.location_layer_1 = editor_layer_1
            if editor_layer_1 != 0:
                report.mark_invalid(f"Object has invalid editor layer of {editor_layer_1}")
            continue

        if object_property["name"] == "editor_layer_2":
            editor_layer_2 = int(value)
            report.location_layer_2 = editor_layer_2
            if editor_layer_2 != 0:
                report.mark_invalid(f"Object has invalid editor layer 2 of {editor_layer_2}")
            continue

output_file = open("output.txt", "w")

output_file.write("1.0 Validator Output\n")
output_file.write(f"{len(invalid_objects)} out of {len(level_objects)} objects were found to be invalid.\n\n")

if len(invalid_object_identifier_frequencies) != 0:
    output_file.write("Invalid object identifier frequencies:\n")
    for name, frequency in invalid_object_identifier_frequencies.items():
        output_file.write(f"\t{frequency}x \"{name}\"\n")

output_file.write("\nInvalid objects:\n\n")
for invalid_object in invalid_objects:
    output_file.write(f"{invalid_object.raw_object}\n")
    output_file.write("Location:\n")
    output_file.write(f"\t- Position: ({invalid_object.location_x}, {invalid_object.location_y})\n")
    output_file.write(f"\t- Editor Layer 1: {invalid_object.location_layer_1}\n")
    output_file.write(f"\t- Editor Layer 2: {invalid_object.location_layer_2}\n")
    output_file.write(f"Invalid reasons ({len(invalid_object.invalid_reasons)}):\n")
    for invalid_reason in invalid_object.invalid_reasons:
        output_file.write(f"\t- {invalid_reason}\n")
    output_file.write("\n")

output_file.close()
print("Done! Output written in \"output.txt\"")
