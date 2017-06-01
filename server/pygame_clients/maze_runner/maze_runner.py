"""
 -------------------------------------------------------------------------
 shine - 
 maze_runner
 
 A simple maze runner game example to test automatic option learning 
  
 created: 2017/06/01 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import shine.spygame.spygame as spyg

debug_flags = (#spyg.DEBUG_RENDER_COLLISION_TILES |
               #spyg.DEBUG_DONT_RENDER_TILED_TILE_LAYERS |
               #spyg.DEBUG_RENDER_SPRITES_RECTS |
               #spyg.DEBUG_RENDER_SPRITES_BEFORE_EACH_TICK |
               #spyg.DEBUG_RENDER_SPRITES_BEFORE_COLLISION_DETECTION |
               #spyg.DEBUG_RENDER_ACTIVE_COLLISION_TILES
               0 #spyg.DEBUG_ALL
               )


class MazeRunnerLevel(spyg.Level):
    def __init__(self, name: str = "maze", **kwargs):
        super().__init__(name, tile_layer_physics_collision_handler=spyg.StepPhysics.tile_layer_physics_collision_handler, **kwargs)

        # hook to the Level's Viking objects (defined in the tmx file's TiledObjectGroup)
        self.vikings = []
        # overwrite empty keyboard inputs
        # arrows, ctrl (switch viking), d, s, space, esc
        self.keyboard_inputs = spyg.KeyboardInputs([[pygame.K_UP, "up"], [pygame.K_DOWN, "down"], [pygame.K_LEFT, "left"], [pygame.K_RIGHT, "right"],
                                                    [pygame.K_SPACE, "action1"], [pygame.K_d, "action2"],
                                                    [pygame.K_RCTRL, "ctrl"], [pygame.K_ESCAPE, "esc"]])

        self.state = spyg.State()
        self.state.register_event("changed.active_viking")

        self.register_event("mastered", "aborted", "lost", "viking_reached_exit")

    def play(self):
        # define Level's Scene (default function that populates Stage with stuff from tmx file)
        scene = spyg.Scene.register_scene(self.name, options={"tmx_obj"                             : self.tmx_obj,
                                                              "tile_layer_physics_collision_handler": self.tile_layer_physics_collision_handler})

        # start level (stage the scene; will overwrite the old 0-stage (=main-stage))
        # - the options-object below will be also stored in [Stage object].options
        stage = spyg.Stage.stage_scene(scene, 0, {"screen_obj": self, "components": [spyg.Viewport(self.display)]})

        # find all Vikings in the Stage and store them for us
        for sprite in stage.sprites:
            if isinstance(sprite, Viking):
                self.vikings.append(sprite)

        # handle characters deaths
        for i, viking in enumerate(self.vikings):
            viking.on_event("die", self, "viking_died")

        # manage the characters in this level
        self.state.set("vikings", self.vikings)
        self.state.on_event("changed.active_viking", self, "active_viking_changed")
        self.state.set("active_viking", 0, True)  # 0=set to first Viking, True=trigger event
        self.state.set("orig_num_vikings", len(self.vikings))

        # activate level triggers
        self.on_event("viking_reached_exit")

        # activate Ctrl switch vikings
        self.keyboard_inputs.on_event("key_down.ctrl", self, "next_active_viking")
        # activate stage's escape menu
        self.keyboard_inputs.on_event("key_down.esc", self, "escape_menu")

        # play a new GameLoop giving it some options
        spyg.GameLoop.play_a_loop(screen_obj=self, debug_rendering=True)

    def done(self):
        spyg.Stage.get_stage().stop()
        self.state.set("active_viking", None, True)
        # switch off keyboard
        self.keyboard_inputs.update_keys()  # empty list -> no more keys

    def escape_menu(self):
        pass

        # TODO: UI
        """def scene_func(stage):
            spyg.Stage.get_stage().pause()
            box = stage.add_sprite(new Q.UI.Container({

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
    def viking_died(self, dead_viking):
        # remove the guy from the Characters list
        vikings = self.state.get("vikings")
        active = self.state.get("active_viking")

        # remove the guy from vikings list
        for i, viking in enumerate(vikings):

            # found the dead guy
            if viking is dead_viking:
                vikings.pop(i)
                # no one left for the player to control -> game over, man!
                if len(vikings) == 0:
                    # TODO: UI alert("You lost!\nClearing stage 0.");
                    self.trigger_event("lost", self)

                # if viking was the active one, make next viking in list the new active one
                elif i == active:
                    # was the last one in list, make first one the active guy
                    if i == len(vikings):
                        self.state.dec("active_viking", 1)  # decrement by one: will now point to last viking in list ...
                        self.next_active_viking()  # ... will move pointer to first element in list

                    # leave active pointer where it is and call _activeCharacterChanged
                    else:
                        self.active_viking_changed([i, i])

                break

    # handles a character reaching the exit
    def viking_reached_exit(self, viking):
        characters = self.state.get("vikings")
        num_reached_exit = 0
        still_alive = len(characters)
        # check all characters' status (dead OR reached exit)
        for i in range(still_alive):
            # at exit
            if characters[i].components["physics"].at_exit:
                num_reached_exit += 1

        # all original characters reached the exit (level won)
        if num_reached_exit == self.state.get("orig_num_vikings"):
            # TODO UI alert("Great! You made it!");
            self.done()
            self.trigger_event("mastered", self)

        # everyone is at exit, but some guys died
        elif num_reached_exit == still_alive:
            # TODO: UI alert("Sorry, all of you have to reach the exit.");
            self.done()
            # TODO: 2) fix black screen mess when level lost or aborted
            self.trigger_event("lost", self)

    # returns the next active character (-1 if none) and moves the activeCharacter pointer to that next guy
    def next_active_viking(self):
        slot = self.state.get("active_viking")
        # TODO if typeof slot == 'undefined':
        #    return -1
        vikings = self.state.get("vikings")
        next_ = ((slot + 1) % len(vikings))
        self.state.set("active_viking", next_, True)
        return next_

    # reacts to a change in the active character to some new slot
    # - changes the viewport follow to the new guy
    def active_viking_changed(self, new_viking, old_viking):
        vikings = self.state.get("vikings")
        # someone is active
        if new_viking is not None:
            for i in range(len(vikings)):
                if i != new_viking:
                    vikings[i].deactivate()
                else:
                    vikings[i].activate()

            # TODO: follow with camera
            # stage = spyg.Stage.get_stage(0)  # default stage
            # stage.follow(characters[params[0]], {x: true, y: true}, {minX: 0, maxX: this.p.collisionLayer.p.w, minY: 0, maxY: this.p.collisionLayer.p.h}, (typeof params[1] == 'undefined' ? 0 : 15)/*max follow-speed (only when not first character)*/)
            vikings[new_viking].blink_animation(15, 1.5)  # 15/s for 1.5s
        # no one is active anymore -> switch 'em all off
        else:
            for viking in vikings:
                viking.deactivate()


class Agent(spyg.AnimatedSprite, metaclass=ABCMeta):
    """
    a generic Agent walking in the maze

    """

    def __init__(self, x: int, y: int, spritesheet: spyg.SpriteSheet):
        """
        Args:
            x (int): the start x position
            y (int): the start y position
            spritesheet (spyg.Spritesheet): the SpriteSheet object (tsx file) to use for this Viking
        """
        super().__init__(x, y, spritesheet)

        self.handles_own_collisions = True
        self.type = spyg.Sprite.get_type("friendly")

        # add components to this Viking
        # loop time line:
        # - pre-tick: Brain (needs animation comp to check e.g., which commands are disabled), Physics (movement + collision resolution)
        # - tick: chose animation to play
        # - post-tick: Animation
        self.register_event("pre_tick", "post_tick", "collision")
        self.cmp_brain = self.add_component(spyg.Brain("brain", ["up", "down", "left", "right"]))
        self.cmp_physics = self.add_component(spyg.PlatformerPhysics("physics"))

        # subscribe/register to some events
        self.register_event("bump.bottom", "bump.top", "bump.left", "bump.right")

    # - mainly determines agent's animation that gets played
    def tick(self, game_loop):
        dt = game_loop.dt

        # tell our subscribers (e.g. Components) that we are ticking
        self.trigger_event("pre_tick", game_loop)

        # moving in x/y direction?
        if self.cmp_physics.vx != 0 or self.cmp_physics.vy:
            self.check_running()
        # not moving in any direction
        else:
            # just stand
            if self.allow_play_stand():
                self.play_animation("stand")

        self.trigger_event("post_tick", game_loop)

        return

    # player is running (called if x-speed != 0)
    def check_running(self):
        if self.cmp_brain.commands["left"] != self.cmp_brain.commands["right"]:  # xor
            self.play_animation("run")

    # check, whether it's ok to play 'stand' animation
    def allow_play_stand(self):
        anim_setup = spyg.Animation.get_settings(self.spritesheet.name, self.cmp_animation.animation)
        return not (anim_setup["flags"] & spyg.Animation.ANIM_PROHIBITS_STAND)


if __name__ == "__main__":
    # create a GameManager
    game_manager = spyg.GameManager([
        # the level
        {"class": MazeRunnerLevel,
         "name" : "MAZE", "id": 1,  # name is enough -> takes tmx file from 'data/'+[name.lower()]+'.tmx' and has default key-inputs
         },
    ], title="The Maze Runner - An A-Maze-ing Game :D", max_fps=60, debug_flags=debug_flags)

    # that's it, play one of the levels -> this will enter an endless game loop
    game_manager.levels_by_name["MAZE"].play()

