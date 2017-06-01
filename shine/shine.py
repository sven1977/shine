"""
 ---------------------------------------------------------------------------------
 shine - [s]erver [h]osted [i]ntelligent [n]eural-net [e]nvironment :)

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""

import random
from typing import List, Callable, Union
from abc import ABCMeta, abstractmethod
import queue
from collections import namedtuple

import tensorflow as tf
import numpy as np



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
    def __init__(self, max_size: Union[int, None] = None, items: Union[List[tuple], None] = None):
        if max_size is None:
            max_size = 1000000
        self.maxSize = max_size
        self.items = items if items is not None else []

    # adds items to our storage
    # - erases old items if we reach the maxSize so that we have exactly maxSize items left
    def add_items(self, items: List[tuple]):
        self.items.extend(items)
        if len(self.items) > self.maxSize:
            self.items = self.items[-self.maxSize:]  # prune the item storage

    # returns n randomly selected items from the storage
    def get_random_items(self, num_items: int) -> List[tuple]:
        return random.sample(self.items, min(num_items, len(self.items)))

    # returns the len of our storage list
    def __len__(self):
        return len(self.items)


class PriorityReplayMemory(object):
    """
    stores sars' transitions (items)
    - erases old items once a given maxSize is reached (set to 0 for unlimited storage)
    """

    # initializes the storage
    # max_size: when more than max_size items are in the storage block old new incoming ones
    def __init__(self, max_size: Union[int, None] = None):
        if max_size is None:
            max_size = 1000000
        self.items = queue.PriorityQueue(maxsize=max_size)

    # adds items to our sorted storage
    # - the first element of the tuple will have to be the score by which we measure priority:
    #   p=-(r + gamma maxa' Q(s'a') - Q(s,a)) (negative so that high rewards are processed first)
    def add_items(self, items: List[tuple]):
        for item in items:
            self.items.put(item)

    # can be used to iterate over the entire priority queue until it's empty
    def iterate(self) -> tuple:
        while True:
            try:
                item = self.items.get(block=False)
            # that's it: queue is empty -> stop iteration
            except queue.Empty:
                return
            # keep iterating until queue is empty
            yield item

    # can be used to iterate over the entire priority queue until it's empty
    def get_item(self) -> Union[tuple, None]:
        try:
            return self.items.get(block=False)
        # that's it: queue is empty -> stop iteration
        except queue.Empty:
            return None

    # returns the len of our storage list
    def __len__(self):
        return self.items.qsize()


class World(object):
    """
    a world object that stores all parameters necessary to handle the world on the server side
      - state/action space dimension
    """

    # dim_state: the dimension of the state space (how many features are there in one state vector?)
    # num_actions: the number of possible actions to chose from in any state
    # max_size_replay: the maximum size of our replay-memory
    def __init__(self, name: str, dim_state: int, num_actions: int=2):
        self.name = name
        self.dimState = dim_state
        self.numActions = num_actions


class QTable(dict):
    """
    simplest Q-table implementation: dictionary
    - keys are state tuples with #elem=World.stateDim
    - values are lists of action/q-value tuples
    """

    # num_actions: the number of possible actions in each state
    def __init__(self, num_actions: int):
        super().__init__()
        self.numActions = num_actions

    # adds a new state record under s in this dict and sets all action dims to 0
    def add_state_record(self, s: tuple) -> None:
        assert (s not in self)
        self[s] = [0.0 for _ in range(self.numActions)]

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
    def upsert_q_value(self, s: tuple, a: int, q: float) -> None:
        if s in self:
            assert a < self.numActions, "ERROR in upsert_q_value: given action ({:d}) out of bounds".format(a)
            self[s][a] = q  # override old value
        else:
            self.add_state_record(s)
            self.upsert_q_value(s, a, q)


class TabularDeterministicWorldModel(dict):
    """
    simplest state transition AND reward model: dictionary
    - keys are s/a-tuples with shape=(World.stateDim, 1(action))
    - values are the r/s' as tuples with shape=[1(reward), World.stateDim]
    """

    # num_actions: the number of possible actions in each state
    def __init__(self, num_actions: int):
        super().__init__()
        self.numActions = num_actions

    # adds a new state/action record
    # - since we are assuming a deterministic environment, simply overwrite old records
    def update(self, s: tuple, a: int, r: float, s_: tuple) -> None:
        self[(s, a)] = (r, s_)

    # returns the r/s' tuple for a given s/a
    def get(self, s: tuple, a: int) -> tuple:
        key = (s, a)
        # we don't have a value yet for this transition -> return 0 reward and same state
        if key not in self:
            return 0.0, s
        return self[key]

    # returns the sar-tuple that would lead to the given state s'
    def get_sar_leading_to_s_(self, s_: tuple) -> list:
        ret = []
        for key, value in self.items():
            if value[1] == s_:
                ret.append((key[0], key[1], value[0]))  # sar
        return ret


class Algorithm(object, metaclass=ABCMeta):
    """
    a simple algorithm object handling the learning algos and the distribution of the same over different CPU/GPU units
    """

    # just set a name here
    # TODO: remove the callback once we have proper event handling/multi processing in place
    def __init__(self, name: str, callback: Callable[[dict], None]):
        self.name = name  # the algo's name
        self.callback = callback  # the callback to call when certain things happen (progress, done learning, q-table sync, etc..)
        self.replayMemory = None  # will be used for planning/priority experience replay

    # runs this algorithm
    # TODO: multiprocessing implementation
    @abstractmethod
    def run(self, options: dict={}) -> None:
        pass

    # resets all data associated with this algo (but not the algo's current hyper-parameters)
    @abstractmethod
    def reset_parameters(self) -> None:
        pass

    # sets the algos hyper-parameters by keyword
    @abstractmethod
    def set_hyperparameters(self, **kwargs) -> None:
        pass


class BasicQLearner(Algorithm, metaclass=ABCMeta):
    """
    a simple (tabular) q-learning algorithm
    """

    def __init__(self, name: str, callback: Callable[[dict], None], learning_rate: float=0.01, gamma: float=0.95, client_sync_frequency: int=50):
        """
        Args:
            name (str): the name of the algorithm
            callback (Callable[dict, None]): a callback to call when we make progress, are done, etc..
            learning_rate (float): the learning rate for Q backups
            gamma (float): discount factor
            client_sync_frequency (int): frequency with which updates are sent to the client
        """
        super().__init__(name, callback)

        # store hyper-parameters
        self.learningRate = learning_rate
        self.gamma = gamma
        self.clientSyncFrequency = client_sync_frequency

        # setup our learning tools
        self.qFunction = None

    # clear out our q-table as our parameter deposit
    def reset_parameters(self) -> None:
        self.qFunction.clear()

    # name of hyper parameters must match class attribute name
    def set_hyperparameters(self, **kwargs) -> None:
        for key, value in kwargs.items():
            # make sure we don't allow fields that are not hyper parameters
            assert key in ["learningRate", "gamma", "maxNumBatches", "batchSize", "clientSyncFrequency"]
            setattr(self, key, value)


class RandomSampleOneStepTabularQLearner(BasicQLearner):
    """
    a simple (tabular) q-learning algorithm
    """

    def __init__(self, name: str, callback: Callable[[dict], None],
                 learning_rate: float=0.01, gamma: float=0.95, max_num_batches: int=10000, batch_size: int=128,
                 client_sync_frequency: int=50, max_size_replay: Union[int, None]=None
                 ):
        """
        Args:
            name (str): the name of the algorithm
            callback (Callable[dict, None]): a callback to call when we make progress, are done, etc..
            learning_rate (float): the learning rate for Q backups
            gamma (float): discount factor
            max_num_batches (int): the maximum number of batches to pull from the ReplayMemory
            batch_size (int): the number of experience tuples to pull for each batch from the ReplayMemory
            client_sync_frequency (int): the number of batches to complete before we send out an update to the client
            max_size_replay (int): the maximum number or sars tuples in our replayMemory
        """
        super().__init__(name, callback, learning_rate, gamma, client_sync_frequency)

        self.maxNumBatches = max_num_batches
        self.batchSize = batch_size

        # setup our own replay memory
        self.replayMemory = ReplayMemory(max_size_replay)

    def add_items_to_replay_memory(self, items: list) -> None:
        self.replayMemory.add_items(items)

    # runs the tabular q-learner algo on the given world and experience-storage
    def run(self, options: dict={}) -> None:
        assert self.qFunction is not None, "Cannot execute run on {} if qFunction is missing!".format(type(self).__name__)

        for batch_i in range(self.maxNumBatches):
            # pull a batch from our ReplayMemory
            batch = self.replayMemory.get_random_items(self.batchSize)
            for s, a, r, s_ in batch:
                q_sa = self.qFunction.get_q_value(s, a)
                max_a_ = self.qFunction.get_max_a(s_)
                new_q_sa = q_sa + self.learningRate * (r + self.gamma * max_a_ - q_sa)
                self.qFunction.upsert_q_value(s, a, new_q_sa)
                # TODO: collect some stats: e.g. avg reward per step

            # sync our table with client every n batches
            # send some progress report to client
            if batch_i % self.clientSyncFrequency == 0:
                self.callback({"event": "progress", "algorithmName": self.name, "pct": int(100 * batch_i / self.maxNumBatches)})
                # TODO: change our protocol b/c json cannot handle tuples as keys, so for now, we have to convert the dict into string-keyed
                q_table_to_send = {}
                for key, value in self.qFunction.items():
                    q_table_to_send[str(key)] = value
                self.callback({"event": "qTableSync", "algorithmName": self.name, "qTable": q_table_to_send})


class PrioritizedSweepingQLearner(BasicQLearner):
    """
    a prioritized sweeping q-learning algorithm (R. Sutton, A. Barto - RL, an Introduction 2016)
    """

    def __init__(self, name: str, callback: Callable[[dict], None],
                 learning_rate: float=0.1, gamma: float=0.95, max_num_sweeps: int=1000, client_sync_frequency: int=100,
                 max_size_replay: Union[int, None]=None, priority_threshold: float=0.1
                 ):
        """
        Args:
            name (str): the name of the algorithm
            callback (Callable[dict, None]): a callback to call when we make progress, are done, etc..
            learning_rate (float): the learning rate for Q backups
            gamma (float): discount factor
            max_num_sweeps (int): how many sweep rounds do we do after each batch of experience?
            client_sync_frequency (int): the number of sweeps to complete before we send out an update to the client
            max_size_replay (int): the maximum size of the replayMemory that we use
            priority_threshold (float): the minimum priority value that a sars tuple must have in order for it to be stored in our replayMemory
        """
        super().__init__(name, callback, learning_rate, gamma, client_sync_frequency)

        self.maxNumSweeps = max_num_sweeps
        self.priorityThreshold = priority_threshold

        # setup priority memory
        self.replayMemory = PriorityReplayMemory(max_size_replay)

        # this algo needs a model to work "offline"
        self.model = None

    # same as parent BUT: calculates the priority of each sars tuple first based on the impact on learning the table
    def add_items_to_replay_memory(self, items: list) -> None:
        # calc priority of the given items
        for item in items:
            # the higher p, the more interesting this tuple is
            p = abs(item[2] + self.gamma * self.qFunction.get_max_a(item[3]) - self.qFunction.get_q_value(item[0], item[1]))
            if p >= self.priorityThreshold:
                # do negative p as python's riorityQueue takes the lowest scores first
                item_to_add = tuple([-p] + list(item))
                self.replayMemory.add_items([item_to_add])

    # runs the prioritized sweeping algo
    def run(self, options: dict={}) -> None:

        # updates our model and inserts 'interesting' experiences (those with string learning changes) into the buffer (prioritized)
        experiences = options["experiences"] if "experiences" in options else []
        for s, a, r, s_ in experiences:
            # only update our world model
            self.model.update(s, a, r, s_)
        self.add_items_to_replay_memory(experiences)

        # do the prioritized sweeping part
        sweeps = 0
        while len(self.replayMemory) > 0 and sweeps < self.maxNumSweeps:
            # pull top item
            p, s, a, r, s_ = self.replayMemory.get_item()
            sweeps += 1
            q_sa = self.qFunction.get_q_value(s, a)
            max_a_ = self.qFunction.get_max_a(s_)
            new_q_sa = q_sa + self.learningRate * (r + self.gamma * max_a_ - q_sa)
            self.qFunction.upsert_q_value(s, a, new_q_sa)

            # get all s-1/a-1 (t-1) predicted (by our model) to end up in s
            predecessors = self.model.get_sar_leading_to_s_(s)
            for s_pre, a_pre, r_pre in predecessors:
                self.add_items_to_replay_memory([(s_pre, a_pre, r_pre, s)])

            # sync our table with client every n batches
            # send some progress report to client
            if sweeps % self.clientSyncFrequency == 0:
                # report approximate progress (not more than 99%)
                # - we don't know exact progress as we cannot estimate the items that get pushed into the queue each iteration
                self.callback({"event": "progress", "algorithmName": self.name, "pct": min(int(100 * sweeps / self.maxNumSweeps), 99.0)})

        # only when we are all done do we send a table refresh
        q_table_to_send = {}
        for key, value in self.qFunction.items():
            q_table_to_send[str(key)] = value
        self.callback({"event": "qTableSync", "algorithmName": self.name, "qTable": q_table_to_send})
        self.callback({"event": "progress", "algorithmName": self.name, "pct": 100})


class LSTMGameObjectQLearner(BasicQLearner):
    """
    A neural network Q-learner that's based on:
    1) an underlying LSTM+fully-connected-linear that takes game objects as inputs and outputs a compressed game state
    2) two "heads" for the LSTM that can be switched
        a) a normal deep Q-learning network that takes the compressed game state and outputs a q-value/action
        b) a pre-train head used to pre-train the LSTM. This head tries to predict the next game image from the input game objects using a deconv net
    """
    def __init__(self, name: str, callback: Callable[[dict], None],
                 learning_rate: float=0.01, gamma: float=0.95,
                 max_num_batches: int=10000, batch_size: int=128,
                 num_inputs: int=10,
                 num_lstm_steps: int=50, lstm_size: int=512, num_lstm_layers: int=1,
                 num_outputs: int=200,
                 client_sync_frequency: int=50, max_size_replay: Union[int, None]=None
                 ):
        """
        Args:
            name (str): the name of the algorithm
            callback (Callable[dict, None]): a callback to call when we make progress, are done, etc..
            learning_rate (float): the learning rate for Q backups
            gamma (float): discount factor
            max_num_batches (int): the maximum number of batches to pull from the ReplayMemory
            batch_size (int): the number of experience tuples to pull for each batch from the ReplayMemory
            num_lstm_steps (int): the number of time steps to rollout the RNN
            lstm_size (int): the number of nodes inside the LSTM (C and h)
            num_lstm_layers (int): the height of the LSTM-cell-stack
            num_outputs (int): the number of output nodes coming from the final layer
            client_sync_frequency (int): the number of batches to complete before we send out an update to the client
            max_size_replay (int): the maximum number or sars tuples in our replayMemory
        """
        super().__init__(name, callback, learning_rate, gamma, client_sync_frequency)

        self.max_num_batches = max_num_batches
        self.batch_size = batch_size
        self.max_size_replay = max_size_replay

        # qFunction is a namedtuple now
        self.qFunction = self.build_nn(num_inputs, num_outputs, batch_size, num_lstm_steps, lstm_size, num_lstm_layers, learning_rate)

    # builds the LSTM + the two different deep learning heads in tensorflow
    @staticmethod
    def build_nn(num_inputs: int, num_outputs: int=100, batch_size: int=50, num_steps: int=50, lstm_size: int=128,
                 num_layers: int=1, learning_rate: float=0.001,
                 grad_clip: int=5, sampling: bool=False) -> namedtuple:
        if sampling:
            batch_size = 1
            num_steps = 1

        tf.reset_default_graph()

        # the LSTM's input (object vectors of size num_inputs are fed in batches for n steps)
        with tf.name_scope('inputs'):
            inputs = tf.placeholder(tf.int32, [batch_size, num_steps, num_inputs], name='inputs')

        # the targets
        with tf.name_scope('targets'):
            targets = tf.placeholder(tf.int32, [batch_size, num_steps, num_outputs], name='targets')
            y_reshaped = tf.reshape(targets, [-1, num_outputs])

        # the dropout rate
        keep_prob = tf.placeholder(tf.float32, name='keep_prob')

        # build the RNN layers
        with tf.name_scope("RNN_cells"):
            # setup a basic lstm cell of size lstm_size (lstm cells have the same size in the hidden state (h) as well as the conveyor belt (C))
            lstm = tf.contrib.rnn.BasicLSTMCell(lstm_size)
            # add dropout to each single LSTM cell
            drop = tf.contrib.rnn.DropoutWrapper(lstm, output_keep_prob=keep_prob)
            # stack up LSTM cell by num_layers (not to be confused with num_steps!)
            cell = tf.contrib.rnn.MultiRNNCell([drop] * num_layers)

        # set the init state of the LSTM to all zeros (across the batch-size)
        with tf.name_scope("RNN_init_state"):
            initial_state = cell.zero_state(batch_size, tf.float32)

        # unfold the RNN across the num_steps (run the data through the RNN layers single-sample-by-single-sample)
        with tf.name_scope("RNN_forward"):
            # split across the num_steps axis, then squeeze that dimension away and push all single inputs into a list
            rnn_inputs = [tf.squeeze(i, squeeze_dims=[1]) for i in tf.split(inputs, num_steps, 1)]
            # we feed that list into the RNN (cell) and give the initial state
            outputs, state = tf.contrib.rnn.static_rnn(cell, rnn_inputs, initial_state=initial_state)

        # keep track of state -> now we are done with the pass, so 'state' is now our final state
        final_state = state

        # reshape output so it's a bunch of rows, one row for each cell output
        with tf.name_scope('sequence_reshape'):
            # do the opposite of splitting -> concat output list back together into one tensor
            seq_output = tf.concat(outputs, axis=1, name='seq_output')
            # reshape so we get out of the lstm with lstm_size features (across the batch)
            output = tf.reshape(seq_output, [-1, lstm_size], name='graph_output')

        # connect the RNN outputs to a final (fully connected) softmax layer and calculate the cost
        with tf.name_scope('logits'):
            softmax_w = tf.Variable(tf.truncated_normal([lstm_size, num_outputs], stddev=0.1), name='softmax_w')
            softmax_b = tf.Variable(tf.zeros(num_outputs), name='softmax_b')
            logits = tf.matmul(output, softmax_w) + softmax_b
            tf.summary.histogram('softmax_w', softmax_w)
            tf.summary.histogram('softmax_b', softmax_b)

        # do the softmax normalization
        with tf.name_scope('predictions'):
            predictions = tf.nn.softmax(logits, name='predictions')
            tf.summary.histogram('predictions', predictions)

        # calculate the loss and the cost
        with tf.name_scope('cost'):
            loss = tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=y_reshaped, name='loss')
            cost = tf.reduce_mean(loss, name='cost')
            tf.summary.scalar('cost', cost)

        # define training part of the graph
        # optimizer for training, using gradient clipping to control exploding gradients
        with tf.name_scope('train'):
            # get all trainable variables
            trainable_vars = tf.trainable_variables()
            # clip gradients of cost over all trainable_variables (d[cost]/d[trainable_vars]) by a global norm
            # gradients(cost, trainable_vars): returns list of gradients with respect to all trainable_vars
            # clip_by_global_norm(list, clip_norm): returns (list of clipped tensors corresponding to list, the global norm (discard in our case))
            clipped_grads, _ = tf.clip_by_global_norm(tf.gradients(cost, trainable_vars), grad_clip)
            # the training algo
            train_op = tf.train.AdamOptimizer(learning_rate)
            # instead of minimize, do the obj_to_follow:
            # 1) we already have the gradients computed (1st part of minimize)
            # 2) apply the clipped gradients to the variables (2nd part of minimize)
            optimizer = train_op.apply_gradients(zip(clipped_grads, trainable_vars))

        merged = tf.summary.merge_all()

        # define a new namedtuple with the follwing field:
        export_nodes = ['inputs', 'targets', 'initial_state', 'final_state', 'keep_prob', 'cost', 'predictions', 'optimizer', 'merged']
        Graph = namedtuple('Graph', export_nodes)
        # collect all local variables in this function
        local_dict = locals()
        # and stick them into the new namedtuple
        graph = Graph(*[local_dict[each] for each in export_nodes])

        return graph  # graph.inputs = inputs, graph.cost = cost, etc...

    # runs the LSTM training procedure
    # - feeds in batch-size x num-steps x input-dim tensors into the network and receives only one output image after each input sequence
    # - sequences of different length are handled by padding with zero-inputs at the end
    def run(self, options: dict={}) -> None:
        # get the experiences from the options dict or from our buffer
        if options["experiences"]:
            experiences = options["experiences"]
            self.add_items_to_replay_memory(experiences)
        else:
            experiences = self.replayMemory.get_random_items(self.batch_size)


        # do the prioritized sweeping part
        sweeps = 0
        while len(self.replayMemory) > 0 and sweeps < self.maxNumSweeps:
            # pull top item
            p, s, a, r, s_ = self.replayMemory.get_item()
            sweeps += 1
            q_sa = self.qFunction.get_q_value(s, a)
            max_a_ = self.qFunction.get_max_a(s_)
            new_q_sa = q_sa + self.learningRate * (r + self.gamma * max_a_ - q_sa)
            self.qFunction.upsert_q_value(s, a, new_q_sa)

            # get all s-1/a-1 (t-1) predicted (by our model) to end up in s
            predecessors = self.model.get_sar_leading_to_s_(s)
            for s_pre, a_pre, r_pre in predecessors:
                self.add_items_to_replay_memory([(s_pre, a_pre, r_pre, s)])

            # sync our table with client every n batches
            # send some progress report to client
            if sweeps % self.clientSyncFrequency == 0:
                # report approximate progress (not more than 99%)
                # - we don't know exact progress as we cannot estimate the items that get pushed into the queue each iteration
                self.callback({"event": "progress", "algorithmName": self.name, "pct": min(int(100 * sweeps / self.maxNumSweeps), 99.0)})

        # only when we are all done do we send a table refresh
        q_table_to_send = {}
        for key, value in self.qFunction.items():
            q_table_to_send[str(key)] = value
        self.callback({"event": "qTableSync", "algorithmName": self.name, "qTable": q_table_to_send})
        self.callback({"event": "progress", "algorithmName": self.name, "pct": 100})
