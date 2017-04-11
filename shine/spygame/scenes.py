"""
 -------------------------------------------------------------------------
 shine - 
 scene
 
 !!TODO: add file description here!! 
  
 created: 2017/04/06 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import pygame
import spygame.spygame as spyg
import spygame.components as comps


class Scene(object):
    """
    A Scene class that allows a 'scene-func' to be run when the Scene is staged (on one of the Stages of the Game)
    """

    # stores all scenes of the game by name
    scenes_registry = {}

    @staticmethod
    def register_scene(name, scene_or_func, options=None):
        # no scene_func given -> use our default func (taking 'tmx' as a tmx object in options)
        if isinstance(scene_or_func, dict) or (not scene_or_func and not options):
            options = scene_or_func
            scene_or_func = default_scene_func_from_tmx
        # we have to create the scene from the scene_func
        if callable(scene_or_func):
            scene_or_func = Scene(scene_or_func, options)
        Scene.scenes_registry[name] = scene_or_func

    @staticmethod
    def get_scene(name):
        if name not in Scene.scenes_registry:
            return None
        return Scene.scenes_registry[name]

    def __init__(self, scene_func, options=None):
        """

        Args:
            scene_func (callable): the function to be executed when the Scene is staged
            options (None,iterable): the options to pass on to the Stage when staging this Scene
        """
        self.scene_func = scene_func  # will take Stage object as parameter
        self.options = options or {}


class Stage(spyg.GameObject):
    """
    A Stage is a container class for Sprites (GameObjects) divided in groups
    - each group has a name
    - Sprites within a Stage can collide with each other
    """

    max_stages = 10

    # list of all stages
    stages = [None for x in range(max_stages)]
    active_stage = 0

    # the default game loop callback to use if none given when staging a Scene
    # - ticks all stages
    # - then renders all stages
    @staticmethod
    def stage_default_game_loop_callback(game_loop: spyg.GameLoop):
        dt = game_loop.dt
        if dt < 0:
            dt = 1.0 / 60
        if dt > 1 / 15:
            dt = 1.0 / 15

        for i, stage in enumerate(Stage.stages):
            Stage.active_stage = i
            if stage:
                stage.tick(dt)

        # black out display (really necessary?)
        game_loop.rl_world.display.fill(pygame.Color("#000000"))

        # render all Stages
        for i, stage in enumerate(Stage.stages):
            Stage.active_stage = i
            if stage:
                stage.render(game_loop.rl_world.display)
        Stage.active_stage = 0

    @staticmethod
    def clear_stage(idx):
        if Stage.stages[idx]:
            Stage.stages[idx].destroy()
            Stage.stages[idx] = None

    @staticmethod
    def clear_stages():
        for i, stage in enumerate(Stage.stages):
            if Stage.stages[i]:
                Stage.stages[i].destroy()
                Stage.stages[i] = None

    @staticmethod
    def get_stage(idx=None):
        if idx is None:
            idx = Stage.active_stage
        return Stage.stages[idx]

    @staticmethod
    def stage_scene(scene, stage_idx=None, options=None):
        # if it's a string, find a registered scene by that name
        if isinstance(scene, str):
            scene = Scene.get_scene(scene)

        # if the user skipped the num arg and went straight to options, swap the two and grab a default for num
        if isinstance(stage_idx, dict):
            options = stage_idx
            stage_idx = options["stage"] if "stage" in options else (scene.options["stage"] if "stage" in scene.options else 0)

        if options is None:
            options = {}

        ## clone the options arg to prevent modification
        # options = Q._clone(options)

        # grab the stage class, pulling from options, the scene default, or use the default Stage class
        stage_class = options["stage_class"] if "stage_class" in options else (scene.options["stage_class"] if "stage_class" in scene.options else Stage)

        # figure out which stage to use
        stage_idx = stage_idx if stage_idx is not None else (scene.options["stage"] if "stage" in scene.options else 0)

        # clean up an existing stage if necessary
        if Stage.stages[stage_idx]:
            Stage.stages[stage_idx].destroy()

        # make this this the active stage and initialize the stage, calling loadScene to popuplate the stage if we have a scene
        Stage.active_stage = stage_idx
        stage = Stage.stages[stage_idx] = stage_class(scene, options)

        ## load an assets object array
        # if stage.options.asset:
        #   stage.loadAssets()

        if scene:
            stage.load_scene()
        Stage.active_stage = 0

        # if there's no loop active, run the default stageGameLoop
        if "game_loop" not in options or options["game_loop"] == "new":
            spyg.GameLoop.active_loop = spyg.GameLoop(Stage.stage_default_game_loop_callback)
            spyg.GameLoop.active_loop.play()

        # finally return the stage to the user for use if needed
        return stage

    def __init__(self, scene: Scene=None, options=None):
        super().__init__()
        self.groups = {}  # "default": {"group": pygame.sprite.Group(), "render": True, "renderOrder": 0}
        self.game_objects = []  # a plain list of all Sprites in this group
        # self.index = {}  # used for search methods
        self.remove_list = []  # game_objects to be removed from the Stage (only remove when Stage gets ticked)
        self.scene = scene
        self.options = options or {}
        if self.scene:
            spyg.extend(self.options, self.scene.options)

        self.is_paused = False
        self.is_hidden = False

        # make sure our destroyed method is called when the stage is destroyed
        self.on_event("destroyed")

    def destroyed(self):
        self.broadcast("debind_events")
        self.trigger_event("destroyed")

    # executes our Scene by calling the Scene's function with self as only parameter
    def load_scene(self):
        if self.scene:
            self.scene.scene_func(self)

    # TODO: loadAssets?

    # calls the callback function for each sprite, each time passing it the sprite and params
    def for_each(self, callback: callable, params=None):  # quintus: `each`
        if not params:
            params = []
        for game_object in self.game_objects:
            callback(game_object, *params)

    # calls a function on all of the GameObjects on this Stage
    def invoke(self, func_name: str, params=None):
        if not params:
            params = []
        for game_object in self.game_objects:
            if hasattr(game_object, func_name):
                func = getattr(game_object, func_name)
                if callable(func):
                    func(*params)

    # returns the first GameObject in this Stage that - when passed to the detector function with params - returns True
    def detect(self, detector: callable, params=None):
        if not params:
            params = []
        for game_object in self.game_objects:
            if detector(game_object, *params):
                return game_object

    # TODO: def identify(self, ):

    def add_game_object(self, game_object: spyg.GameObject, group: str):
        """
        adds a new sprite to an existing or a new Group
        Args:
            game_object (spyg.GameObject): the GameObject to be added
            group (str): the name of the group to which the GameObject should be added (group will not be created if it doesn't exist yet)

        Returns:

        """
        assert group in self.groups, "ERROR: group '{}' does not exist in Stage!".format(group)
        game_object.stage = self  # set the Stage of this GameObject
        self.groups[group]["group"].add(game_object)
        self.game_objects.append(game_object)
        game_object.trigger_event("added-to-stage")

        # trigger two events, one on the Stage with the object as target and one on the object with the Stage as target
        self.trigger_event("added-to-stage", game_object)
        game_object.trigger_event("added-to-stage", self)

        return game_object

    def add_group(self, group: str, render: bool=True, render_order: int=0):
        assert group not in self.groups, "ERROR: group {} already exists in Stage!".format(group)
        self.groups[group] = {"group": pygame.sprite.Group(), "render": render, "renderOrder": render_order}

    def remove_game_object(self, game_object):
        self.remove_list.append(game_object)

    def force_remove_game_object(self, game_object):
        try:
            idx = self.game_objects.index(game_object)
        except ValueError:
            return
        self.game_objects.pop(idx)

        game_object.destroy()
        self.trigger_event("removed", game_object)

    def pause(self):
        self.is_paused = True

    def unpause(self):
        self.is_paused = False

    def solve_collisions(self, group_sprite_1, group_sprite_2):
        """
        solves collisions between two groups (could also be within the same group) or one group vs a particular sprite (in same or another group)
        Returns:
            all collision objects as a list
        """

        pass

    # gets called each frame by the GameLoop
    # - calls update on all its Sprites (through 'updateSprites')
    def tick(self, dt):
        if self.is_paused:
            return False

        self.trigger_event("pre-tick", dt)
        for game_object in self.game_objects:
            game_object.tick(dt)

        self.trigger_event("tick", dt)

        for game_object in self.remove_list:
            self.force_remove_game_object(game_object)
        self.remove_list.clear()

        self.trigger_event("post-tick", dt)

    def hide(self):
        self.is_hidden = True

    def show(self):
        self.is_hidden = False

    def stop(self):
        self.hide()
        self.pause()

    def start(self):
        self.show()
        self.unpause()

    # gets called each frame by the GameLoop (after 'tick' is called on all Stages)
    # - renders all GameObjects
    def render(self, display: pygame.Surface):
        """
        renders the Stage with all it's renderable objects (GameObjects)
        Returns:

        """
        if self.is_hidden:
            return False
        # if self.options.sort:
        #    this.items.sort(this.options.sort);

        self.trigger_event("pre-render", display)

        for group in self.groups:
            # don't render game_objects with containers (game_objects do that themselves)
            # if (!item.container) {
            group.draw(display)

        self.trigger_event("render", display)
        self.trigger_event("post-render", display)


# helper function for setting up a scene on a stage
# reads a tmx file and creates a scene from it
def default_scene_func_from_tmx(stage: Stage, options=None):

    # mandatory options: tmx (the tmx object) and rl_world (the RLWorld object)
    if not isinstance(options, dict) or "tmx_object" not in options:
        return

    tmx = options["tmx_object"]

    for layer in tmx.layers:
        props = layer.properties
        assert "collision" in props, "ERROR: layer's properties does not have 'collision' field!"

        # add layer as a group to the Stage (so it can hold GameObjects if necessary)
        stage.add_group(layer.name, props["render"] == "true", (int(props["renderOrder"]) if "renderOrder" in props else 0))

        # the main collision layer
        # TODO: try to accumulate tiles so we don't get that many collision objects
        if props["collision"] == "main":
            for x, y, gid in layer.iter_data():
                tile_props = tmx.get_tile_properties_by_gid(gid)
                # a full collision tile
                if tile_props and "collision" in tile_props and tile_props["collision"] == "full":
                    p = spyg.CollisionBlock(x * tmx.tilewidth, y * tmx.tileheight)
                    # platforms.append(p)
                    stage.add_game_object(p, layer.name)

        # background- and foreground-type layers (no collisions)
        elif props["collision"] == "none":
            surf = pygame.Surface((tmx.width * tmx.tilewidth, tmx.height * tmx.tileheight)).convert()
            for x, y, image in layer.tiles():
                surf.blit(image, (x * tmx.tilewidth, y * tmx.tileheight))
            sprite = spyg.GameObject()  # TODO: this should not be a GameObject, but rather a simple Sprite (problem: Stage only accepts GameObjects)
            sprite.image = surf
            sprite.rect = surf.get_rect()
            stage.add_game_object(sprite, layer.name)

        # add all objects from the objects layer
        elif props["collision"] == "objects":
            for obj in layer:
                obj_props = obj.properties
                # TODO: need to change this from player to every object
                # the player
                if "agent" in obj_props and obj_props["agent"] == "true":
                    spritesheet_player = spyg.SpriteSheet("data/" + obj_props["tsx"] + ".tsx")
                    # TODO: move this to somewhere else
                    comps.Animation.register_settings(props["tsx"], {
                        "stand": {"frames": [0], "loop": False, "flags": comps.Animation.ANIM_PROHIBITS_STAND},
                        "beBored1": {"frames": [1], "rate": 1 / 2, "next": 'stand', "flags": comps.Animation.ANIM_PROHIBITS_STAND},
                        "beBored2": {"frames": [61, 2, 3, 4, 3, 4, 3, 4], "rate": 1 / 3, "next": 'stand', "flags": comps.Animation.ANIM_PROHIBITS_STAND},
                        "run": {"frames": [5, 6, 7, 8, 9, 10, 11, 12], "rate": 1 / 8},
                        "outOfBreath": {"frames": [13, 14, 15, 13, 14, 15], "rate": 1 / 4, "next": 'stand', "flags": comps.Animation.ANIM_PROHIBITS_STAND},
                        "push": {"frames": [54, 55, 56, 57], "rate": 1 / 4},
                        "jumpUp": {"frames": [16], "loop": False},
                        "jumpPeak": {"frames": [17], "loop": False},
                        "jumpDown": {"frames": [18, 19], "rate": 1 / 3},
                        "fall": {"frames": [81], "loop": False, "flags": comps.Animation.ANIM_DISABLES_CONTROL,
                                 "keys_status": {"left": -1, "right": -1, "up": -1}},
                        "beDizzy": {"frames": [36, 37, 38, 39, 40, 38, 39, 40, 41, 42, 43], "rate": 1 / 3, "loop": False, "next": 'stand',
                                    "flags": (comps.Animation.ANIM_DISABLES_CONTROL | comps.Animation.ANIM_PROHIBITS_STAND)},
                        "getHurt": {"frames": [72], "rate": 1 / 2, "next": 'stand',
                                    "flags": (comps.Animation.ANIM_DISABLES_CONTROL | comps.Animation.ANIM_PROHIBITS_STAND)},
                        "getSqueezed": {"frames": [126, 127, 128, 128, 129, 129, 129, 129], "rate": 1 / 4, "loop": False, "trigger": 'die',
                                        "flags": (comps.Animation.ANIM_DISABLES_CONTROL | comps.Animation.ANIM_PROHIBITS_STAND)},
                        "sinkInQuicksand": {"frames": [108, 109, 110, 108, 109, 110, 108, 109], "loop": False, "rate": 1 / 2, "trigger": 'die',
                                            "flags": (comps.Animation.ANIM_PROHIBITS_STAND | comps.Animation.ANIM_DISABLES_CONTROL)},
                        "sinkInWater": {"frames": [90, 91, 92, 93, 91, 92, 93], "loop": False, "rate": 1 / 2, "trigger": 'die',
                                        "flags": (comps.Animation.ANIM_PROHIBITS_STAND | comps.Animation.ANIM_DISABLES_CONTROL)},
                        "burn": {"frames": [117, 118, 119, 120, 121, 122, 123, 124], "rate": 1 / 4, "loop": False, "trigger": 'die',
                                 "flags": comps.Animation.ANIM_DISABLES_CONTROL},
                    })
                    player = spyg.Player(obj.x, obj.y, spritesheet_player, obj.width, obj.height)
                    stage.add(player, layer.name)
