

// the q-table class
function QTable(num_actions) {
    this.table = {}; // this is the table (lookup by state vector, e.g. this.table[(0, 3, 3.5, 8, 10)] -> list of n q-values where n=num-actions [])
    this.numActions = num_actions;

    // used by the synchronization from server
    // table has to be a str-keyed dict where the strings represent the state-description-tuples (e.g. "(12, 34)") coming from the shine server
    this.set_table = function(table) {
        this.table = table;
    };

    // return the argmax(a) for a given state s represented as a string (representing a state-description-tuple e.g. "(12, 46)")
    // - if there are more than one argmax(a)'s, pick one action (from the best) at random
    this.get_max_a = function(s_str) {
        var action_list = this.table[s_str];
        // we know this state -> get the best action
        if (action_list) {
            var best_actions = [];
            var max = null;
            for (var x = 0, l = action_list.length, i = 0; x < l; ++x, ++i) {
                var q = action_list[x];
                if (max == null || q > max) {
                    max = q;
                    best_actions = [i];
                }
                else if (q == max) {
                    best_actions.push(i);
                }
            }
            return best_actions[getRandomInt(0, best_actions.length - 1)];
        }
        // return random action as we don't even have this state (so all q-values are 0 (or uninitialized) anyway)
        else {
            return getRandomInt(0, this.numActions - 1);
        }
    };
}


function EpsilonGreedyPolicy(epsilon, q_table) {
    this.epsilon = epsilon; // default epsilon to use
    this.qTable = q_table; // our q-lookup-table

    // returns an action given s (based on our q-table and epsilon)
    // - s has to be a python-tuple-representing string (e.g. "(1, 2)")
    this.get_a = function(s_str, epsilon) {
        if (epsilon == null) {
            epsilon = this.epsilon;
        }

        // "normal" case: get greedy action from q-table
        if (Math.random() > epsilon) {
            return this.qTable.get_max_a(s_str);
        }
        // epsilon case: return random action
        else {
            return getRandomInt(0, this.qTable.numActions - 1);
        }
    };
}


function SARSBuffer(max_size) {
    this.buffer = [];
    this.maxSize = max_size;
    this.lastAddedItem = null; // the last added item

    // adds a single sars item to this buffer
    this.add_item = function(item) {
        // compare with last added item to see whether we have to include this one (if they are the same, don't include)
        if (this.lastAddedItem && item[1] == this.lastAddedItem[1] && item[2] == this.lastAddedItem[2] && item[0][0] == this.lastAddedItem[0][0] && item[0][1] == this.lastAddedItem[0][1] && item[3][0] == this.lastAddedItem[3][0] && item[3][1] == this.lastAddedItem[3][1]) {
            return;
        }
        //console.log("recording sars=[("+item[0]+"),"+item[1]+","+item[2]+",("+item[3]+")]");
        this.buffer.push(item);
        if (this.buffer.length >= this.maxSize) {
            this.fullHandler(this);
        }
        this.lastAddedItem = item;
    };

    // adds a single sars item to this buffer
    this.empty = function() {
        this.buffer.length = 0;
    };

    // registers a full-handler for this buffer that takes care of emptying the buffer when max_size is reached
    this.register_full_handler = function(handler) {
        this.fullHandler = handler;
    };
}


function ObjectSeqBuffer(max_size) {

}


/**
 * Returns a random integer between min (inclusive) and max (inclusive)
 * Using Math.round() will give you a non-uniform distribution!
 */
function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}