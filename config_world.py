"""World paths, extraction regions, and schematic version settings."""

# Minecraft world (PrismLauncher save)
SAVE = (r"C:/Users/NewAdmin/AppData/Roaming/PrismLauncher/instances/"
        r"Keo optimized/minecraft/saves/Flat 64 2.0")
REGION_DIR = SAVE + "/dimensions/minecraft/overworld/region"

DATA_VERSION = 4790

# Road assets region in world (x_a, x_b, z_a, z_b, y0, y1)
ROAD_MODERN = (-230, -176, 16, 121, 65, 75)
ROAD_MEDIEVAL = (-294, -240, 16, 121, 65, 75)
ROAD_BOX = ROAD_MEDIEVAL

# Built assets region in world (type, x_a, x_b, z_a, z_b, y0, y1)
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.

BUILD_MEDIEVAL = (1, 0, -366, -266, -140, 64, 65) 
BUILD_MODERN_A = (1, 0, -366, 0, -135, 64, 65)
BUILD_MODERN_B = (1, 0, -234, -267, -383, 64, 65)
BUILD_MODERN_TYPE2 = (2, 0, 300, 0, -300, 64, 65)

BUILD_MARKER_Y_RANGE = (60, 230)
BUILD_TYPES = [BUILD_MEDIEVAL]