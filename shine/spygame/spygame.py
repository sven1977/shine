"""
 -------------------------------------------------------------------------
 shine - 
 pyg
 
 !!TODO: add file description here!! 
  
 created: 2017/04/04 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import xml.etree.ElementTree
import pygame
import os.path
from collections import Iterable
from typing import List, Union


class KeyboardInputs(object):
    def __init__(self, key_list=None):
        # stores the keys that we would like to be registered as important
        # - key: pygame keyboard code (e.g. pygame.K_ESCAPE, pygame.K_UP, etc..)
        # - value: True if currently pressed, False otherwise
        if not key_list:
            key_list = [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]
        self.keyboard_registry = {key: False for key in key_list}

    def tick(self, dt=None):
        """
        pulls all keyboard events from the even queue and processes them according to our keyboard_inputs definition
        Args:
            dt (float): will be ignored

        Returns: None

        """
        events = pygame.event.get([pygame.K_DOWN, pygame.K_UP])
        for e in events:
            if e.key in self.keyboard_registry:
                if e.type == pygame.KEYDOWN:
                    self.keyboard_registry[e.key] = True
                else:
                    self.keyboard_registry[e.key] = False


class GameLoop(object):

    # static loop object (the currently active GameLoop gets stored here)
    active_loop = None

    def __init__(self, rl_world: RLWorld, callback, keyboard_inputs: KeyboardInputs, max_fps: float=60.0):
        """

        Args:
            rl_world (RLWorld): The reinforcement learning world that this loop takes care of
            callback (callable): The callback function used for looping
            keyboard_inputs ():
            max_fps ():
        """
        self.rl_world = rl_world
        self.is_paused = True  # True -> Game loop will be paused (no frames, no ticks)
        self.callback = callback  # gets called each tick with this GameLoop instance as the first parameter (can then extract dt as `game_loop.dt`)
        self.max_fps = max_fps  # the max fps rate
        self.timer = pygame.time.Clock()  # our tick object
        self.frame = 0  # global frame counter
        self.keyboard_inputs = keyboard_inputs
        self.dt = 0.0  # time since last tick was executed

    def pause(self):
        self.is_paused = True

    def play(self, max_fps=None):
        self.is_paused = False
        while not self.is_paused:
            self.tick(max_fps)

    def tick(self, max_fps=None):
        if not max_fps:
            max_fps = self.max_fps

        # move the clock and store the dt (since last frame) in sec
        self.dt = self.timer.tick(max_fps) / 1000

        # default global events?
        events = pygame.event.get([pygame.QUIT])  # TODO: add more here?
        for e in events:
            if e.type == pygame.QUIT:
                raise(SystemExit, "QUIT")
        # collect keyboard events
        self.keyboard_inputs.tick()

        # call the callback with self (for references to important game parameters)
        self.callback(self)

        # increase global frame counter
        self.frame += 1

        ## deal with other system events
        # pygame.event.pump()


class EventObject(object):
    """
    Corresponds to evented class in Quintus/html5
    - these are not pygame events!
    """
    def on_event(self, event, target=None, callback=None):
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

    def trigger_event(self, event, data=None):
        """
        triggers an event, passing in some optional additional data about the event
        Args:
            event (str): the event's name
            data (any): the data to be passed to the handler methods

        Returns:

        """
        # make sure there are any listeners, then check for any listeners on this specific event, if not, early out
        if hasattr(self, "listeners") and event in self.listeners:
            # call each listener in the context of either the target passed into `on_event` ([0]) or the object itself
            for listener in self.listeners[event]:
                # listener expects at least one arg
                if data:
                    params = data if isinstance(data, Iterable) else [data]
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


class GameObject(pygame.sprite.Sprite, EventObject):
    """
    Inherits from Sprite, but also adds capability to add Components
    """

    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        EventObject.__init__(self)
        self.components = {}
        self.is_destroyed = False
        self.stage = None

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

        # TODO: remove this -> we should just subscribe to event 'destroyed' if we have a destroyed method
        if self.destroyed:
            self.destroyed()


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


class Player(GameObject):
    def __init__(self, x: int, y: int, spritesheet: SpriteSheet, width: int, height: int):
        """
        Args:
            x (int): the start x position
            y (int): the start y position
            width (int): the width of the collision rect
            height (int): the height of the collision rect
        """
        super().__init__()
        self.xVel = 0
        self.yVel = 0
        self.onGround = False
        self.spritesheet = spritesheet
        self.image = spritesheet.tiles[0]  # start with default image 0 from spritesheet
        self.rect = Rect(x, y, width, height)
        # self.running = False

        # add animation component
        self.add_component(comps.Animation("animation"))
        self.play_animation("run")

    def tick(self, game_loop: GameLoop, platforms):  # TODO: move platforms and collision control into Stage object
        # tell our subscribers (e.g. Components) that we are about to tick
        self.trigger_event("pre-tick", game_loop)

        inputs = game_loop.keyboard_inputs.keyboard_registry
        if inputs[pygame.K_UP]:
            # only jump if on the ground
            if self.onGround:
                self.yVel -= 10
        # if self.down:
        #    pass
        # if self.running:
        #    self.xVel = 12
        if inputs[pygame.K_LEFT]:
            self.xVel = -8
        if inputs[pygame.K_RIGHT]:
            self.xVel = 8
        if not self.onGround:
            # only accelerate with gravity if in the air
            self.yVel += 0.3
            # max falling speed
            if self.yVel > 100:
                self.yVel = 100
        if not(inputs[pygame.K_LEFT] or inputs[pygame.K_RIGHT]):
            self.xVel = 0

        # increment in x direction
        self.rect.left += self.xVel
        # do x-axis collisions
        self.collide(self.xVel, 0, platforms)

        # increment in y direction
        self.rect.top += self.yVel
        # assuming we're in the air
        self.onGround = False
        # do y-axis collisions
        self.collide(0, self.yVel, platforms)

    def collide(self, x_vel, y_vel, platforms):
        for p in platforms:
            if pygame.sprite.collide_rect(self, p):
                # if isinstance(p, ExitBlock):
                #    pygame.event.post(pygame.event.Event(pygame.QUIT))
                if x_vel > 0:
                    self.rect.right = p.rect.left
                if x_vel < 0:
                    self.rect.left = p.rect.right
                if y_vel > 0:
                    self.rect.bottom = p.rect.top
                    self.onGround = True
                    self.yVel = 0
                if y_vel < 0:
                    self.rect.top = p.rect.bottom
                    self.yVel = 0


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
        self.tilePropsById = {}

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
                self.tilePropsById[id_] = {}  # create new dict for this tile
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
                            self.tilePropsById[id_][prop.attrib["name"]] = val
                    else:
                        raise("ERROR: expected only <properties> tag within <tile> in tsx file {}".format(file))


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
