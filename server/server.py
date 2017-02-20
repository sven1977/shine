"""
 ---------------------------------------------------------------------------------
 The main shine server running as backend and waiting
 for incoming Game connections to be served
 - using the twisted library

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""

import sys
# import inspect
from threading import Thread
import logging as log

# twisted server stuff
# from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor

# import ZODB
# import transaction
# import persistent.mapping

# import shine
# import server_pyrate # need to import this to be able to read subclasses of WorldManager
import server_protocol


def get_all_subclasses(_class):
    return _class.__subclasses__() + [g for s in _class.__subclasses__() for g in get_all_subclasses(s)]


# collects all of shine's Algorithm classes and stores them in two structures:
# a) a JSON list that can be sent (as is) back to clients asking for "list algorithms"
# b) a algos_by_name where we can lookup (by Algorithm class name),
#    which methods are clientcallable (field: 'methodNames') and the class itself (field: 'class')
"""def collect_algorithm_class_info():
    algos = get_all_subclasses(shine.Algorithm)
    json_algo_class_list = []
    algo_dict_by_name = {}  # key: WorldManager class name; values: list of ClientCallableMethods (method names)
    # collect each WM's name and pyrateclientcallable methods to the returned json
    for algo in algos:
        methods = inspect.getmembers(algo, predicate=inspect.ismethod)
        client_callable_method_names = []
        for m in methods:
            if hasattr(m, "_IsShineClientCallable"):
                client_callable_method_names.append(m.__name__)
        json_algo_class_list.append({"name": algo.__name__, "setupMethods": methods})
        algo_dict_by_name[algo.__name__] = {"methodNames": client_callable_method_names, "class": algo}

    return algos_by_name, json_algo_class_list
"""


# the command line prompt for shutdown or other commands
def command_prompt(_factory):
    while True:
        cmd = str(input(">"))
        if cmd == "exit":
            # shutdown all protocol (client) connections
            _factory.shutdown_all()
            # stop the reactor
            reactor.stop()
            return  # ends the thread


# main server code
# - run server in main thread
# - spawn off one controller thread that serves as a command prompt (e.g. to shutdown the server gracefully)
if __name__ == "__main__":
    # setup logging
    log.basicConfig(filename='log/server.log', level=log.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

    # figure out our listening port
    port = 0
    try:
        if sys.argv[1]:
            port = int(sys.argv[1])
    except IndexError:
        port = 0

    if port == 0:
        port = 2017

    log.info("PyRATE server started. Listening for incoming web-socket connections on port %d ..." % port)

    # get all pyrate WorldManagers and all of every WorldManager's ClientCallableMethods
    # algos_by_name, json_algo_list = collect_algorithm_class_info()

    # log.info("json_algo_list was compiled as %s" % json_algo_list)

    # connect to the ZODB and store the connection object in this factory object for all protocols to be able to access the DB  # ZODB!
    # connection = ZODB.connection('data/shine_server_data.fs')  # ZODB!
    zoRoot = {}  # connection.root  # ZODB!
    # log.info("connected to ZODB")  # ZODB!

    # create empty tree structure if doesn't exist yet in DB
    # if not hasattr(zoRoot, "Users"):  # ZODB!
    if "Users" not in zoRoot:
        log.info("created ZODB root.Users persistent dict for UserRecord object storage")
        # zoRoot.Users = {"sven": server_protocol.UserRecord("sven")}  # persistent.mapping.PersistentMapping()  # ZODB!
        zoRoot["Users"] = {"sven": server_protocol.UserRecord("sven")}  # persistent.mapping.PersistentMapping()

    # setup the TCP server and start listening
    factory = server_protocol.ShineProtocolFactory(reactor, "ws://localhost:%d" % port, zoRoot)  # , algos_by_name, json_algo_list)
    # determine our protocol to be generated on each call to buildProtocol
    factory.protocol = server_protocol.ShineProtocol

    # endpoint = TCP4ServerEndpoint(reactor, port)
    # endpoint.listen(fact)

    # before we start the "run", start a command prompt thread (+ queue) in order to be later able to shut down the server
    # commandQ = Queue() # the command queue that we'll listen on
    commandT = Thread(target=command_prompt, args=(factory,))
    log.info("starting command prompt thread")
    commandT.start()

    # if "sven" in root.Users:
    #    print("main thread: root.Users['sven'] = %s" % str(root.Users['sven']))

    # start the reactor (this will block until reactor.stop() is called)
    print("starting reactor.run()")
    print("type 'exit' to quit server")
    reactor.listenTCP(port, factory)
    reactor.run()

    # we were stopped by the command prompt thread
    # - commit all transactions to DB before we go down
    # print("exiting server: committing all ZODB transactions and shutting down")  # ZODB!
    print("exiting server: shutting down")
    # transaction.commit()  # ZODB!
    # connection.close() # ZODB!

