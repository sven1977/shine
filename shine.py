# shine - super human intelligent neural-net extension :)

import numpy as np
#import tensorflow as tf


"""
server backend
contains:
- experience replay storage
- Q-table/neural nets (parameter server)
- is used by pyrate server
"""


class TransitionStorage(object):
    """
    stores sars' transitions
    """

    # initializes the storage
    # max_size: when more than max_size items are in the storage, erase old ones
    # items: list of initial items
    def __init__(self, max_size=0, items=[]):
        self.maxSize = max_size
        self.items = items

    def add_items(self, items):
        self.items.extend(items)
        if len(self.items) > self.maxSize:
            self.items = self.items[-self.maxSize:]  # prune the item storage


class World(object):
    """
    a world object that stores all parameters necessary to handle the world on the server side
      - state/action space dimension
    """

    # state_dim: the dimension of the state space (how many features are there in one state vector?)
    # action_dim: the dimension of the action space (how many features are there in one action vector?)
    #             for tabular Q-learning, 1 is probably the best value
    def __init__(self, state_dim, action_shape=[2]):
        self.stateDim = state_dim
        self.actionShape = action_shape


class QTable(dict):
    """
    simplest Q-table implementation: dictionary
    - keys are state tuples with #elem=World.stateDim
    - values are lists of action/q-value tuples
    """

    def __init__(self, action_shape):
        self.actionShape = action_shape

    # adds a new state record under s in this dict and sets all action dims to 0
    def add_state_record(self, s):
        assert(s not in self)
        self[s] = np.zeros(self.actionShape)

    # returns the q value for s and a
    # - also fills in new values if entries cannot be found
    def get_q_value(self, s, a):
        if s in self:
            l = self[s]
            for entry in l:
                if entry[0] == a:
                    return entry[1]
            raise Exception("ERROR in get_q_value: no entry for action %s found" % str(a))
        else:
            self.add_state_record(s)
            return 0.0



