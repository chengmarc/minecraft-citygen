import os, tempfile
os.environ["MC_CITY_DATA_VERSION"] = "3337"  # 1.19.4

import nbtlib
from config.config_world import DATA_VERSION
from engine.schematic_writer import write_sponge_schem_cells
from config import version_compat as vc

print("resolved DATA_VERSION:", DATA_VERSION, "->", vc.release_name_for(DATA_VERSION))

cells = [[["minecraft:short_grass", "minecraft:iron_chain[axis=y]", "minecraft:cherry_planks"]]]
path = os.path.join(tempfile.mkdtemp(), "t.schem")
write_sponge_schem_cells(cells, path, DATA_VERSION)

f = nbtlib.load(path)
schem = f["Schematic"]
print("stamped DataVersion:", int(schem["DataVersion"]))
print("palette:", sorted(str(k) for k in schem["Blocks"]["Palette"].keys()))

# GUI-facing report: renames should be safe, cherry fine, nothing offending at 1.19.4
rep = vc.compatibility_report(
    ["minecraft:short_grass", "minecraft:iron_chain", "minecraft:cherry_planks", "minecraft:stone"],
    vc.data_version_for("1.19.4"),
)
print("report ok:", rep["ok"], "| offending:", [o["block"] for o in rep["offending"]])
print("renamed:", [(r["block"], r["as"]) for r in rep["renamed"]])
print("floor:", rep["floor_release"])
