"""
 ---------------------------------------------------------------------------------
 shine - [s]erver [h]osted [i]ntelligent [n]eural-net [e]nvironment :)

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""

import numpy as np
import random
from typing import List, Tuple, Union
from abc import ABCMeta, abstractmethod

# import tensorflow as tf


"""
server backend
contains:
- experience replay storage
- Q-table/neural nets (parameter server)
- is used by pyrate server
"""


class ReplayMemory(object):
    """
    stores sars' transitions (items)
    - erases old items once a given maxSize is reached (set to 0 for unlimited storage)
    """

    # initializes the storage
    # max_size: when more than max_size items are in the storage, erase old ones
    # items: list of initial items
    def __init__(self, max_size: int = 0, items: List[tuple] = None):
        self.maxSize = max_size
        self.items = items if items is not None else []

    # adds items to our storage
    # - erases old items of we reach the maxSize so that we have exactly maxSize items left
    def add_items(self, items: List[tuple]):
        self.items.extend(items)
        if len(self.items) > self.maxSize:
            self.items = self.items[-self.maxSize:]  # prune the item storage

    # returns n randomly selected items from the storage
    def get_random_items(self, num_items: int) -> List[tuple]:
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
    def __init__(self, name: str, state_dim: int, action_shape: Tuple[int]=(2,)):
        self.name = name
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
    def __init__(self, action_shape: tuple):
        super().__init__()
        self.actionShape = action_shape

    # adds a new state record under s in this dict and sets all action dims to 0
    def add_state_record(self, s: tuple) -> None:
        assert (s not in self)
        self[s] = np.zeros(self.actionShape)

    # returns the q value for s and a
    # - also fills in new values if entries cannot be found
    def get_q_value(self, s: tuple, a: tuple) -> float:
        if s in self:
            l = self[s]
            for entry in l:
                if entry[0] == a:
                    return entry[1]
            raise Exception("ERROR in get_q_value: no entry for action %s found" % str(a))
        else:
            self.add_state_record(s)
            return 0.0

    # returns the argmax(a) value given s
    def get_argmax_a(self, s: tuple) -> float:
        if s in self:
            l = self[s]
            argmax = float("-inf")
            for entry in l:
                if entry[1] > argmax:
                    argmax = entry[1]
            return argmax
        else:
            self.add_state_record(s)
            return 0.0

    # updates an existing entry or creates a new entry given s,a and a q-value
    def upsert_q_value(self, s: tuple, a: tuple, q: float) -> None:
        if s in self:
            l = self[s]
            for entry in l:
                if entry[0] == a:
                    entry[1] = q  # override old value
            raise Exception("ERROR in upsert_q_value: no entry for action %s found" % str(a))
        else:
            self.add_state_record(s)
            self.upsert_q_value(s, a, q)


class Algorithm(object, metaclass=ABCMeta):
    """
    a simple algorithm object handling the learning algos and the distribution of the same over different CPU/GPU units
    """

    def __init__(self):
        pass

    # runs this algorithm
    # TODO: multiprocessing implementation
    @abstractmethod
    def run(self):
        pass


class SimpleQLearner(Algorithm):
    """
    a simple (tabular) q-learning algorithm
    """

    # define some learning parameters
    # learning_rate (alpha): the learning rate for Q backups
    # gamma: discount factor
    # max_num_batches: the maximum number of batches to pull from the ReplayMemory
    # batch_size: the number of experience tuples to pull for each batch from the ReplayMemory
    # client_sync_frequency: the number of batches after which a sync with the client will happen
    # world: the world to run/train on
    # experience_storage: the ExperienceStorage object to use
    def __init__(self, learning_rate: float=0.01, gamma: float=0.95, max_num_batches: int=10000, batch_size: int=128,
                 client_sync_frequency: int=50,
                 world: Union[World, None] = None,
                 replay_memory: Union[ReplayMemory, None] = None
                 ):
        super().__init__()

        # store parameters
        self.learningRate = learning_rate
        self.gamma = gamma
        self.maxNumBatches = max_num_batches
        self.batchSize = batch_size
        self.clientSyncFrequency = client_sync_frequency

        # setup our learning tools
        self.qTable = None
        self.world = None
        if world is not None:
            self.set_world(world)

        self.replayMemory = replay_memory

    # sets the world to learn to the given World object
    # - then resets our Q-Table and resizes it correctly according to the World's action space
    def set_world(self, world: World) -> None:
        self.world = world
        # generate new Q-table (with all slots initialized to 0)
        self.qTable = QTable(world.actionShape)

    # runs the tabular q-learner algo on the given world and experience-storage
    # TODO: multiprocessing support
    def run(self):
        assert(self.world, "Cannot run algorithm without World object!")
        assert(self.replayMemory, "Cannot run algorithm without replayMemory object!")
        for batch_i in range(self.maxNumBatches):
            # pull a batch from our ReplayMemory
            batch = self.replayMemory.get_random_items(self.batchSize)
            for s, a, r, s_ in batch:
                q_sa = self.qTable.get_q_value(s, a)
                new_q_sa = q_sa + self.learningRate * (r + self.gamma * self.qTable.get_argmax_a(s_) - q_sa)
                self.qTable.upsert_q_value(s, a, new_q_sa)
                # TODO: collect some stats: e.g. avg reward per step

            # TODO: frequent progress report to client

            # sync our table with client every n batches
            if batch_i % self.clientSyncFrequency == 0:
                # TODO: where to send client sync request (up to some project/manager object)?
                pass

        # TODO: what to do when we are done


