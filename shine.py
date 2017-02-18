# shine - super human intelligent neural-net extension :)

import numpy as np
import random
from typing import List
# import tensorflow as tf


"""
server backend
contains:
- experience replay storage
- Q-table/neural nets (parameter server)
- is used by pyrate server
"""


class TransitionStorage(object):
    """
    stores sars' transitions (items)
    - erases old items once a given maxSize is reached (set to 0 for unlimited storage)
    """

    # initializes the storage
    # max_size: when more than max_size items are in the storage, erase old ones
    # items: list of initial items
    def __init__(self, max_size:int=0, items:List[tuple]=None):
        self.maxSize = max_size
        self.items = items if items is not None else []

    # adds items to our storage
    # - erases old items of we reach the maxSize so that we have exactly maxSize items left
    def add_items(self, items:List[tuple]):
        self.items.extend(items)
        if len(self.items) > self.maxSize:
            self.items = self.items[-self.maxSize:]  # prune the item storage

    # returns n randomly selected items from the storage
    def get_random_items(self, num_items:int):
        return random.sample(self.items, num_items)

    # returns the len of our storage list
    def __len__(self):
        return len(self.items)


class World(object):
    """
    a world object that stores all parameters necessary to handle the world on the server side
      - state/action space dimension
    """

    # state_dim: the dimension of the state space (how many features are there in one state vector?)
    # action_dim: the dimension of the action space (how many features are there in one action vector?)
    #             for tabular Q-learning, 1 is probably the best value
    def __init__(self, state_dim, action_shape=(2,)):
        self.stateDim = state_dim
        self.actionShape = action_shape


class QTable(dict):
    """
    simplest Q-table implementation: dictionary
    - keys are state tuples with #elem=World.stateDim
    - values are lists of action/q-value tuples
    """

    # action_shape: the shape of the action space.
    #               E.g. (6,) means that we have a 1D array of 6 elements that can represent the entire action space
    #               E.g. (1,2) means we need a matrix of 1 row/2 cols to be able to represent the entire action space
    def __init__(self, action_shape:tuple):
        super().__init__()
        self.actionShape = action_shape

    # adds a new state record under s in this dict and sets all action dims to 0
    def add_state_record(self, s:str):
        assert(s not in self)
        self[s] = np.zeros(self.actionShape)

    # returns the q value for s and a
    # - also fills in new values if entries cannot be found
    def get_q_value(self, s:tuple, a:tuple):
        if s in self:
            l = self[s]
            for entry in l:
                if entry[0] == a:
                    return entry[1]
            raise Exception("ERROR in get_q_value: no entry for action %s found" % str(a))
        else:
            self.add_state_record(s)
            return 0.0

    # updates an existing entry or creates a new entry given s,a and a q-value
    def upsert_q_value(self, s:tuple, a:tuple, q:float):
        if s in self:
            l = self[s]
            for entry in l:
                if entry[0] == a:
                    entry[1] = q  # override old value
            raise Exception("ERROR in upsert_q_value: no entry for action %s found" % str(a))
        else:
            self.add_state_record(s)
            self.upsert_q_value(s, a, q)


class SimpleQLearner(object):
    """
    a simple (tabular) q-learning algorithm
    """

    # define some learning parameters
    # learning_rate (alpha): the learning rate for Q backups
    # gamma: discount factor
    # max_num_episodes: the maximum number of episodes to play through before learning stops
    # max_steps_per_episode: the maximum number of steps in an episode before we reset the episode again (0=no limit, play until we reach terminal state)
    def __init__(self, learning_rate:float=0.01, gamma:float=0.95, max_num_episodes:int=2000, max_steps_per_episode:int=0, world=None):
        # store parameters
        self.learningRate = learning_rate
        self.gamma = gamma
        self.maxNumEpisodes = max_num_episodes
        self.maxStepsPerEpisode = max_steps_per_episode

        # setup our learning tools
        self.qTable = None
        self.world = None
        if world is not None:
            self.set_world(world)

    # sets the world to learn to the given World object
    # - then resets our Q-Table and resizes it correctly according to the World's action space
    def set_world(self, world:World):
        self.world = world
        # generate new Q-table (with all slots initialized to 0)
        self.qTable = QTable(world.actionShape)


class Job(object):
    """
    a simple job object handling the learning algos and the distribution of the same over different CPU/GPU units
    """
    def __init__(self):
        pass





