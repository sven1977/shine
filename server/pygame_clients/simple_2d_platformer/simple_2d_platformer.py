#! /usr/bin/python

import pygame
from pygame import Rect
import shine.spygame.spygame as spyg
import shine.spygame.components as comps
import shine.spygame.scenes as scenes


# WIN_WIDTH = 800
# WIN_HEIGHT = 640
# HALF_WIDTH = int(WIN_WIDTH / 2)
# HALF_HEIGHT = int(WIN_HEIGHT / 2)

# DISPLAY = (WIN_WIDTH, WIN_HEIGHT)
# DEPTH = 32  # 32-bits per color (RGB+alpha, 8-bits each)
# FLAGS = 0

# TILE_SIZE = 16
# AGENT_SIZE = 32


def main():
    # init the pygame module
    pygame.init()

    # create our RL world from a tmx file, some screen dimensions and other options (e.g. frame_rate, etc..)
    world = spyg.RLWorld("data/test.tmx", [800, 640, "Use arrows to move!"], frame_rate=60)

    # generate a Scene object
    scene = scenes.Scene({"tmx_object": world.tmx_obj})

    # stage the scene -> run the game
    scenes.Stage.stage_scene(scene)

    # TODO: fix Camera
    #camera = Camera(complex_camera, total_level_width, total_level_height)

    # this is already in
    game_loop = spyg.GameLoop(world, keyboard_inputs)

    # endless loop
    game_loop.play()


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

