#! /usr/bin/python

import pygame
from pygame import Rect
import shine.spygame.spygame as spyg
import shine.spygame.rl_worlds as rl
import vikings


def main():
    # init the pygame module
    pygame.init()

    # generates a level (world) from a tmx file
    world = spyg.World("data/test.tmx", [800, 640, "Use arrows to move"], frame_rate=60)

    # wraps the world into a reinforcement learning world
    rl_world = rl.RLWorld(world, time_step=30)
    # time_step determines how many times per second we execute an action
    # - actions are executed by either human input (keyboard)
    # - or by an rl-algorithm that permanently runs in the background

    # create our RL world from a tmx file, some screen dimensions and other options (e.g. frame_rate, etc..)
    world = rl.RLWorld("data/test.tmx", [800, 640, "Use arrows to move!"], frame_rate=60)
    # should be quite static in nature:
    # contains/needs:
    # - tmx_obj
    # - screen (pygame.Surface)
    # - spygame:
    #   - action-space (KeybordInputs)
    #   - state-space
    # - options (frame-rate, rl-frame-rate, etc..)
    # --> independent of scenes/stages
    # --> independent of GameLoop

    # generate a Scene object (using the default scene_func (from tmx obj))
    # contains/needs:
    # - tmx_obj (in order to set the Stage)
    scene = spyg.Scene({"tmx_obj": world.tmx_obj})
    spyg.Scene.register_scene("2d_platformer", scene)

    # stage the scene -> run the game with the default GameLoop callback
    # Stage
    # contains/needs:
    # - GameObjects
    # - GameLoop (in order to define default Stage callback method)
    # --> moved GameLoop into Stage/Scene module (only collides with Player, which currently needs GameLoop)
    spyg.Stage.stage_scene("2d_platformer", {"rl_world": world})

    # GameLoop
    # contains/needs:
    # - RLWorld

    # TODO: fix Camera (copy viewport code from quintus)
    #camera = Camera(complex_camera, total_level_width, total_level_height)


class Camera(object):
    def __init__(self, camera_func, width, height):
        self.camera_func = camera_func
        self.state = Rect(0, 0, width, height)

    def apply(self, target):
        return target.rect.move(self.state.topleft)

    def update(self, target):
        self.state = self.camera_func(self.state, target.rect)


def simple_camera(camera, target_rect):
    l, t, _, _ = target_rect
    _, _, w, h = camera
    return Rect(-l+HALF_WIDTH, -t+HALF_HEIGHT, w, h)


def complex_camera(camera, target_rect):
    l, t, _, _ = target_rect
    _, _, w, h = camera
    l, t, _, _ = -l+HALF_WIDTH, -t+HALF_HEIGHT, w, h

    l = min(0, l)                            # stop scrolling at the left edge
    l = max(-(camera.width-WIN_WIDTH), l)    # stop scrolling at the right edge
    t = max(-(camera.height-WIN_HEIGHT), t)  # stop scrolling at the bottom
    t = min(0, t)                            # stop scrolling at the top
    return Rect(l, t, w, h)


# execute the main function
if __name__ == "__main__":
    main()

