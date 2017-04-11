"""
 -------------------------------------------------------------------------
 shine - 
 components
 
 !!TODO: add file description here!! 
  
 created: 2017/04/05 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

from abc import ABCMeta, abstractmethod
import spygame.spygame as spyg
import types


class Component(object, metaclass=ABCMeta):
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
            spyg.defaults(anim_settings[anim], {
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

    def __init__(self):
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
        self.game_object.on_event("pre-tick", self, self.tick)

        # do the extensions of the GameObject
        # ----
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

