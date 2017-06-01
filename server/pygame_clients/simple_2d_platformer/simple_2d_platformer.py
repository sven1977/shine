from pygame import K_UP, K_DOWN
import shine.spygame.spygame as spyg
#import server.pygame_clients.simple_2d_platformer.vikings as vikings
import vikings


debug_flags = (#spyg.DEBUG_RENDER_COLLISION_TILES |
               #spyg.DEBUG_DONT_RENDER_TILED_TILE_LAYERS |
               #spyg.DEBUG_RENDER_SPRITES_RECTS |
               #spyg.DEBUG_RENDER_SPRITES_BEFORE_EACH_TICK |
               #spyg.DEBUG_RENDER_SPRITES_BEFORE_COLLISION_DETECTION |
               #spyg.DEBUG_RENDER_ACTIVE_COLLISION_TILES
               0 #spyg.DEBUG_ALL
               )

# create a GameManager
game_manager = spyg.GameManager([
    # Screen example (a simple start screen with a menu-selector)
    {"class": vikings.VikingScreen,
        "name": "start", "id": 0,
        "keyboard_inputs": spyg.KeyboardInputs([[K_UP, "up"], [K_DOWN, "down"]]),  # only up and down allowed
        "sprites": [],
        "labels": [],
     },
    # Level example
    {"class": vikings.VikingLevel,
        "name": "TEST", "id": 1,  # name is enough -> takes tmx file from 'data/'+[name.lower()]+'.tmx' and has default key-inputs
     },
    ], title="The Lost Vikings - Return of the Heroes", max_fps=60, debug_flags=debug_flags)

# that's it, play one of the levels -> this will enter an endless game loop
game_manager.levels_by_name["TEST"].play()

