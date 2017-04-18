"""
 -------------------------------------------------------------------------
 shine - 
 vikings
 
 !!TODO: add file description here!! 
  
 created: 2017/04/16 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import spygame.spygame as spyg
import pygame
import pygame.font
import random
from abc import ABCMeta, abstractmethod


class Viking(spyg.GameObject, metaclass=ABCMeta):
    """
    a generic Viking

    """

    def __init__(self, x: int, y: int, spritesheet: spyg.SpriteSheet, width: int, height: int):
        """
        Args:
            x (int): the start x position
            y (int): the start y position
            width (int): the width of the collision rect
            height (int): the height of the collision rect
        """
        self.spritesheet = spritesheet
        self.image = spritesheet.tiles[0]  # start with default image 0 from spritesheet
        self.rect = pygame.Rect(x, y, width, height)
        super().__init__(self.image, self.rect)

        self.handles_own_collisions = True
        self.type = spyg.GameObject.register_type("friendly")
        self.is_active_character = False  # more than one Viking can exist in the level
        self.squeeze_speed = 0.5
        self.life_points = 3
        self.ladder_frame = 0
        self.unhealthy_fall_speed = 340
        self.unhealthy_fall_speed_on_slopes = 340  # on slopes, the players can fall a little harder without hurting themselves

        # add components to this player
        self.add_component(spyg.VikingPhysics("physics"))
        self.add_component(spyg.Animation("animation"))
        # TODO: policy: self.add_component(spyg.Policy("policy", [pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_SPACE]))

        # register some events
        self.on_event("bump.bottom", self, "land")
        self.on_event("squeezed.top", self, "get_squeezed")
        self.on_event("hit_liquid_ground")  # player stepped into liquid ground
        self.on_event("hit_particle")  # player hits a particle
        self.on_event("die")  # some animations trigger 'die' when done

        # initialize the 'getting bored'-timer
        self.standing_around_since = 0
        self.next_bored_seq = int(random.random() * 10)+5  # play the next 'bored'-sequence after this amount of seconds

    # makes this player active
    def activate(self):
        if not self.is_active_character:
            self.is_active_character = True
        return self

    # makes this player inactive
    def deactivate(self):
        if self.is_active_character:
            self.is_active_character = False
        return self

    # Controls component's "tick"-method gets called first (event: entity.prestep fired by Player's "update"-method), only then the Player's step method is called
    # - mainly determines player's animation that gets played
    def tick(self, game_loop):
        dt = game_loop.dt

        # tell our subscribers (e.g. Components) that we are ticking
        self.trigger_event("pre_tick", game_loop)

        anim = self.components["animation"]
        phys = self.components["physics"]

        # player is currently standing on ladder (locked into ladder)
        if self.check_on_ladder():
            return

        # jumping/falling
        elif self.check_in_air():
            return

        # special capabilities can go here: e.g. hit with sword or shoot arrows
        elif self.check_actions():
            return

        # moving in x direction
        elif phys.vx != 0:
            self.check_running()
            return

        # not moving in x direction
        else:
            if anim.animation == 'stand':
                self.standing_around_since += dt
            else:
                self.standing_around_since = 0

            brain = self.components["brain"]
            # not moving in x-direction, but trying -> push
            if brain.commands["left"] != brain.commands["right"]:  # xor
                self.play("push")
            # out of breath from running?
            elif self.check_out_of_breath and self.check_out_of_breath():
                pass
            # getting bored?
            elif self.check_bored_timer():
                pass
            # just stand
            elif self.allow_play_stand():
                self.play("stand")
            return

    @abstractmethod
    def check_actions(self):
        pass

    def check_on_ladder(self) -> bool:
        if self.on_ladder <= 0:
            return False

        anim = self.components["animation"]
        anim.animation = False  # do anim manually when on ladder
        anim.flags = 0
        phys = self.components["physics"]

        character_bot = self.rect.y + self.rect.centery - 4

        # we are alomst at the top -> put end-of-ladder frame
        if character_bot <= phys.which_ladder.rect.topy:
            self.ladder_frame = 63
            # we crossed the "frame-jump" barrier -> y-jump player to cover the sprite frame y-shift between ladder top position and ladder 2nd-to-top position
            if self.on_ladder > phys.which_ladder.rect.topy:
                self.rect.y -= 5
        # we are reaching the top -> put one-before-end-of-ladder frame
        elif character_bot <= phys.which_ladder.yalmosttop:
            self.ladder_frame = 64
            if phys.on_ladder:
                if phys.on_ladder <= phys.which_ladder.rect.topy:
                    self.rect.y += 5
        # we are in middle of ladder -> alternate climbing frames
        else:
            self.ladder_frame += phys.vy * dt * -0.16
            if self.ladder_frame >= 69:
                self.ladder_frame = 65
            elif self.ladder_frame < 65:
                self.ladder_frame = 68.999

        phys.on_ladder = self.rect.y + self.rect.centery - 4  # update onLadder (serves as y-pos memory for previous y-position so we can detect a crossing of the "frame-jump"-barrier)
        anim.frame = int(self.ladder_frame)  # normalize to while frame number

        return True

    # function is called when sprite lands on floor
    def land(self, col):
        # if impact was big -> bump head/beDizzy
        if col.impact > self.unhealthy_fall_speed:
            self.play("be_dizzy", 1)

    # quicksand or water
    def hit_liquid_ground(self, what):
        anim = self.components["animation"]
        phys = self.components["physics"]
        if what == "quicksand":
            self.play("sink_in_quicksand", 1)
        elif what == "water":
            self.play("sink_in_water", 1)
        phys.vy = 2

    # hit a flying particle (shot, arrow, etc..)
    def hit_particle(self, col):
        # sliding away from arrow
        #TODO: if we set the speed here, it will be overwritten (to 0) by step func in gamePhysics component
        # we need to have something like an external force that will be applied on top of the player's/scorpion's own movements
        #p.vx = 100*(col.normalX > 0 ? 1 : -1);
        #p.gravityX = -2*(col.normalX > 0 ? 1 : -1);
        self.play("get_hurt", 1)

    # called when this object gets squeezed from top by a heavy object
    def get_squeezed(self, squeezer):
        self.play("get_squeezed", 1)
        # update collision points (top point should be 1px lower than bottom point of squeezer)
        # TODO: don't have p.points in spygame ??
        #dy = (squeezer.rect.y + squeezer.rect.centery) - (self.y + p.points[0][1]) + 1
        #Q._changePoints(this, 0, dy)

    # die function (take this Viking out of the game)
    def die(self):
        self.trigger("dead", self)
        self.destroy()

    # function stubs (may be implemented if these actions are supported)

    # player is running (called if x-speed != 0)
    def check_running(self):
        phys = self.components["physics"]
        brain = self.components["brain"]
        if brain.commands["left"] != brain.commands["right"]:  # xor
            if phys.at_wall:
                self.play("push")
            else:
                self.play("run")

    # check whether we are in the air
    def check_in_air(self):
        anim = self.components["animation"]
        phys = self.components["physics"]
        # we are sinking in water/quicksand
        if anim.animation == "sink_in_quicksand" or anim.animation == "sink_in_water":
            return False
        # falling too fast
        elif phys.vy > self.unhealthy_fall_speed:
            self.play("fall")
            return True
        elif phys.vy != 0:
            self.play("jump")
            return True
        return False

    # check, whether player is getting bored (to play bored sequence)
    def check_bored_timer(self):
        if self.standing_around_since > self.next_bored_seq:
            self.standing_around_since = 0
            self.next_bored_seq = int(random.random() * 10) + 5
            self.play(random.choice(["be_bored1", "be_bored2"]))
            return True
        return False

    # check, whether it's ok to play 'stand' animation
    def allow_play_stand(self):
        return not (self.components["animation"].flags & spyg.Animation.ANIM_PROHIBITS_STAND)


# define player: Baleog
class Baleog(Viking):
    def __init__(self, x: int, y: int, spritesheet: spyg.SpriteSheet, width: int, height: int):
        super().__init__(x, y, spritesheet, width, height)

        self.components["physics"].can_jump = False
        self.disabled_sword = False

        spyg.Animation.register_settings(spritesheet.name, {
            "stand"            : {"frames": [0], "loop": False, "flags": spyg.Animation.ANIM_PROHIBITS_STAND},
            "be_bored1"        : {"frames": [1, 2, 2, 1, 1, 3, 4, 3, 4, 5, 6, 5, 6, 7, 8, 7, 8, 3, 4, 3, 4], "rate": 1 / 3, "loop": False, "next": "stand",
                                  "flags" : spyg.Animation.ANIM_PROHIBITS_STAND},
            "be_bored2"        : {"frames": [1, 2, 2, 1, 1, 7, 8, 7, 8, 2, 2, 1, 2, 2, 1], "rate": 1 / 3, "loop": False, "next": "stand",
                                  "flags" : spyg.Animation.ANIM_PROHIBITS_STAND},
            "run"              : {"frames": [9, 10, 11, 12, 13, 14, 15, 16], "rate": 1 / 8},
            "push"             : {"frames": [54, 55, 56, 57], "rate": 1 / 4},
            "jump"             : {"frames": [36, 37], "rate": 1 / 6},
            "fall"             : {"frames"     : [38], "loop": False, "flags": spyg.Animation.ANIM_DISABLES_CONTROL,
                                  "keys_status": {"left": -1, "right": -1, "up": -1}},
            "be_dizzy"         : {"frames": [39, 40, 41, 40, 41, 42, 42, 43], "rate": 1 / 3, "loop": False, "next": "stand",
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "get_hurt"         : {"frames": [72], "rate": 1 / 2, "next": 'stand',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "get_squeezed"     : {"frames": [122, 123, 124, 124, 125, 125, 125, 125], "rate": 1 / 3, "loop": False, "trigger": "die",
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "sink_in_quicksand": {"frames": [120, 121, 121, 120, 120, 121, 121, 120], "rate": 1 / 2, "loop": False, "trigger": "die",
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "sink_in_water"    : {"frames": [90, 91, 92, 93, 91, 92, 93], "rate": 1 / 2, "loop": False, "trigger": "die",
                                  "flags" : (spyg.Animation.ANIM_PROHIBITS_STAND | spyg.Animation.ANIM_DISABLES_CONTROL)},
            "burn"             : {"frames": [126, 127, 128, 129, 130, 131, 132, 133], "rate": 1 / 4, "loop": False, "trigger": "die",
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            # disables control, except for action1 (which is pressed down)
            "swing_sword1"     : {"frames": [18, 19, 20, 21], "rate": 1 / 4, "loop": False, "next": 'stand',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_SWING_SWORD), "keys_status": {"action1": 1}},
            # disables control, except for action1 (which is pressed down)
            "swing_sword2"     : {"frames": [22, 23, 24, 25], "rate": 1 / 4, "loop": False, "next": 'stand',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_SWING_SWORD), "keys_status": {"action1": 1}},
            "draw_bow"         : {"frames": [27, 27, 28, 29, 30, 31], "rate": 1 / 5, "loop": False, "next": 'holdBow',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_BOW), "keys_status": {"action2": 1}},
            "hold_bow"         : {"frames"     : [31], "loop": False, "flags": (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_BOW),
                                  "keys_status": {"action2": -1}},
            "release_bow"      : {"frames": [33, 32, 33, 32, 33, 32, 0], "rate": 1 / 6, "loop": False, "next": "stand",
                                  "flags" : (spyg.Animation.ANIM_PROHIBITS_STAND | spyg.Animation.ANIM_BOW)},
        })

    def check_actions(self):
        # sword or arrow?
        if self.check_hit_with_sword() or self.check_shoot_with_arrow():
            return True
        return False

    # hit with sword
    # - returns true if player is currently hitting with sword
    def check_hit_with_sword(self):
        anim_flags = self.components["animation"].flags
        brain = self.components["brain"]
        # action1 is pressed AND user's sword is replenished (had released action1 key) AND anim is currently not swinging sword
        if brain.commands["action1"] and not self.disable_sword and not (anim_flags & spyg.Animation.ANIM_SWING_SWORD):
            self.disabled_sword = True
            self.play_animation(random.choice(["swing_sword1", "swing_sword2"]))
            return True
        # re-enable sword? (space key needs to be released between two sword strikes)
        elif not spyg.GameLoop.active_loop.keyboard_inputs.keyboard_registry[pygame.K_SPACE]:  # TODO: what about touch screens?
            self.disabled_sword = False

        return anim_flags & spyg.Animation.ANIM_SWING_SWORD

    # shoot arrow
    # - returns true if player is doing something with arrow right now
    # - false otherwise
    def check_shoot_with_arrow(self):
        anim = self.components["animation"]
        anim_flags = anim.flags
        brain = self.components["brain"]
        if brain.commands["action2"] and not (anim_flags & spyg.Animation.ANIM_BOW):
            self.play_animation("draw_bow")
            return True
        elif not brain.commands["action2"] and anim.animation == "hold_bow":
            self.play_animation("release_bow")
            self.stage.add_game_object(spyg.Arrow({"shooter": self}))
            return True
        return brain.commands["action2"] and (anim_flags & spyg.Animation.ANIM_BOW)


# define player: Erik the Swift
class Erik(Viking):
    def __init__(self, x: int, y: int, spritesheet: spyg.SpriteSheet, width: int, height: int):
        super().__init__(x, y, spritesheet, width, height)

        phys = self.components["physics"]
        phys.run_acceleration = 450
        phys.can_jump = True
        phys.vx_max = 175
        phys.stops_abruptly_on_direction_change = False

        self.ran_fast = False  # flag: if True, play outOfBreath sequence
        self.vx_out_of_breath = 120  # speed after which to play outOfBreath sequence
        self.vx_smash_wall = 150  # minimum speed at which we can initiate smash sequence with 'D'

        spyg.Animation.register_settings(spritesheet.name, {
            "stand"            : {"frames": [0], "loop": False, "flags": spyg.Animation.ANIM_PROHIBITS_STAND},
            "be_bored1"        : {"frames": [1], "rate": 1 / 2, "next": 'stand', "flags": spyg.Animation.ANIM_PROHIBITS_STAND},
            "be_bored2"        : {"frames": [61, 2, 3, 4, 3, 4, 3, 4], "rate": 1 / 3, "next": 'stand',
                                  "flags" : spyg.Animation.ANIM_PROHIBITS_STAND},
            "run"              : {"frames": [5, 6, 7, 8, 9, 10, 11, 12], "rate": 1 / 8},
            "out_of_breath"    : {"frames": [13, 14, 15, 13, 14, 15], "rate": 1 / 4, "next": 'stand',
                                  "flags" : spyg.Animation.ANIM_PROHIBITS_STAND},
            "push"             : {"frames": [54, 55, 56, 57], "rate": 1 / 4},
            "jump_up"          : {"frames": [16], "loop": False},
            "jump_peak"        : {"frames": [17], "loop": False},
            "jump_down"        : {"frames": [18, 19], "rate": 1 / 3},
            "fall"             : {"frames"     : [81], "loop": False, "flags": spyg.Animation.ANIM_DISABLES_CONTROL,
                                  "keys_status": {"left": -1, "right": -1, "up": -1}},
            "be_dizzy"         : {"frames": [36, 37, 38, 39, 40, 38, 39, 40, 41, 42, 43], "rate": 1 / 3, "loop": False, "next": 'stand',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "get_hurt"         : {"frames": [72], "rate": 1 / 2, "next": 'stand',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "get_squeezed"     : {"frames": [126, 127, 128, 128, 129, 129, 129, 129], "rate": 1 / 4, "loop": False, "trigger": 'die',
                                  "flags" : (spyg.Animation.ANIM_DISABLES_CONTROL | spyg.Animation.ANIM_PROHIBITS_STAND)},
            "sink_in_quicksand": {"frames": [108, 109, 110, 108, 109, 110, 108, 109], "loop": False, "rate": 1 / 2, "trigger": 'die',
                                  "flags" : (spyg.Animation.ANIM_PROHIBITS_STAND | spyg.Animation.ANIM_DISABLES_CONTROL)},
            "sink_in_water"    : {"frames": [90, 91, 92, 93, 91, 92, 93], "loop": False, "rate": 1 / 2, "trigger": 'die',
                                  "flags" : (spyg.Animation.ANIM_PROHIBITS_STAND | spyg.Animation.ANIM_DISABLES_CONTROL)},
            "burn"             : {"frames": [117, 118, 119, 120, 121, 122, 123, 124], "rate": 1 / 4, "loop": False, "trigger": 'die',
                                  "flags" : spyg.Animation.ANIM_DISABLES_CONTROL},
        })

    # Erik has no special actions
    def check_actions(self):
        return False

    def check_running(self):
        phys = self.components["physics"]
        brain = self.components["brain"]
        if brain.commands["left"] != brain.commands["right"]:  # xor
            if phys.at_wall:
                self.play_animation("push")
                self.ran_fast = True
            else:
                self.play_animation("run")
            if abs(phys.vx) > self.vx_out_of_breath:
                self.ran_fast = True

    # check whether we are in the air
    def check_in_air(self) -> bool:
        anim = self.components["animation"]
        phys = self.components["physics"]
        # we are sinking in water/quicksand
        if anim.animation == "sink_in_quicksand" or anim.animation == "sink_in_water":
            return False
        # falling too fast
        elif phys.vy > self.unhealthy_fall_speed:
            self.play_animation("fall")
            return True
        # Erik jumps
        elif phys.vy != 0:
            if abs(phys.vy) < 60:
                self.play_animation("jump_peak")
            elif phys.vy < 0:
                self.play_animation("jump_up")
            elif phys.vy > 0:
                self.play_animation("jump_down")
            return True
        return False

    # overwrite bored functionality: Erik blinks eyes more often than he does his other crazy stuff
    def check_bored_timer(self):
        if self.standing_around_since > self.next_bored_seq:
            self.standing_around_since = 0
            self.next_bored_seq = int(random.random() * 5)+5
            self.play_animation(random.choice(["be_bored1", "be_bored1"]))
            return True
        return False

    # check whether we should play the out of breath sequence
    def check_out_of_breath(self):
        anim = self.components["animation"]
        if anim.animation == "run" and self.ran_fast:
            self.play_animation("out_of_breath")
            self.ran_fast = False
        return False


class VikingScreen(spyg.Screen):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.game_objects = (kwargs["game_objects"] if "game_objects" in kwargs else [])  # game_objects (could be plain sprites)

        # labels example: {x: Q.width / 2, y: 220, w: 150, label: "NEW GAME", color: "white", align: "left", weight: "900", size: 22, family: "Fixedsys"},
        self.labels = (kwargs["labels"] if "labels" in kwargs else [])
        ## ODO: audio? self.audio = kwargs["audio"] if "audio" in kwargs else []

    # plays the screen (stages the scene)
	def play(self):

        # define the screen's scene
        def scene_func(stage: spyg.Stage):
            screen = stage.options["screen_obj"]

            # insert labels to screen
            for label_def in self.labels:
                # generate new Font object
                font = pygame.font.Font(None, label_def["size"])
                surf = font.render(label_def["text"], 1, pygame.Color(label_def["color"]))
                game_object = spyg.GameObject(surf, rect=surf.get_rect().move(label_def["x"], label_def["y"]))
                stage.add_game_object(game_object, "labels")

                # insert objects to screen
                for game_obj in self.game_objects:
            stage.add_game_object(game_obj, "sprites")
            return

        scene = spyg.Scene.register_scene(self.name, scene_func)

        # start screen (stage the scene; will overwrite the old 0-stage (=main-stage))
        # - also, will give our keyboard-input setup to the new GameLoop object
	    spyg.Stage.stage_scene(self.name, 0, { "screen_obj": self }) # <-this options-object will be stored in stage.options

    def done(self):
        print("hello")


class VikingLevel(spyg.Level):
    def __init__(self, name: str="test", **kwargs):
        super().__init__(name, **kwargs)
        self.players = kwargs["players"] if "players" in kwargs else []

    def play(self):
        # define Level's Scene (default function that populates Stage with stuff from tmx file)
        scene = spyg.Scene.register_scene(self.name, {"tmx_obj": self.tmx_obj})

        # handle characters deaths
        for i, player in enumerate(self.players):
            player.on_event("dead", self, "character_died")

        # manage the characters in this level
        spyg.state.set("characters", self.players)
        spyg.state.on_event("change.active_character", self, "active_character_changed")
        spyg.state.set("active_character", 0)
        spyg.state.set("orig_num_players", len(self.players))

        # activate level triggers
        self.on_event("reached_exit", self, "character_reached_exit")

        # activate Ctrl switch players
        self.keyboard_inputs.on_event("key_down.ctrl", self, "next_active_character")
        # activate stage's escape menu
        self.keyboard_inputs.on_event("key_down.esc", self, "escape_menu")

        # start level (stage the scene; will overwrite the old 0-stage (=main-stage))
        spyg.Stage.stage_scene(scene, 0, {"screen_obj": self})  # <-this options-object will be stored in stage.options

    def done(self):
        spyg.Stage.get_stage().stop()
        spyg.state.set("active_character", None)
        # switch off keyboard
        self.keyboard_inputs.update_keys()  # empty list -> no more keys

    def escape_menu(self):
        pass

        # TODO: UI
        """def scene_func(stage):
            spyg.Stage.get_stage().pause()
            box = stage.add_game_object(new Q.UI.Container({

                x: Q.width/2,
                y: Q.height/2,
                fill: "rgba(255,255,255,0.75)"
                }));
            var label = stage.insert(new Q.UI.Text(
                { x: 0, y: -10 - 30, w: 100, align: "center", label: "Give up?", color: "black",}
                ), box);
            var yes = stage.insert(new Q.UI.Button(
                { x: 0, y: 0, fill: "#CCCCCC", label: "Yes"},
                function() { stage.options.levelObj.trigger("aborted", stage.options.levelObj); }
                ), box);
            var no = stage.insert(new Q.UI.Button(
                { x: yes.p.w + 20, y: 0, w: yes.p.w, fill: "#CCCCCC", label: "No" },
                function() { Q.clearStage(1); Q.stage(0).unpause(); }
                ), box);
            box.fit(20);

        spyg.Stage.stage_scene(spyg.Scene(scene_func), 1, { "screen_obj": self })
        """

    # handles a dead character
    def character_died(self, dead_character):
        # remove the guy from the Characters list
        characters = spyg.state.get("characters")
        active = spyg.state.get("active_character")

        # remove the guy from characters list
        for i, character in enumerate(characters):

            # found the dead guy
            if character is dead_character:
                characters.pop(i);
                # no one left for the player to control -> game over, man!
                if len(characters) == 0:
                    # TODO: UI alert("You lost!\nClearing stage 0.");
                    self.trigger_event("lost", self)
    
                # if character was the active one, make next character in list the new active one
                elif i == active:
                    # was the last one in list, make first one the active guy
                    if i == len(characters):
                        spyg.state.dec("active_character", 1)  # decrement by one: will now point to last character in list ...
                        self.next_active_character()  # ... will move pointer to first element in list
    
                    # leave active pointer where it is and call _activeCharacterChanged
                    else:
                        self.active_character_changed([i, i])

                break
    
    # handles a character reaching the exit
    def character_reached_exit(self, character):
        characters = spyg.state.get("characters")
        num_reached_exit = 0
        still_alive = len(characters)
        # check all characters' status (dead OR reached exit)
        for i in range(still_alive):
            # at exit
            if characters[i].components["physics"].at_exit:
                num_reached_exit += 1
    
        # all original characters reached the exit (level won)
        if num_reached_exit == spyg.state.get("orig_num_characters"):
            # TODO UI alert("Great! You made it!");
            self.done()
            self.trigger_event("mastered", self)
    
        # everyone is at exit, but some guys died
        elif num_reached_exit == still_alive:
            # TODO: UI alert("Sorry, all of you have to reach the exit.");
            self.done()
            #TODO: 2) fix black screen mess when level lost or aborted
            self.trigger_event("lost", self)

    # returns the next active character (-1 if none) and moves the activeCharacter pointer to that next guy
    @staticmethod
    def next_active_character():
        slot = spyg.state.get("active_character")
        # TODO if typeof slot == 'undefined':
        #    return -1
        characters = spyg.state.get("characters")
        next_ = ((slot+1) % len(characters))
        spyg.state.set("active_character", next_)
        return next_
    
    # reacts to a change in the active character to some new slot
    # - changes the viewport follow to the new guy
    @staticmethod
    def active_character_changed(params):  # [new val, old val]
        characters = spyg.state.get("characters")
        # someone is active
        if params[0] is not None:
            for i in range(len(characters)):
                if i != params[0]:
                    characters[i].deactivate()
                else:
                    characters[i].activate()
    
            stage = spyg.Stage.get_stage(0)  # default stage
            # TODO: follow: stage.follow(characters[params[0]], {x: true, y: true}, {minX: 0, maxX: this.p.collisionLayer.p.w, minY: 0, maxY: this.p.collisionLayer.p.h}, (typeof params[1] == 'undefined' ? 0 : 15)/*max follow-speed (only when not first character)*/)
            characters[params[0]].blink(15, 1.5)  # 15/s for 1.5s
        # no one is active anymore -> switch 'em all off
        else:
            for character in characters:
                character.deactivate()


"""
        Q._defaults(p, {
                id: 0, // a unique ID
                tmxFile: p.name.toLowerCase()+".tmx",
                tmxObj: 0,
                sheets: ['baleog', 'erik', 'arrow', 'scorpion', 'enemies', 'scorpionshot', 'fireball', 'movable_rock'],
                assets: ['empty_sprite.png', 'elevator.png', 'bg_'+p.nameLc+'.png', 'generic.tsx', p.nameLc+'.tsx'],

                assetList: [],

                collisionLayerName: "collision",
                backgroundLayerName: "background",
                foregroundLayerName: "foreground",
                objectLayerName: "objects",

                playerCharacters: [], // holds all the players (Erik, Baleog, etc..) as objects

                fullyLoaded: false, // set to true if all assets have been loaded
                forcePlayWhenLoaded: false,
            }); // set some defaults, in case they are not given

        this.p = p;

        // build list of assets to load:
        // ... fixed assets
        p.assetList.push(p.tmxFile);
        // add pngs to all tsx files ([same name as tsx].png)
        for (var x = 0, l = p.assets.length; x < l; ++x)
            if (p.assets[x].match(/^([\w\-\.]+)\.tsx$/))
                p.assets.push(RegExp.$1 + ".png");
        p.assetList = p.assetList.concat(Q._normalizeArg(p.assets));
        // ... from sheets info
        for (var x = 0, l = p.sheets.length; x < l; ++x) {
            var name = p.sheets[x].toLowerCase(),
                tsx = name+".tsx",
                png = name+".png";
            p.assetList.push(png, tsx);
            // overwrite sheets array with clean, completed values
            p.sheets[x] = [name, tsx];
        }
    },

    // load all assets in assetList and trigger "ready" event
    load: function(forcePlay) {
        var p = this.p;
        p.forcePlayWhenLoaded = (forcePlay || false);

        // already loaded -> play?
        if (p.fullyLoaded) {
            if (this.p.forcePlayWhenLoaded)
                this.play();
            return;
        }

        // start loading all assets
        Q.load(p.assetList,
            // when loading is done, call this function with context=this
            function(args) {
                // read level's tmx file (will take care of generating sheet-objects for internal sheets)
                this.p.tmxObj = new Q.TmxFile(this.p.tmxFile);
                // generate other sheets needed for this level (given in p.sheets), all from tsx files
                Q._each(this.p.sheets,
                    function(val, slot, arr) {
                        Q.sheet(val[0], 0 /*no asset (we do: from Tsx -->)*/, { fromTsx: val[1] /*tsx filename*/ });
                    },
                    this);
                p.fullyLoaded = true;
                this.trigger("ready", this);
                if (this.p.forcePlayWhenLoaded) this.play();
            },
            {context: this});
    },

    // creates objects from TileLayer objects and adds them into the level's stage
    addObjectsFromTmx: function (stage, level, tmxObj) {
        var p = this.p, layer, obj_counts = { "ladder" : 0, "exit" : 0 };
        // layers
        for (var layerName in tmxObj.p.layers) {
            var tiles = tmxObj.p.layers[layerName];
            //var tiles = layer.p.tiles;
            var tilePropsByGID = tmxObj.p.tilePropsByGID;
            for (var y = 0, n = tiles.length; y < n; ++y) {
                for (var x = 0, l = tiles[y].length; x < l; ++x) {
                    var props = tilePropsByGID[tiles[y][x]];
                    if (! props) continue;
                    // we hit the upper left corner of a ladder
                    if (props["ladder"] &&
                        (! (x > 0 && tilePropsByGID[tiles[y][x-1]] && tilePropsByGID[tiles[y][x-1]]["ladder"])) &&
                        (! (y > 0 && tilePropsByGID[tiles[y-1][x]] && tilePropsByGID[tiles[y-1][x]]["ladder"]))
                    ) {
                        // measure width and height
                        var w = 1, h = 1;
                        for (var x2 = x+1; ; ++x2) {
                            var props2 = tilePropsByGID[tiles[y][x2]];
                            if (! (props2 && props2["ladder"])) break;
                            ++w;
                        }
                        for (var y2 = y+1; ; ++y2) {
                            var props2 = tilePropsByGID[tiles[y2][x]];
                            if (! (props2 && props2["ladder"])) break;
                            ++h;
                        }
                        // insert new Ladder
                        stage.insert(new Q.Ladder({ name: "Ladder"+(++obj_counts["ladder"]), x: x, y: y, w: w, h: h }));
                    }
                    /*// we hit the left tile of an exit
                    else if (props["exit"] && (! (tilePropsByGID[tiles[y][x-1]] && tilePropsByGID[tiles[y][x-1]]["exit"]))) {
                        // insert new exit
                        stage.insert(new Q.Exit({ name: "Exit"+(++obj_counts["exit"]), x: x, y: y }));
                    }*/
                }
            }
        }
        // objects
        for (var objGroupName in tmxObj.p.objectgroups) {
            var objects = tmxObj.p.objectgroups[objGroupName];
            for (var x = 0, l = objects.length; x < l; ++x) {
                var object = objects[x];
                var props = Q._clone(object); // shallow copy to avoid changing of the object in the object-layer by the Sprite's c'tor
                var options = {};
                // remove ()-properties (those are "private" and should not go into Sprite's c'tor)
                for (var prop in object) {
                    if (prop.match(/^\(([\w\.\-]+)\)$/))
                        options[RegExp.$1] = Q._popProperty(props, prop);
                }
                // a sprite -> call c'tor with all given properties
                var ctor = 0, sprite = options.sprite;
                if (sprite && (ctor = Q[sprite])) {
                    // set xmax and ymax automatically for player and enemy game_objects
                    if (options.isPlayer || options.isEnemy)
                        Q._defaults(props, { xmax: stage.options.levelObj.p.collisionLayer.p.w, ymax: stage.options.levelObj.p.collisionLayer.p.h });
                    obj_counts[sprite] = (++obj_counts[sprite] || 1);
                    if (! options.name) {
                        props.name = sprite+(options.isPlayer ? "" : obj_counts[sprite]);
                    }
                    // create and insert the object
                    var obj = stage.insert(new ctor(props));
                    // shift object to match center positions (positions in tmx file are bottom/left positions, not center positions)
                    obj.p.x += obj.p.cx;
                    obj.p.y -= obj.p.cy;
                    // add players to levels player-list
                    if (options["isPlayer"]) level.p.playerCharacters.push(obj);
                }
            }
        }
    },


});
"""