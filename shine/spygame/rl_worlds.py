"""
 -------------------------------------------------------------------------
 shine - 
 rl_worlds
 
 !!TODO: add file description here!! 
  
 created: 2017/04/11 in PyCharm
 (c) 2017 Sven - ducandu GmbH
 -------------------------------------------------------------------------
"""

import pygame
import spygame.spygame as spyg
from typing import List, Union
from pytmx.util_pygame import load_pygame


class RLWorld(object):
    """
    An actual reinforcement learning game world
    """
    def __init__(self, tmx_file, display: Union[pygame.Surface, List[int, str]], **kwargs):
        """

        Args:
            display (pygame.Surface): the display that we render everything on
        """
        self.tmx_file = tmx_file
        ## load in the world's tmx file
        # self.tmx_obj = load_pygame(self.tmx_file)
        # self.level_width = self.tmx_obj.width * self.tmx_obj.tilewidth
        # self.level_height = self.tmx_obj.height * self.tmx_obj.tileheight

        # register keyboard inputs (get them from the tmx file properties (property='actions' which should be a comma-separated string of pygame key codes (e.g. "K_RIGHT,K_DOWN,K_a,K_1,K_2,K_UP"))
        self.keyboard_inputs = spyg.KeyboardInputs([getattr(pygame, key) for key in self.tmx_obj.properties["actions"].split(',')])

        if isinstance(display, list):
            # dimensions and title given: create a Screen (pygame.Surface)
            self.display = pygame.display.set_mode(tuple([display[0], display[1]]), 0, 32)  # 0=flags, 32=depth
            pygame.display.set_caption(display[2] if len(display) >= 2 else "spygame RLWorld")
        else:
            self.display = display

        # the reinforcement learning time step parameter (note: this can be different from the game's framerate)
        # TODO: implement
        if "rl_frame_rate" in kwargs:
            self.rl_frame_rate = kwargs["rl_frame_rate"]
        # TODO: implement not showing the display, but just doing the calculations under the hood
