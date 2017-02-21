

// the q-table class
function QTable(num_actions) {
    this.table = {}; // this is the table (lookup by state vector, e.g. this.table[(0, 3, 3.5, 8, 10)] -> list of n q-values where n=num-actions [])
    this.numActions = num_actions;

    // used by the synchronization from server
    this.set_table = function(table) {
        this.table = table;
    };

    // return the argmax(a) for a given state
    this.get_max_a = function(s) {
        var l = this.table[s];
        // we know this state -> get the best action
        if (l) {
            var action = -1;
            var max = undef;
            var i = 0;
            for (var q in l) {
                if (max == undef || q > max) {
                    max = q;
                    action = i;
                }
                ++i;
            }
            return action;
        }
        // return random action as we don't even have this state (so all q-values are 0 (or uninitialized) anyway)
        else {
            return getRandomInt(0, this.numActions);
        }
    };

}


function EpsilonGreedyPolicy(epsilon, q_table) {
    this.epsilon = epsilon;
    this.qTable = q_table;

    // returns an action given a (based on our q-table and epsilon)
    this.get_a = function(s) {
        // "normal" case: get greedy action from q-table
        if (Math.random() > this.epsilon) {
            return this.qTable.get_max_a(s);
        }
        // epsilon case: return random action
        else {
            return getRandomInt(0, this.qTable.numActions);
        }
    };
}



/**
 * Returns a random integer between min (inclusive) and max (inclusive)
 * Using Math.round() will give you a non-uniform distribution!
 */
function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}