"""
 -------------------------------------------------------------------------
 shine - 
 pyg
 
 !!TODO: add file description here!! 
  
 created: 2017/04/04 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

from abc import ABCMeta, abstractmethod
import xml.etree.ElementTree
import pygame
import os.path
from collections import Iterable
from typing import List, Union
import types
import pytmx
import sys
import shine


class EventObject(object):
    """
    Corresponds to evented class in Quintus/html5
    - these are not pygame events!
    """
    def on_event(self, event: Union[str, list[str]], target=None, callback=None):
        """
        Binds a callback to an event on this object. If you provide a
        `target` object, that object will add this event to it's list of
        binds, allowing it to automatically remove it when it is destroyed.

        Args:
            event (str): The event name (e.g. tick, got_hit, etc..)
            target (object): The target object on which to call the callback (defaults to self if not given)
            callback (callable): The (bound!) method to call on target

        Returns:

        """
        # more than one event given
        if isinstance(event, list):
            for i in range(len(event)):
                self.on_event(event[i], target, callback)
            return

        # handle the case where there is no target provided, swapping the target and callback parameters
        if not callback:
            callback = target
            target = None

        # if there's still no callback, default to the event name
        if not callback:
            callback = event

        # handle case for callback that is a string, this will pull the callback from the target object or from this object
        if isinstance(callback, str):
            callback = getattr(target or self, callback)

        # to keep EventObjects from needing a constructor, the `listeners` object is created on the fly as needed
        # - listeners keeps a list of callbacks indexed by event name for quick lookup
        # - a listener is an array of 2 elements: 0=target, 1=callback
        if not hasattr(self, "listeners"):
            self.listeners = {}
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append([target or self, callback])

        # with a provided target, the events bound to the target, so we can erase these events if the target no longer exists
        if target:
            if not hasattr(target, "binds"):
                target.event_binds = []
            target.event_binds.append([self, event, callback])

    def trigger_event(self, event, params=None):
        """
        triggers an event, passing in some optional additional data about the event
        Args:
            event (str): the event's name
            params (any): the params as list or single value to be passed to the handler methods as *args

        Returns:

        """
        # make sure there are any listeners, then check for any listeners on this specific event, if not, early out
        if hasattr(self, "listeners") and event in self.listeners:
            # call each listener in the context of either the target passed into `on_event` ([0]) or the object itself
            for listener in self.listeners[event]:
                # listener expects at least one arg
                if params:
                    params = params if isinstance(params, Iterable) else [params]
                    listener[1](*params)
                # listener expects no args
                else:
                    listener[1]()

    def off_event(self, event, target=None, callback=None):
        """
        unbinds an event
        - can be called with 1, 2, or 3 parameters, each of which unbinds a more specific listener

        Args:
            event ():
            target ():
            callback ():

        Returns:

        """
        # without a target, remove all the listeners
        if not target:
            if hasattr(self, "listeners") and event in self.listeners:
                del self.listeners[event]
        else:
            # if the callback is a string, find a method of the same name on the target
            if isinstance(callback, str) and hasattr(target, callback):
                callback = getattr(target, callback)
            if hasattr(self, "listeners") and event in self.listeners:
                l = self.listeners[event]
                # loop from the end to the beginning, which allows us to remove elements without having to affect the loop
                for i in range(len(l)-1, -1, -1):
                    if l[i][0] is target:
                        if not callback or callback is l[i][1]:
                            l.pop(i)

    def debind_events(self):
        """
        called to remove any listeners from this object
        - e.g. when this object is destroyed you'll want all the event listeners to be removed from this object

        Returns:

        """
        if hasattr(self, "event_binds"):
            for source, event, _ in self.event_binds:
                source.off_event(event, self)


# can handle events as well as
class State(EventObject):
    instantiated = False

    def __init__(self):
        assert not State.instantiated, "ERROR: can only create one State object!"
        super().__init__()
        self.dict = {}
        State.instantiated = True

    # sets a value in our dict and triggers a changed event
    def set(self, key, value):
        # trigger an event that the value changed
        self.trigger_event("changed."+key, value)
        # set to new value
        self.dict[key] = value

    # retrieve a value from the dict
    def get(self, key):
        if key not in self.dict:
            raise(Exception, "ERROR: key {} not in dict!".format(key))
        return self.dict[key]

    # decrease value by amount
    def dec(self, key, amount: int=1):
        self.dict[key] -= amount

    # increase value by amount
    def inc(self, key, amount: int=1):
        self.dict[key] += amount


# initiate the only instance of this class
state = State()


class KeyboardInputs(EventObject):
    def __init__(self, key_list=None):
        # stores the keys that we would like to be registered as important
        # - key: pygame keyboard code (e.g. pygame.K_ESCAPE, pygame.K_UP, etc..)
        # - value: True if currently pressed, False otherwise
        # - needs to be ticked in order to yield up-to-date information
        self.keyboard_registry = None
        self.descriptions = None

        if not key_list:
            key_list = [[pygame.K_UP, "up"], [pygame.K_DOWN, "down"], [pygame.K_LEFT, "left"], [pygame.K_RIGHT, "right"]]
        self.update_keys(key_list)

    def update_keys(self, new_key_list: Union[list[int],None]=None):
        self.keyboard_registry = {}
        self.descriptions = {}
        if new_key_list:
            for key, desc in new_key_list:
                self.keyboard_registry[key] = False
                self.descriptions[key] = desc

    def tick(self):
        """
        pulls all keyboard events from the even queue and processes them according to our keyboard_inputs definition
        """
        events = pygame.event.get([pygame.KEYDOWN, pygame.KEYUP])
        for e in events:
            # a key was pressed that we are interested in -> set to True or False
            if e.key in self.keyboard_registry:
                if e.type == pygame.KEYDOWN:
                    self.keyboard_registry[e.key] = True
                    self.trigger_event("key_down."+self.descriptions[e.key])
                else:
                    self.keyboard_registry[e.key] = False
                    self.trigger_event("key_up."+self.descriptions[e.key])


class GameObject(pygame.sprite.Sprite, EventObject):
    """
    Inherits from Sprite, but also adds capability to add Components
    """

    # dict of GameObject types (by name) to bitmappable-int (1, 2, 4, 8, 16, etc..)
    types = {
        "none"          : 0x0,
        "default"       : 0x1,
        "default_ground": 0x2,
        "default_wall"  : 0x4,
        "particle"      : 0x8,
        "friendly"      : 0x10,
        "enemy"         : 0x20,
        "character"     : 0x40,
        "ui"            : 0x80,
        "all"           : 0x100,
    }
    next_type = 0x200

    # stores all GameObjects by a unique int ID
    id_to_obj = {}
    next_id = 0

    @staticmethod
    def register_type(*types):
        if type not in GameObject.types:
            GameObject.types[type] = GameObject.next_type
            GameObject.next_type *= 2
        return GameObject.types[type]

    @staticmethod
    def get_type(type):
        assert type in GameObject.types, "ERROR in get_type: GameObject type of name '{}' is not registered!".format(type)
        return GameObject.types[type]

    def __init__(self, surf: pygame.Surface, rect: Union[pygame.Rect, None]=None):
        pygame.sprite.Sprite.__init__(self)
        EventObject.__init__(self)

        # assign the image/rect for the Sprite
        self.image = surf
        self.rect = rect if rect else self.image.get_rect()  # if no rect given, use entire image as rect

        # correspond to quintus p.cx and p.cy
        self.center_x = int(self.rect.width / 2)
        self.center_y = int(self.rect.height / 2)

        # GameObject specific stuff
        self.type = 0  # specifies the type of the GameObject (can be used e.g. for collision detection)
        self.handles_own_collisions = False  # set to True if this object takes care of its own collision handling

        self.components = {}  # dict of added components by component's name
        self.is_destroyed = False
        self.stage = None  # the current Stage this GameObject is in
        self.flip = False  # 'x': flip in x direction, 'y': flip in y direction, False: don't flip

        self.id = GameObject.next_id
        GameObject.id_to_obj[self.id] = self
        GameObject.next_id += 1

    def add_component(self, component):
        """
        Adds a component object to this game Entity -> calls the component's added method
        Args:
            component (shine.pyg.components.Component):

        Returns:

        """

        component.game_object = self
        assert component.name not in self.components, "ERROR: component with name {} already exists in Entity!".format(component.name)
        self.components[component.name] = component
        component.added()

    def remove_component(self, component):
        assert component.name in self.components, "ERROR: component with name {} does no exist in Entity!".format(component.name)
        # call the removed handler (if implemented)
        component.removed()
        # only then erase the component from the GameObject
        del self.components[component.name]

    def destroy(self):
        """
        Destroys the object by calling debind and removing the object from it's parent
        - will trigger a destroyed event callback
        Returns:

        """
        # we are already dead -> return
        if self.is_destroyed:
            return

        # tell everyone we are done
        self.trigger_event("destroyed")

        # debind events where we are the target
        self.debind_events()

        # if we are on a stage -> remove us from that stage
        if self.stage and self.stage.remove:
            self.stage.remove(self)

        self.is_destroyed = True

        # remove ourselves from the id_to_obj dict
        del GameObject.id_to_obj[self.id]

        # TODO: remove this -> we should just subscribe to event 'destroyed' if we have a destroyed method
        #if self.destroyed:
        #    self.destroyed()


# a simple block (but not rendered) in the level (collision)
class CollisionBlock(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()
        # no image: collision blocks are not rendered
        # self.image = pygame.Surface((TILE_SIZE, TILE_SIZE)).convert()
        # self.image.fill(pygame.Color("#DDDDDD"))
        self.rect = pygame.Rect(x, y, width, height)

    def update(self):
        pass


class SpriteSheet(object):
    """
    loads a spritesheet from a tsx file and assigns frames to each sprite (Surface) in the sheet
    """

    def __init__(self, file):
        try:
            tree = xml.etree.ElementTree.parse(file)
        except:
            raise("ERROR: could not open xml file: {}".format(file))

        elem = tree.getroot()
        props = elem.attrib
        self.name = props["name"]
        self.tw = int(props["tilewidth"])
        self.th = int(props["tileheight"])
        self.count = int(props["tilecount"])
        self.cols = int(props["columns"])
        self.tiles = []  # the list of all Surfaces
        self.tile_props_by_id = {}

        # assert (tilesets.length == 1, "Not exactly 1 tileset found in tsx file " + tsx + "!");

        for child in elem:
            # the image asset -> load and save all Surfaces
            if child.tag == "image":
                props = child.attrib
                self.w = int(props["width"])
                self.h = int(props["height"])
                image_file = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(file)), os.path.relpath(props["source"])))
                #image_file = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(file)), os.path.relpath("../images/debug.png")))
                image = pygame.image.load(image_file).convert_alpha()
                col = -1
                row = 0
                for tile in range(self.count):
                    col += 1
                    if col >= self.cols:
                        col = 0
                        row += 1
                    surf = pygame.Surface((self.tw, self.th), depth=32)
                    surf.blit(image, (0, 0), area=pygame.Rect(col*self.tw, row*self.th, self.tw, self.th))  # blits the correct frame of the image to this new surface
                    self.tiles.append(surf)

            # single tiles (and their properties)
            elif child.tag == "tile":
                id_ = int(child.attrib["id"])
                self.tile_props_by_id[id_] = {}  # create new dict for this tile
                for tag in child:
                    # the expected properties tag
                    if tag.tag == "properties":
                        for prop in tag:
                            val = prop.attrib["value"]
                            type_ = prop.attrib["type"] if "type" in prop.attrib else None
                            if type_:
                                if type_ == "bool":
                                    val = True if val == "true" else False
                                else:
                                    val = int(val) if type_ == "int" else float(val) if type_ == "float" else val
                            self.tile_props_by_id[id_][prop.attrib["name"]] = val
                    else:
                        raise("ERROR: expected only <properties> tag within <tile> in tsx file {}".format(file))


class GameLoop(object):
    """
    Class that represents the GameLoop
    - has play and pause functions: play stats the tick/callback loop
    - has clock for ticking (keeps track of self.dt each tick), handles max-fps rate
    - handles keyboard input registrations via its KeyboardInputs object
    - needs a callback to know what to do each tick. Does the keyboard_inputs.tick, then calls callback with self as only argument
    """

    # static loop object (the currently active GameLoop gets stored here)
    active_loop = None

    def __init__(self, callback: callable, keyboard_inputs: KeyboardInputs=None, max_fps: float=60.0):
        """

        Args:
            callback (callable): The callback function used for looping
            keyboard_inputs (KeyboardInputs): The leyboard input registry to use
            max_fps (float): the maximum frame rate per second to allow when ticking. fps can be slower, but never faster
        """
        self.is_paused = True  # True -> Game loop will be paused (no frames, no ticks)
        self.callback = callback  # gets called each tick with this GameLoop instance as the first parameter (can then extract dt as `game_loop.dt`)
        self.max_fps = max_fps  # the max fps rate
        self.timer = pygame.time.Clock()  # our tick object
        self.frame = 0  # global frame counter
        self.dt = 0.0  # time since last tick was executed
        # registers those keyboard inputs to capture each tick (up/right/down/left as default if none given)
        # - keyboard inputs can be changed during the loop via self.keyboard_input.update_keys([new key list])
        self.keyboard_inputs = keyboard_inputs or KeyboardInputs(None)

    def pause(self):
        self.is_paused = True

    def play(self, max_fps=None):
        # pause the current loop
        if GameLoop.active_loop:
            GameLoop.active_loop.pause()
        GameLoop.active_loop = self
        self.is_paused = False
        while not self.is_paused:
            self.tick(max_fps)

    def tick(self, max_fps=None):
        if not max_fps:
            max_fps = self.max_fps

        # move the clock and store the dt (since last frame) in sec
        self.dt = self.timer.tick(max_fps) / 1000

        # default global events?
        events = pygame.event.get(pygame.QUIT)  # TODO: add more here?
        for e in events:
            if e.type == pygame.QUIT:
                raise(SystemExit, "QUIT")

        # collect keyboard events
        self.keyboard_inputs.tick()

        # call the callback with self (for references to important game parameters)
        self.callback(self)

        # increase global frame counter
        self.frame += 1


class Scene(object):
    """
    A Scene class that allows a 'scene-func' to be run when the Scene is staged (on one of the Stages of the Game)
    """

    # stores all scenes of the game by name
    scenes_registry = {}

    @staticmethod
    def register_scene(name: str, scene_or_func, options=None):
        # no scene_func given -> use our default func (taking 'tmx' as a tmx object in options)
        if isinstance(scene_or_func, dict) or (not scene_or_func and not options):
            options = scene_or_func
            scene_or_func = Scene.default_scene_func_from_tmx
        # we have to create the scene from the scene_func
        if callable(scene_or_func):
            scene_or_func = Scene(scene_or_func, options)
        Scene.scenes_registry[name] = scene_or_func
        return scene_or_func

    @staticmethod
    def get_scene(name: str):
        if name not in Scene.scenes_registry:
            return None
        return Scene.scenes_registry[name]

    # helper function for setting up a scene on a stage
    # reads a tmx file and creates a scene from it
    @staticmethod
    def default_scene_func_from_tmx(stage: Stage, options=None):

        # mandatory options: tmx (the tmx object)
        if not isinstance(options, dict) or "tmx_obj" not in options:
            return

        tmx = options["tmx_obj"]

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
                        p = CollisionBlock(x * tmx.tilewidth, y * tmx.tileheight, tmx.tilewidth, tmx.tileheight)
                        # platforms.append(p)
                        stage.add_game_object(p, layer.name)

            # background- and foreground-type layers (no collisions)
            elif props["collision"] == "none":
                surf = pygame.Surface((tmx.width * tmx.tilewidth, tmx.height * tmx.tileheight)).convert()
                for x, y, image in layer.tiles():
                    surf.blit(image, (x * tmx.tilewidth, y * tmx.tileheight))
                sprite = GameObject(surf)  # TODO: this should not be a GameObject, but rather a simple Sprite (problem: Stage only accepts GameObjects)
                # sprite.image = surf
                # sprite.rect = surf.get_rect()
                stage.add_game_object(sprite, layer.name)

            # add all objects from the objects layer
            elif props["collision"] == "objects":
                for obj in layer:
                    obj_props = obj.properties
                    if "class" in obj_props:
                        class_ = obj_props["class"]
                        spritesheet = SpriteSheet("data/" + obj_props["tsx"] + ".tsx")
                        class_instance = getattr(sys.modules[__name__], class_)(obj.x, obj.y, spritesheet, obj.width, obj.height)
                        # add animation component to the player
                        class_instance.add_component(Animation("animation"))
                        # class_instance.play_animation("run")  # TODO: remove this

                        stage.add(class_instance, layer.name)

    def __init__(self, scene_func, options=None):
        """

        Args:
            scene_func (callable): the function to be executed when the Scene is staged
            options (None,iterable): the options to pass on to the Stage when staging this Scene
        """
        self.scene_func = scene_func  # will take Stage object as parameter
        self.options = options or {}


class Stage(GameObject):
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
    def stage_default_game_loop_callback(game_loop: GameLoop):
        # determine dt
        if game_loop.dt < 0:
            game_loop.dt = 1.0 / 60
        if game_loop.dt > 1 / 15:
            game_loop.dt = 1.0 / 15

        # tick all Stages
        for i, stage in enumerate(Stage.stages):
            Stage.active_stage = i
            if stage:
                stage.tick(game_loop)

        # black out display (really necessary?)
        # game_loop.rl_world.display.fill(pygame.Color("#000000"))

        # render all Stages
        for i, stage in enumerate(Stage.stages):
            Stage.active_stage = i
            if stage:
                stage.render(game_loop.rl_world.display)  # TODO: where do we get display from?
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

        # - if there's no other loop active, run the default stageGameLoop
        # - or: there is an active loop, but we force overwrite it
        if GameLoop.active_loop is None or "force_loop" in options and options["force_loop"]:
            # try to extract the keyboard registry for the GameLoop from the Screen object
            keyboard_inputs = None
            # set keyboard inputs directly
            if "keyboard_inputs" in options:
                keyboard_inputs = options["keyboard_inputs"]
            # or through the
            elif "screen_obj" in options:
                keyboard_inputs = options["screen_obj"].keyboard_inputs

            # either generate new loop (and play) or play an existing one
            if "game_loop" not in options or options["game_loop"] == "new":
                loop = GameLoop(Stage.stage_default_game_loop_callback, keyboard_inputs=keyboard_inputs)
                loop.play()
            elif isinstance(options["game_loop"], GameLoop):
                options["game_loop"].play()

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
            extend(self.options, self.scene.options)

        self.is_paused = False
        self.is_hidden = False

        # make sure our destroyed method is called when the stage is destroyed
        self.on_event("destroyed")

    def destroyed(self):
        self.invoke("debind_events")
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

    def add_game_object(self, game_object: GameObject, group: str):
        """
        adds a new sprite to an existing or a new Group
        Args:
            game_object (spyg.GameObject): the GameObject to be added
            group (str): the name of the group to which the GameObject should be added (group will not be created if it doesn't exist yet)

        Returns:

        """
        if group not in self.groups:
            self.add_group(group)
        game_object.stage = self  # set the Stage of this GameObject
        self.groups[group]["group"].add(game_object)
        self.game_objects.append(game_object)

        # trigger two events, one on the Stage with the object as target and one on the object with the Stage as target
        self.trigger_event("added_to_stage", game_object)
        game_object.trigger_event("added_to_stage", self)

        return game_object

    def add_group(self, group: str, render: bool=True, render_order: int=0, collision: str="none"):
        assert group not in self.groups, "ERROR: group {} already exists in Stage!".format(group)
        self.groups[group] = {"group": pygame.sprite.Group(), "render": render, "render_order": render_order}

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

        # do the ticking of all objects
        self.trigger_event("pre_ticks", dt)
        for game_object in self.game_objects:
            game_object.tick(dt, GameLoop.active_loop)

        # do the collision resolution
        self.trigger_event("pre_collisions", dt)
        # look for the objects group

        self.solve_collisions()

        for game_object in self.remove_list:
            self.force_remove_game_object(game_object)
        self.remove_list.clear()

        self.trigger_event("post_tick", dt)

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


class Component(EventObject, metaclass=ABCMeta):
    def __init__(self, name):
        self.name = name
        self.game_object = None  # to be set by Entity when this component gets added

    # gets called when the component is added to an entity
    @abstractmethod
    def added(self):
        pass

    # gets called when the component is removed from an entity
    def removed(self):
        pass

    # extends the given method (has to take self as 1st param) onto the GameObject, so that this method can be called
    # directly from the GameObject
    def extend(self, method: callable):
        # use the MethodType function to bind the play_animation function to only this object (not any other instances of the GameObject's class)
        setattr(self, method.__name__, types.MethodType(method, self))


# TODO: this is actually the hook into the RL/DL world
class Brain(Component):
    """
    a brain class that handles agent control (via RL and/or keyboard)
    - sets self.commands each tick depending on leyboard input and/or RL algorithm
    """
    def __init__(self, name: str, commands: Union[list,None]):
        super().__init__(name)
        if not commands:
            commands = []
        self.commands = {key: False for key in commands}

    def added(self):
        # call our own step method when event "tick" is triggered on our GameObject
        self.game_object.on_event("pre_tick", self, self.tick)

    # TODO: needs to translate the key input from the gameloop into commands
    # TODO: needs to do RL with algorithm classes
    def tick(self, game_loop):
        pass


class Animation(Component):

    # static animation-properties registry
    # - stores single animation records (these are NOT Animation objects, but simple dicts representing settings for single animation sequences)
    animation_settings = {}

    # some flags
    ANIM_NONE = 0x0
    ANIM_SWING_SWORD = 0x1
    ANIM_DISABLES_CONTROL = 0x2
    ANIM_PROHIBITS_STAND = 0x4  # anims that should never be overwritten by 'stand'(even though player might not x - move)
    ANIM_BOW = 0x8

    @staticmethod
    def register_settings(spritesheet_name, anim_settings):
        for anim in anim_settings:
            defaults(anim_settings[anim], {
                "rate": 1/3,  # the rate with which to play this animation in 1/s
                "frames": [0, 1],  # the frames to play from our spritesheet (starts with 0)
                "priority": -1,  # which priority to use for next if next is given
                "flags": Animation.ANIM_NONE,  # flags bitmap that determines the behavior of the animation (e.g. block controls during animation play, etc..)
                "loop": True,  # whether to loop the animation when done
                "next": None,  # which animation to play next
                "next_priority": -1,  # which priority to use for next if next is given
                "trigger": None,  # which events to trigger on the game_object that plays this animation
                "trigger_data": None,  # data to pass to the event handler if trigger is given
                "keys_status": {},  # ??? can override DISABLE_MOVEMENT setting only for certain keys
            })
        Animation.animation_settings[spritesheet_name] = anim_settings

    @staticmethod
    def get_settings(spritesheet_name, anim_setting):
        if spritesheet_name not in Animation.animation_settings or anim_setting not in Animation.animation_settings[spritesheet_name]:
            return None
        return Animation.animation_settings[spritesheet_name][anim_setting]

    def __init__(self, name: str):
        super().__init__(name)
        self.animation = None  # str: if set to something, we are playing this animation
        self.rate = 1/3  # in s
        self.has_changed = False
        self.priority = -1  # animation priority (takes the value of the highest priority animation that wants to be played simultaneously)
        self.frame = 0  # the current frame in the animation 'frames' list
        self.time = 0  # the current time after starting the animation in s
        self.flags = 0
        self.keys_status = {}
        self.blink_rate = 3.0
        self.blink_duration = 0
        self.blink_time = 0

    # implement added
    def added(self):
        # call our own step method when event "tick" is triggered on our GameObject
        self.game_object.on_event("pre_tick", self, self.tick)

        # do the extensions of the GameObject
        # ----
        # TODO: do this with the extend method of the Component class
        # play an animation
        def play_animation(self2, name, priority=0):
            # if (Q.debug & Q._DEBUG_LOG_ANIMATIONS) console.log("playing: " + this.p.name + "." + name + (priority ? " (" + priority + ")": ""));
            self2.components[self.name].play(name, priority)
        # use the MethodType function to bind the play_animation function to only this object (not any other instances of the GameObject's class)
        self.game_object.play_animation = types.MethodType(play_animation, self.game_object)

        def blink_animation(self2, rate, duration):
            self2.components[self.name].blink(rate, duration)
        self.game_object.blink_animation = types.MethodType(blink_animation, self.game_object)

    # gets called when the GameObject triggers a "tick" event
    def tick(self, game_loop):
        # blink stuff?
        if self.blink_duration > 0:
            self.blink_time += game_loop.dt
            # blinking stops
            if self.blink_time >= self.blink_duration:
                self.blink_duration = 0
                self.hidden = False  # make GameObj visible
            else:
                frame = int(self.blink_time * self.blink_rate)
                self.hidden = True if frame % 2 else False

        # animation stuff?
        if self.animation:
            anim_settings = Animation.get_settings(self.game_object.spritesheet.name, self.animation)
            rate = anim_settings["rate"] or self.rate
            stepped = 0
            self.time += game_loop.dt
            if self.has_changed:
                self.has_changed = False
            else:
                self.time += game_loop.dt
                if self.time > rate:
                    stepped = int(self.time // rate)
                    self.time -= stepped * rate
                    self.frame += stepped
            if stepped > 0:
                if self.frame >= len(anim_settings["frames"]):
                    if anim_settings["loop"] is False or anim_settings["next"]:
                        self.frame = len(anim_settings["frames"]) - 1
                        self.game_object.trigger_event("animEnd")
                        self.game_object.trigger_event("animEnd."+self.animation)
                        self.priority = -1
                        if anim_settings["trigger"]:
                            self.game_object.trigger_event(anim_settings["trigger"], anim_settings["trigger_data"])
                        if anim_settings["next"]:
                            self.play(anim_settings["next"], anim_settings["next_priority"])
                        return
                    else:
                        self.game_object.trigger_event("animLoop")
                        self.game_object.trigger_event("animLoop." + self.animation)
                        self.frame %= len(anim_settings["frames"])

                self.game_object.trigger_event("animFrame")

            self.game_object.image = self.game_object.spritesheet.tiles[anim_settings["frames"][self.frame]]

    def play(self, name, priority=0):
        # p = self.get_p()
        if name != self.animation and priority >= self.priority:
            self.animation = name
            self.has_changed = True
            self.time = 0
            self.frame = 0  # start each animation from 0
            self.priority = priority

            # look up animation in list
            anim_settings = Animation.get_settings(self.game_object.spritesheet.name, self.animation)
            # console.assert (anim, "anim: "+p.animation+" of "+entity.p.name+" not found!");
            # set flags to sprite's properties
            self.flags = anim_settings["flags"]
            self.keys_status = anim_settings["keys_status"]

            self.game_object.trigger_event("anim")
            self.game_object.trigger_event("anim." + self.animation)

    def blink(self, rate=3.0, duration=3.0):
        """

        Args:
            self ():
            rate (float): in 1/s
            duration (float): in s

        Returns:

        """
        # p = self.get_p()
        self.blink_rate = rate
        self.blink_duration = duration
        self.blink_time = 0


class VikingPhysics(Component):
    """
    defines "The Lost Vikings"-like game physics
    - to be addable to any character (player or enemy)
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.vx = 0  # velocities
        self.vy = 0

        # physics
        # self.collision_mask = Q._SPRITE_DEFAULT | Q._SPRITE_LADDER | Q._SPRITE_PARTICLE
        self.run_acceleration = 300  # running acceleration
        self.vx_max = 150  # max run-speed
        self.max_fall_speed = 400  # maximum fall speed
        self.gravity = True  # set to False to make this guy not be subject to y-gravity (e.g. while locked into ladder)
        self.gravity_y = 9.8 * 100
        self.jump_speed = 330  # jump-power
        self.disable_jump = False  # if True: disable jumping so we don't keep jumping when action1 key keeps being pressed
        self.can_jump = True  # set to False to make this guy not be able to jump
        self.stops_abruptly_on_direction_change = True  # Vikings stop abruptly when running in one direction, then the other direction is pressed
        self.climb_speed = 70  # speed at which player can climb
        self.is_pushable = False  # set to True if a collision with the entity causes the entity to move a little
        self.is_heavy = False  # set to true if this object should squeeze other objects that are below it and cannot move away
        self.squeeze_speed = 0  # set to a value > 0 to define the squeezeSpeed at which this object gets squeezed by heavy objects
                                # (objects with is_heavy == True)

        # environment stuff
        self.x_min = 0  # the minimum/maximum allowed positions
        self.y_min = 0
        self.x_max = 9000
        self.y_max = 9000

        self.touching = 0  # bitmap with those bits set that the entity is currently touching (colliding with)
        self.on_ground = [0, 0]  # 0=current state; 1=previous state (sometimes we need the previous state since the
                                 # current state gets reset to 0 every step)
        self.docked_objects = {}  # dictionary that holds all objects (key=GameObject's id) currently docked to this one

        self.at_exit = False
        self.at_wall = False
        self.on_slope = 0  # 1 if on up-slope, -1 if on down-slope
        self.on_ladder = 0  # 0 if GameObject is not locked into a ladder; y-pos of obj, if obj is currently locked into a ladder (in climbing position)
        self.which_ladder = None  # holds the ladder Sprite, if player is currently touching a ladder sprite, otherwise: 0
        self.climb_frame_value = 0  # int([climb_frame_value]) determines the frame to use to display climbing position

        # self.collision_options = {
        #        "collision_mask": Q._SPRITE_LADDER,
        #        "max_col": 2,
        #        "skip_events": False,
        #        "skip_reciprocal_events": True
        #        }

    def added(self):
        obj = self.game_object
        self.x_min += obj.cx
        self.y_min += obj.cy
        self.x_max -= obj.cx
        self.y_max -= obj.cy

        obj.on_event("pre_tick", self, "tick")  # run this component's step function before GameObject's one
        obj.on_event("hit", self, "collision")  # handle collisions

        self.extend(self.move)

    def move(self, x: int, y: int, precheck: bool=False):
        """
        moves the entity by given x/y positions
        - if precheck is set to True: pre-checks the planned move via call to stage.locate and only moves entity as far as possible
        - returns the actual movement
        """

        """if (precheck) {
            var testcol = this.stage.locate(p.x+x, p.y+y, Q._SPRITE_DEFAULT, p.w, p.h);
            if ((!testcol) || (testcol.tileprops && testcol.tileprops['liquid'])) {
                return true;
            }
            return false;
        }"""

        obj = self.game_object
        obj.rect.x += x
        obj.rect.y += y

        # TODO: move the following into collide of stage (stage knows its borders best, then we don't need to define xmax/xmin, etc.. anymore)
        # maybe we could even build a default collision-frame around every stage when inserting the collision layer
        if obj.rect.x < self.x_min:
            obj.rect.x = self.x_min
            self.vx = 0
        elif obj.rect.x > self.x_max:
            obj.rect.x = self.x_max
            self.vx = 0
        if obj.rect.y < self.y_min:
            obj.rect.y = self.y_min
            self.vy = 0
        elif obj.rect.y > self.y_max:
            obj.rect.y = self.y_max
            self.vy = 0

        if self.docked_objects:  # TODO: where does this come from ??
            for docked_obj in self.docked_objects:
                if hasattr(docked_obj, "move"):
                    docked_obj.move(x, y)

    # locks the GameObject into a ladder
    def lock_ladder(self):
        obj = self.game_object
        self.on_ladder = obj.rect.y
        self.gravity = False
        # move obj to center of ladder
        obj.rect.x = self.which_ladder.rect.x
        self.vx = 0  # stop x-movement

    # frees the GameObject from a ladder
    def unlock_ladder(self):
        self.on_ladder = 0
        self.gravity = True

    # a sprite lands on an elevator -> couple the elevator to the sprite so that when the elevator moves, the sprite moves along with it
    def dock_to(self, mother_ship: spyg.GameObject):
        obj = self.game_object
        if mother_ship.type & spyg.GameObject.get_type("default"):
            obj.on_ground[0] = mother_ship
            if mother_ship.docked_objects:
                mother_ship.docked_objects[self.id] = self

    # undocks itself from the mothership
    def undock(self):
        mother_ship = self.on_ground[0]
        self.on_ground[0] = 0
        # remove docked obj from mothership docked-obj-list
        if mother_ship and mother_ship.docked_objects:
            del mother_ship.docked_objects[self.id]

    # determines x/y-speeds and moves the GameObject
    def tick(self, game_loop: scenes.GameLoop):
        dt = game_loop.dt
        dt_step = dt
        ax = 0
        obj = self.game_object
        stage = obj.stage

        # entity has a brain component
        if "brain" in obj.components and isinstance(obj.components["brain"], Brain):
            brain = obj.components["brain"]

            # determine x speed
            # -----------------
            # user is trying to move left or right (or both?)
            if brain.commands["left"]:
                # only left is pressed
                if not brain.commands["right"]:
                    if self.stops_abruptly_on_direction_change and self.vx > 0:
                        self.vx = 0  # stop first if still walking in other direction
                    ax = -(self.run_acceleration or 999000000000)  # accelerate left
                    obj.flip = "x"  # mirror sprite

                    # user is pressing left or right -> leave on_ladder state
                    if self.on_ladder > 0:
                        self.unlock_ladder()
                # user presses both keys (left and right) -> just stop
                else:
                    self.vx = 0

            # only right is pressed
            elif brain.commands["right"]:
                if self.stops_abruptly_on_direction_change and self.vx < 0:
                    self.vx = 0  # stop first if still walking in other direction
                ax = self.run_acceleration or 999000000000  # accelerate right
                obj.flip = False

                # user is pressing left or right -> leave on_ladder state
                if self.on_ladder > 0:
                    self.unlock_ladder()
            # stop immediately (vx=0; don't accelerate negatively)
            else:
                # ax = 0; // already initalized to 0
                self.vx = 0

            # determine y speed
            # -----------------
            if self.on_ladder > 0:
                self.vy = 0
            # user is pressing 'up' (ladder?)
            if brain.commands["up"]:
                # obj is currently on ladder
                if self.on_ladder > 0:
                    # reached the top of the ladder -> lock out of ladder
                    if obj.rect.y <= self.which_ladder.ytop - obj.rect.height/2:
                        self.unlock_ladder()
                    else:
                        self.vy = -self.climb_speed
                # player locks into ladderi
                elif (self.which_ladder and obj.rect.y <= self.which_ladder.rect.top - obj.rect.height/2 and
                    obj.rect.y > self.which_ladder.rect.bottom - obj.rect.height/2):
                    self.lock_ladder()
            # user is pressing only 'down' (ladder?)
            elif brain.commands["down"]:
                if self.on_ladder > 0:
                    # we reached the bottom of the ladder -> lock out of ladder
                    if obj.rect.y >= self.which_ladder.rect.bottom - obj.rect.height/2:
                        self.unlock_ladder()
                    # move down
                    else:
                        self.vy = self.climb_speed
                elif self.which_ladder and obj.rect.y < self.which_ladder.rect.bottom - obj.rect.height/2 and self.on_ground[0]:
                    self.lock_ladder()
            # jumping?
            elif self.can_jump:
                if "action1" not in brain.commands:
                    self.disable_jump = False
                elif brain.commands["action1"]:
                    if (self.on_ladder > 0 or self.on_ground[0]) and not self.disable_jump:
                        if self.on_ladder > 0:
                            self.unlock_ladder()
                        self.vy = -self.jump_speed
                        self.undock()
                    self.disable_jump = True
        # entity has no steering unit (x-speed = 0)
        else:
            self.vx = 0


        # TODO: check the entity's magnitude of vx and vy,
        # reduce the max dt_step if necessary to prevent skipping through objects.
        while dt_step > 0:
            dt = min(1/30, dt_step)

            # update x/y-velocity based on acceleration
            self.vx += ax * dt  # TODO: x-gravity? + self.(p.gravityX == void 0 ? Q.gravityX : p.gravityX) * dt * p.gravity;
            if abs(self.vx) > self.vx_max:
                self.vx = -self.vx_max if self.vx < 0 else self.vx_max
            if self.gravity:
                self.vy += self.gravity_y * dt

            # if player stands on up-slope and x-speed is negative (or down-slope and x-speed is positive)
            # -> make y-speed as high as x-speed so we don't fly off the slope
            if self.on_slope != 0 and self.on_ground[0]:
                if self.on_slope == 1 and self.vy < -self.vx:
                    self.vy = -self.vx
                elif self.on_slope == -1 and self.vy < self.vx:
                    self.vy = self.vx
            if abs(self.vy) > self.max_fall_speed:
                self.vy = -self.max_fall_speed if self.vy < 0 else self.max_fall_speed

            # update x/y-positions before checking for collisions at these new positions
            obj.move(self.vx * dt, self.vy * dt)

            ## log movements and collisions?
            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("check cols for "+p.name+": x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);
            # render game_objects often?
            #if (Q.debug & Q._DEBUG_RENDER_OFTEN)
            #	renderAllForDebug(Q, this.entity);

            # reset all touch flags before doing all the collision analysis
            self.on_slope = 0
            if self.on_ladder == 0:
                self.which_ladder = None
            self.at_wall = False
            self.at_exit = False
            self.on_ground[1] = self.on_ground[0]  # store "old" value before undocking
            self.undock()

            # check for collisions on this entity's stage AND return in options-hash whether we have a ladder collision amongst the set of collisions
            #opts = self.collision_options
            # check for collisions with ladders first (before collision layer!)
            #opts.collision_mask = spyg.GameObject.get_type("ladder")
            if "ladders" in stage.groups:
                stage.solve_collisions(obj, stage.groups["ladders"])
            # then check for collisions layer, enemies and everything else
            #opts.collisionMask = (p.collisionMask ^ Q._SPRITE_LADDER);
            stage.solve_collisions(obj, obj.type ^ spyg.GameObject.get_type("ladder"))

            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("checked cols");

            # render game_objects often?
            #if (Q.debug & Q._DEBUG_RENDER_OFTEN) renderAllForDebug(Q, this.entity);

            dt_step -= dt

    def collision(self, col, last):
        obj = self.game_object
        assert hasattr(col, "game_object"), "ERROR: no game_object in col-object!"
        other_obj = col.game_object

        #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
        #	console.log("\tcol ("+p.name+" hit "+objp.name+"): onSlope="+p.onSlope+" x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);

        # getting hit by a particle (arrow, scorpionshot, fireball, etc..)
        if other_obj.type & spyg.GameObject.get_type("particle"):
            # shooter (this) is colliding with own shot -> ignore
            if obj is not other_obj.shooter:
                obj.trigger_event("hit_particle", col)
                other_obj.trigger_event("hit", obj)  # for particles, force the reciprocal collisions (otherwise, the character that got shot could be gone (dead) before any collisions on the particle could get triggered (-> e.g. arrow will fly through a dying enemy without ever actually touching the enemy))
            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("\t\tparticle: x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);
            return

        # colliding with a ladder
        if other_obj.type & spyg.GameObject.get_type("ladder"):
            # set whichLadder to the ladder's props
            self.which_ladder = other_obj
            # if we are not locked into ladder AND on very top of the ladder, collide normally (don't fall through ladder's top)
            if (self.on_ladder > 0 or col.normal_x != 0  # don't x-collide with ladder
                or col.normal_y > 0  # don't collide with bottom of ladder
                ):
                return

        # ----------------------------
        # collision layer:
        # ----------------------------
        tileprops = col.tileprops
        # quicksand or water
        if "liquid" in tileprops and tileprops["liquid"]:
            obj.trigger_event("hit_liquid_ground", tileprops["liquid"])
            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("\t\tliquid ground: x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);
            return

        # colliding with an exit
        elif "exit" in tileprops and tileprops["exit"]:
            self.at_exit = True
            obj.stage.options.level.trigger_event("reached_exit", obj)  # let the level know
            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("\t\texit: x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);
            return

        # check for slopes
        elif col.slope != 0 and self.on_ground[1]:
            abs_slope = abs(col.slope)
            offset = int(tileprops["offset"])
            # set p.y according to position of sprite within slope square
            y_tile = (col.tile_y+1) * other_obj.tile_h  # bottom y-pos of tile
            # subtract from bottom-y for different inclines and different stages within the incline
            dy_wanted = (y_tile - (other_obj.tile_h*(offset-1)/abs_slope) - obj.rect.centery - (col.xin / abs_slope)) - obj.rect.y
            # p.y = y_tile - (col.obj.p.tileH*(offset-1)/abs_slope) - p.cy - (col.xin / abs_slope);
            # can we move there?
            #var dy_actual =
            obj.move(0, dy_wanted, True)  # TODO: check top whether we can move there (there could be a block)!!)) {
            #if (dy_actual < dy_wanted) {
            #	// if not -> move back in x-direction
            #	//TODO: calc xmoveback value
            #}
            self.vy = 0
            self.dock_to(other_obj)  # dock to collision layer
            self.on_slope = col.sl

            #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
            #	console.log("\t\tslope: x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);
            return

        # normal collision
        col.impact = 0

        impact_x = abs(self.vx)
        impact_y = abs(self.vy)

        # move away from the collision (back to where we were before)
        x_orig = obj.rect.x
        y_orig = obj.rect.y
        obj.rect.x -= col.separate[0]
        obj.rect.y -= col.separate[1]

        # bottom collision
        if col.normalY < -0.3:
            # a heavy object hit the ground -> rock the stage
            if (self.is_heavy and not self.on_ground[1]  # 1=check old value, the new one was reset to 0 before calling 'collide'
                and other_obj.type & spyg.GameObject.get_type("default")):
                obj.stage.shake()

            # squeezing something
            if self.is_heavy and other_obj.squeeze_speed > 0 and other_obj.on_ground[0] and self.vy > 0:
                # adjust the collision separation to the new squeezeSpeed
                if self.vy > other_obj.squeeze_speed:
                    self.y = y_orig + col.separate[1]*(other_obj.squeeze_speed / self.vy)
                # otherwise, just undo the separation
                else:
                    self.rect.y += col.separate[1]

                self.vy = other_obj.squeeze_speed
                other_obj.trigger_event("squeezed.top", obj)

            # normal bottom collision
            else:
                if self.vy > 0:
                    self.vy = 0
                col.impact = impact_y
                self.dock_on(other_obj)  # dock to bottom object (collision layer or MovableRock, etc..)
                obj.trigger_event("bump.bottom", col)

        # top collision
        if col.normalY > 0.3:
            if self.vy < 0:
                self.vy = 0
            col.impact = impact_y
            obj.trigger_event("bump.top", col)

        # left/right collisions
        if abs(col.normalX) > 0.3:
            col.impact = impact_x
            bump_wall = False
            # we hit a pushable object -> check if it can move
            if other_obj.is_pushable and self.on_ground[1]: # 1=check old value, new one has been set to 0 before calling 'collide'
                self.push_an_object(obj, col)
                bump_wall = True
            # we hit a fixed wall (non-pushable)
            elif self.vx * col.normalX < 0:  # if normalX < 0 -> p.vx is > 0 -> set to 0; if normalX > 0 -> p.vx is < 0 -> set to 0
                self.vx = 0
                bump_wall = True

            if bump_wall:
                if other_obj.type & sypg.GameObject.get_type("default"):
                    self.at_wall = True
                obj.trigger_event("bump."+("right" if col.normalX < 0 else "left"), col)

        #if (Q.debug & Q._DEBUG_LOG_COLLISIONS && ((!Q._DEBUG_LOG_COLLISIONS_AS) || Q._DEBUG_LOG_COLLISIONS_AS == p.name))
        #	console.log("\t\tnormal col: x="+p.x+" y="+p.y+" vx="+p.vx+" vy="+p.vy);

    def push_an_object(self, pusher, col):
        pushee = col.obj
        # TODO: what if normalX is 1/-1 BUT: impactX is 0 (yes, this can happen!!)
        # for now: don't push, then
        if col.impact > 0:
            move_x = col.separate[0] * abs(pushee.vx_max / col.impact)
            #console.log("pushing Object: move_x="+move_x);
            # do a locate on the other side of the - already moved - pushable object
            #var testcol = pusher.stage.locate(pushee_p.x+move_x+(pushee_p.cx+1)*(p.flip == 'x' ? -1 : 1), pushee_p.y, (Q._SPRITE_DEFAULT | Q._SPRITE_FRIENDLY | Q._SPRITE_ENEMY));
            #if (testcol && (! (testcol.tileprops && testcol.tileprops.slope))) {
            #	p.vx = 0; // don't move player, don't move pushable object
            #}
            #else {
            # move obj (plus all its docked objects) and move pusher along
            pusher.move(move_x, 0)
            pushee.move(move_x, 0)
            self.vx = pushee.vx_max * (-1 if self.flip == 'x' else 1)
        else:
            self.vx = 0


# TODO: Viewport
class Viewport(Component):
    def __init__(self, display: pygame.Surface):
        self.x = 0
        self.y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.shake_x = 0
        self.shake_y = 0
        self.display = display
        self.center_x = display.get_rect().width / 2
        self.center_y = display.get_rect().height / 2
        self.scale = 1.0

    def added(self):
        self.game_object.on_event("pre_render", self, "pre_render")
        self.game_object.on_event("render", self, "post_render")
        self.__init__(self.display)

"""
    extend: {
      follow: function(sprite,directions,boundingBox,followMaxSpeed) {
        this.off('poststep',this.viewport,'follow');
        this.viewport.directions = directions || { x: true, y: true };
        this.viewport.following = sprite;
        this.viewport.boundingBox = boundingBox;
        this.viewport.followMaxSpeed = (followMaxSpeed || Infinity);
        this.on('poststep',this.viewport,'follow');
        this.viewport.follow((followMaxSpeed ? false : true));
      },

      unfollow: function() {
        this.off('poststep',this.viewport,'follow');
      },

      centerOn: function(x,y) {
        this.viewport.centerOn(x,y);
      },

      moveTo: function(x,y) {
        return this.viewport.moveTo(x,y);
      },

      shake: function() {
        setTimeout(function(vp) {vp.shakeY = 1;}, 30, this.viewport);
        setTimeout(function(vp) {vp.shakeY = -1;}, 60, this.viewport);
        setTimeout(function(vp) {vp.shakeY = 1;}, 90, this.viewport);
        setTimeout(function(vp) {vp.shakeY = -1;}, 120, this.viewport);
        setTimeout(function(vp) {vp.shakeY = 1;}, 150, this.viewport);
        setTimeout(function(vp) {vp.shakeY = -1;}, 180, this.viewport);
        setTimeout(function(vp) {vp.shakeY = 1;}, 210, this.viewport);
        setTimeout(function(vp) {vp.shakeY = 0;}, 240, this.viewport);
      },
    },

    follow: function(first) {
      var followX = Q._isFunction(this.directions.x) ? this.directions.x(this.following) : this.directions.x;
      var followY = Q._isFunction(this.directions.y) ? this.directions.y(this.following) : this.directions.y;

      this[first === true ? 'centerOn' : 'softCenterOn'](
                    followX ?
                      this.following.p.x + this.following.p.w/2 - this.offsetX :
                      undefined,
                    followY ?
                     this.following.p.y + this.following.p.h/2 - this.offsetY :
                     undefined
                  );
    },

    offset: function(x,y) {
      this.offsetX = x;
      this.offsetY = y;
    },

    softCenterOn: function(x,y) {
      if(x !== void 0) {
        var dx = (x - Q.width / 2 / this.scale - this.x)/3;//, this.followMaxSpeed);
        if (Math.abs(dx) > this.followMaxSpeed)
          dx = this.followMaxSpeed * (dx < 0 ? -1 : 1);
        if(this.boundingBox) {
          if(this.x + dx < this.boundingBox.minX) {
            this.x = this.boundingBox.minX / this.scale;
          }
          else if(this.x + dx > (this.boundingBox.maxX - Q.width) / this.scale) {
            this.x = (this.boundingBox.maxX - Q.width) / this.scale;
          }
          else {
            this.x += dx;
          }
        }
        else {
          this.x += dx;
        }
      }
      if(y !== void 0) {
        var dy = (y - Q.height / 2 / this.scale - this.y)/3;
        if (Math.abs(dy) > this.followMaxSpeed)
          dy = this.followMaxSpeed * (dy < 0 ? -1 : 1);
        if(this.boundingBox) {
          if(this.y + dy < this.boundingBox.minY) {
            this.y = this.boundingBox.minY / this.scale;
          }
          else if(this.y + dy > (this.boundingBox.maxY - Q.height) / this.scale) {
            this.y = (this.boundingBox.maxY - Q.height) / this.scale;
          }
          else {
            this.y += dy;
          }
        }
        else {
          this.y += dy;
        }
      }
    },
    centerOn: function(x,y) {
      if(x !== void 0) {
        this.x = x - Q.width / 2 / this.scale;
      }
      if(y !== void 0) {
        this.y = y - Q.height / 2 / this.scale;
      }

    },

    moveTo: function(x,y) {
      if(x !== void 0) {
        this.x = x;
      }
      if(y !== void 0) {
        this.y = y;
      }
      return this.entity;

    },

    prerender: function() {
      this.centerX = this.shakeX + this.x + Q.width / 2 /this.scale;
      this.centerY = this.shakeY + this.y + Q.height / 2 /this.scale;
      Q.ctx.save();
      Q.ctx.translate(Math.floor(Q.width/2),Math.floor(Q.height/2));
      Q.ctx.scale(this.scale,this.scale);
      Q.ctx.translate(-Math.floor(this.centerX), -Math.floor(this.centerY));
    },

    postrender: function() {
      Q.ctx.restore();
    }
  });
"""


class Screen(EventObject, metaclass=ABCMeta):
    """
    a screen object has a play and a done method that need to be implemented
    - the play method stages a scene
    - the done method can do some cleanup
    """

    def __init__(self, name: str="start", **kwargs):
        self.name = name
        self.id = kwargs["id"] if "id" in kwargs else 0

        # handle keyboard inputs
        self.keyboard_inputs = kwargs["keyboard_inputs"] if "keyboard_inputs" in kwargs else KeyboardInputs()

    @abstractmethod
    def play(self):
        pass

    @abstractmethod
    def done(self):
        pass


class Level(Screen, metaclass=ABCMeta):
    """
    a level class
    - adds tmx file support to the Screen
    - we can get lots of information from the tmx file to build the level in the play method
    """
    def __init__(self, name: str="test", **kwargs):
        self.tmx_file = kwargs["tmx_file"] if "tmx_file" in kwargs else self.name.lower()+".tmx"
        # load in the world's tmx file
        self.tmx_obj = pytmx.load_pygame(self.tmx_file)
        self.width = self.tmx_obj.width * self.tmx_obj.tilewidth
        self.height = self.tmx_obj.height * self.tmx_obj.tileheight

        super().__init__(name, **kwargs)


"""
// -------------------------------------
// A Game Manager Object
// - manages displaying the level and
//   other screens (start screen, etc..)
// -------------------------------------
Q.Evented.extend("GameManager", {
	init: function(p) {
		Q._defaults(p, {
			screensToLoad: ["start"],
			screens: {},
			levelsToLoad: ["STRT"], // list of level names to generate
			levels: {}, // holds the level objects by key=level name
		});
		this.p = p;

		// initialize all screens
		for (var x = 0, l = p.screensToLoad.length; x < l; ++x) {
			var opts = (Q._isString(p.screensToLoad[x]) ? { name: p.screensToLoad[x] } : p.screensToLoad[x]);
			opts.name = (opts.name || "screen"+(x < 10 ? "0"+x : x));
			opts.gameManager = this;
			var screen = p.screens[opts.name] = new Q.Screen(opts);
			//console.log("loading screen "+screen.p.name+"("+(screen.p.name == "start")+")");
			screen.load(screen.p.name == "start"); // load the first screen (its assets) and play it when done
		}
		// initialize all levels
		for (var x = 0, l = p.levelsToLoad.length; x < l; ++x) {
			var opts = (Q._isString(p.levelsToLoad[x]) ? { name: p.levelsToLoad[x] } : p.levelsToLoad[x]);
			opts.name = (opts.name || "LV"+(x < 10 ? "0"+x : x));
			opts.id = x;
			opts.gameManager = this;
			var level = p.levels[opts.name] = new Q.Level(opts);
			// register events
			level.on("ready", this, "levelReady");
			level.on("mastered", this, "levelMastered");
			level.on("aborted", this, "levelAborted");
			level.on("lost", this, "levelLost");
			if (x == 0) level.load(false); // load the first level (its assets)
		}
	},

	// returns the next level (if exists) as object
	// false if no next level
	getNextLevel: function(level) {
		return (this.p.levels[this.p.levelsToLoad[(Q._isNumber(level) ? level : level.p.id)+1]] || false);
	},

	// a level is ready (assets have been loaded)
	// -> if 1st level is ready: load 2nd level, but don't play it
	levelReady: function(level) {
		var id = level.p.id;
		if (id == 0) {
			var next = this.getNextLevel(id);
			if (next) next.load(false);
		}
	},

	// a level has been successfully finished
	// load/play next one
	levelMastered: function(level) {
		var next = this.getNextLevel(level);
		if (next) next.load(true);
		else alert("All done!! Congrats!!");
	},

	// a level has been aborted
	levelAborted: function(level) {
		Q.clearStages();
		this.p.screens["start"].play();
	},

	// a level has been lost (all characters died)
	levelLost: function(level) {
		this.levelAborted(level); // for now: same as aborted level
	},
});
"""



def defaults(dictionary, defaults_dict):
    """
    adds all key/value pairs from defaults_dict into dictionary, but only if dictionary doesn't have the key
    Args:
        dictionary (the target dictionary):
        defaults_dict (the source (default) dictionary):

    Returns:

    """
    for key, value in defaults_dict.items():
        if key not in dictionary:  # overwrite only if key is missing
            dictionary[key] = value


def extend(dictionary, extend_dict):
    """
    extends the dictionary with extend_dict, thereby overwriting existing keys
    Args:
        dictionary (the target dictionary):
        extend_dict (the source dictionary):

    Returns:

    """
    for key, value in extend_dict.items():
        dictionary[key] = value  # overwrite no matter what
