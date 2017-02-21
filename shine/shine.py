"""
 ---------------------------------------------------------------------------------
 shine - [s]erver [h]osted [i]ntelligent [n]eural-net [e]nvironment :)

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""

import numpy as np
import random
from typing import List, Callable
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

    # dim_state: the dimension of the state space (how many features are there in one state vector?)
    # num_actions: the number of possible actions to chose from in any state
    # max_size_replay: the maximum size of our replay-memory
    def __init__(self, name: str, dim_state: int, num_actions: int=2, max_size_replay: int=0):
        self.name = name
        self.dimStateDim = dim_state
        self.numActions = num_actions

        # setup our own replay memory
        self.replayMemory = ReplayMemory(max_size_replay)


class QTable(dict):
    """
    simplest Q-table implementation: dictionary
    - keys are state tuples with #elem=World.stateDim
    - values are lists of action/q-value tuples
    """

    # action_dim: the shape of the action space.
    #               E.g. (6,) means that we have a 1D array of 6 elements that can represent the entire action space
    #               E.g. (1,2) means we need a matrix of 1 row/2 cols to be able to represent the entire action space
    def __init__(self, num_actions: tuple):
        super().__init__()
        self.numActions = num_actions

    # adds a new state record under s in this dict and sets all action dims to 0
    def add_state_record(self, s: tuple) -> None:
        assert (s not in self)
        self[s] = np.zeros(self.numActions)

    # returns the q value for s and a
    # - also fills in new values if entries cannot be found
    def get_q_value(self, s: tuple, a: int) -> float:
        assert a < self.numActions, "ERROR in get_q_value: no entry for action {:d} found".format(a)
        if s in self:
            return self[s][a]
        else:
            self.add_state_record(s)
            return 0.0

    # returns the max(a) value (a Q-value, not an action) given s
    def get_max_a(self, s: tuple) -> float:
        if s in self:
            l = self[s]
            max_q = float("-inf")
            for i, q in enumerate(l):
                if q > max_q:
                    max_q = q
            return max_q
        else:
            self.add_state_record(s)
            # all are the same -> return a random action
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

    # just set a name here
    # TODO: remove the callback once we have proper event handling/multi processing in place
    def __init__(self, name: str, callback: Callable[[dict], None]):
        self.name = name  # the algo's name
        self.callback = callback  # the callback to call when certain things happen (progress, done learning, q-table sync, etc..)

    # runs this algorithm
    # TODO: multiprocessing implementation
    @abstractmethod
    def run(self, world: World) -> None:
        pass

    # resets all data associated with this algo (but not the algo's current hyper-parameters)
    @abstractmethod
    def reset_parameters(self) -> None:
        pass

    # sets the algos hyper-parameters by keyword
    @abstractmethod
    def set_hyperparameters(self, **kwargs) -> None:
        pass


class SimpleQLearner(Algorithm):
    """
    a simple (tabular) q-learning algorithm
    """

    def __init__(self, name: str, callback: Callable[[dict], None],
                 learning_rate: float=0.01, gamma: float=0.95, max_num_batches: int=10000, batch_size: int=128,
                 client_sync_frequency: int=50
                 ):
        """

        Args:
            name (str): the name of the algorithm
            callback (Callable[dict, None]): a callback to call when we make progress, are done, etc..
            learning_rate (float): the learning rate for Q backups
            gamma (float): discount factor
            max_num_batches (int): the maximum number of batches to pull from the ReplayMemory
            batch_size (int): the number of experience tuples to pull for each batch from the ReplayMemory
            client_sync_frequency (int): the number of experience tuples to pull for each batch from the ReplayMemory
        """
        super().__init__(name, callback)

        # store hyper-parameters
        self.learningRate = learning_rate
        self.gamma = gamma
        self.maxNumBatches = max_num_batches
        self.batchSize = batch_size
        self.clientSyncFrequency = client_sync_frequency

        # setup our learning tools
        self.qTable = None

    # runs the tabular q-learner algo on the given world and experience-storage
    # TODO: multiprocessing support
    def run(self, world: World) -> None:
        replay_memory = world.replayMemory
        for batch_i in range(self.maxNumBatches):
            # pull a batch from our ReplayMemory
            batch = replay_memory.get_random_items(self.batchSize)
            for s, a, r, s_ in batch:
                q_sa = self.qTable.get_q_value(s, a)
                argmax_a_ = self.qTable.i(s_)
                new_q_sa = q_sa + self.learningRate * (r + self.gamma * self.qTable.get_q_value(s_, argmax_a_) - q_sa)
                self.qTable.upsert_q_value(s, a, new_q_sa)
                # TODO: collect some stats: e.g. avg reward per step

            # sync our table with client every n batches
            # send some progress report to client
            if batch_i % self.clientSyncFrequency == 0:
                self.callback({"event": "progress", "pct": int(100 * batch_i / self.maxNumBatches)})
                self.callback({"event": "qTableSync", "qTable": self.qTable})

        # TODO: what to do when we are done?

    # clear out our q-table as our parameter deposit
    def reset_parameters(self) -> None:
        self.qTable.clear()

    # name of hyper parameters must match class attribute name
    def set_hyperparameters(self, **kwargs) -> None:
        for key, value in kwargs.items():
            # make sure we don't allow fields that are not hyper parameters
            assert key in ["learningRate", "gamma", "maxNumBatches", "batchSize", "clientSyncFrequency"]
            setattr(self, key, value)

