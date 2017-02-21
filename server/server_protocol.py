"""
 ---------------------------------------------------------------------------------
 The shine protocol class as an instance of twisted's Protocol class
 - the PyRATE protocol handles login, project requests, new projects,
   setup and controlling learning algorithms
 - a persistent record is stored in the DB for each game client username
   under the root-field: 'Users', which is a dict with the username
   as keys and UserRecord objects as values
 - a UserRecord is a dict for Projects (key=project name, values=Project objects)
 - a Project is a dictionary that can hold Algorithm objects
 - the Project can be controlled through the pyrate protocol's
   messages via the client side
 - a project with all its objects (worlds, algorithms, NNs, q-tables, etc..)
   can be stored entirely in the DB and revived by the client after
   disconnecting/reconnecting via the 'set project' request message

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""

import logging as log
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
import json  # our format for messaging
import server_config as conf  # PyRATE TCP server config
import shine


# used for internal protocol related errors whose message text should not be communicated back to the client
class ShineProtocolInternalException(Exception):
    pass


# used for when the client sends back a bad message
class ShineProtocolClientMessageError(Exception):
    pass


class UserRecord(object):  # persistent.Persistent):
    """
     A class to store Projects under a username in the DB roots 'Users' field
    """

    def __init__(self, user_name: str):
        assert (isinstance(user_name, str) and len(user_name) <= conf.SHINE_SERVER_MAX_LEN_USERNAME)
        self.userName = user_name

        # - persistent map for Project/Job objects

        # stores all Projects under their respective 'project name' (a str determined by the client in 'new project' messages)
        self.projects = {}  # persistent.mapping.PersistentMapping()
        # dict with the different algorithms this user might have running (or ran in the past); key=algo Id (int) unique per user; value=an Algorithm object
        self.algorithms = {}  # persistent.mapping.PersistentMapping()


class Project(object):  # persistent.Persistent):
    """
     A Project class that will be stored persistently in the DB
     - a project is stored under a username in the root object of the OODB
     - a project keeps references to all WorldManagers the user has ever used:
     - projects are controlled by the client via the PyRATE protocol's 'execute code' message type
     - projects can be saved before disconnection and reloaded after reconnection
    """

    # define some often used regex's for code matching
    # order in the list is the order with which rx's get applied to the given 'code'
    # slot0: rx to match
    # slot1: method to call with the matched parentheses
    # ProtocolCodeRX = [
    #    # new instance of WorldManager class
    #    (re.compile("^\\s*([a-zA-Z]\\w*)\\s*=\\s*(\\w*)\\((.*)\\)$"), "execute_code_new_instance"),
    #    # calling a valid method on an existing (valid) object
    #    (re.compile("^\\s*([a-zA-Z]\\w*)\\.([a-zA-Z]\\w*)\\((.*)\\)$"), "execute_code_method_call"),
    #    ]

    # a project lives under the user key inside the 'projects' attribute of the root object of the DB
    # - and has a name by which it can be saved and reloaded
    def __init__(self, name: str, user_name: str):
        self.name = name
        self.userName = user_name

        # - persistent map for all (unique) client-used algos and worlds
        self.algorithms = {}  # persistent.mapping.PersistentMapping()
        self.worlds = {}  # persistent.mapping.PersistentMapping()

        self._v_ShineProtocol = None  # will be set whenever a project is 'set' (or new one created)

    # old execute code crap

    # takes care of handling a client 'execute code' request (takes it away from the Protocol's responsibility)
    # IMPORTANT: remember to always update the CurrentWorldManager field whenever a WorldManager variable is used in code
    #  e.g. 'wm = GridWorld()' -> set CurrentWorldManager to 'wm'
    # def handleExecuteCodeRequest(self, code, code_id):
    #    for rule in Project.ProtocolCodeRX:
    #        matchObj = rule[0].search(code)
    #        if matchObj:
    #            # call the respective method
    #            getattr(self, rule[1])(matchObj)
    #            break

    # sanity checks a variable name for validity
    # @staticmethod
    # def execute_code_check_valid_variable_name(var):
    #     if len(var) > conf.SHINE_SERVER_MAX_LEN_VARIABLE:
    #         raise (Exception("variable %s longer than allowed %d characters!" % (var, conf.SHINE_SERVER_MAX_LEN_VARIABLE)))

    # creates a new instance of an allowed object (e.g. WorldManager) inside this Project
    # execute code syntax: [var name] = [c'tor name]()
    # def execute_code_new_instance(self, match_obj):
    #     # check given variable
    #     var = match_obj.group(1)
    #     Project.execute_code_check_valid_variable_name(var)
    #     # check whether class to construct is a valid class
    #     ctor = match_obj.group(2)

    #     if ctor not in self._v_ShineProtocol.factory.WorldManagerDict:
    #         raise (Exception("%s is not a valid constructor to be called!" % ctor))
    #     # generate the WorldManager and store it in the Project's WorldManager dict
    #     obj = self._v_ShineProtocol.factory.WorldManagerDict[ctor]["class"]()
    #     self.variables[var] = obj
    #    self.currentWorldManager = obj

    # calls some valid pyrateclientcallable method on an existing (valid) object
    # execute code syntax: [var name].[method name]([param list])
    """def execute_code_method_call(self, match_obj):
        # check given object variable
        var = match_obj.group(1)
        Project.execute_code_check_valid_variable_name(var)
        if not var in self.variables:
            raise(Exception("%s is not defined!" % var))
        obj = self.variables[var]
        # check whether method to call on that object is @pyrateclientcallable AND
        # actually a method of the variable's class
        meth_name = match_obj.group(2)
        if not hasattr(obj, meth_name):
            raise(Exception("class %s has no member %s!" % (type(obj), meth_name)))
        meth = getattr(obj, meth_name)
        if not callable(meth):
            raise(Exception("class member %s.%s is not callable!" % (type(obj), meth_name)))
        elif not hasattr(meth, "_IsPyrateClientCallable"):
            raise(Exception("class method %s.%s is not @pyrateclientcallable!" % (type(obj), meth_name)))

        # do type checking for parameters of the method
        sig = signature(meth)
        # params_meth: ['num_bla:int', 'name:str', 'names:List[str]']
        params_meth = list(sig.parameters.keys())

        # compare client given parameters with function's remaining parameters
        try:
            # paramsClient: [4, 'someName', ['a', 'b', 'c']]
            jsonStr = "[%s]" % match_obj.group(3)
            Log("Trying to load str '%s' into paramsClient" % jsonStr, -1)
            paramsClient = json.loads(jsonStr)
            Log("Loaded json. Num params=%d" % len(paramsClient), -1)
        # something wrong with json -> re-raise
        except Exception as e:
            raise(Exception("parameters inside method call to %s.%s have invalid syntax!" % (match_obj.group(1), match_obj.group(2))))

        # find out whether we have to pass in the PyrateProtocol as first parameter
        #  (e.g. server_pyrate.ClientWorld.GenerateWorld())
        if params_meth[0] == "pyrateProtocol":
            Log("have to add pyrateProtocol to method call (1st arg)", -1)
            paramsClient.insert(0, self._v_ShineProtocol)

        # params all json-ok
        # check number of params
        if len(paramsClient) != len(params_meth):
            raise(Exception("%d parameters needed in %s.%s, but %d provided!" % (len(params_meth), match_obj.group(1), match_obj.group(2), len(paramsClient))))

        # no type checking -> will be done by the method itself
        # just call it!
        try:
            Log("Calling meth with *paramsClient: paramsClient[0]=%s paramsClient[1]=%s" % (str(paramsClient[0]), str(paramsClient[1])), -1)
            meth(*paramsClient)
        except Exception as e:
            raise(Exception("%s" % str(e)))
"""

    # TODO: this will be replaced by event-handling/multiprocessing
    def algorithm_callback(self, obj):
        assert "event" in obj, "no 'event' field in object in algo-callback!"
        assert "algorithmName" in obj, "no 'algorithmName' field in object in algo-callback!"
        event = obj["event"]
        algo_name = obj["algorithmName"]
        assert algo_name in self.algorithms
        if event == "progress":
            assert "pct" in obj, "no 'pct' field in object in algo-callback (event=progress)!"
            self._v_ShineProtocol.sendJson({"notify": "progress", "pct": obj["pct"], "projectName": self.name, "algorithm": algo_name})
        elif event == "qTable":
            assert "qTable" in obj, "no 'qTable' field in object in algo-callback (event=qTable)!"
            self._v_ShineProtocol.sendJson({"notify": "q-table update", "qTable": obj["qTable"], "projectName": self.name, "algorithm": algo_name})


class ShineProtocol(WebSocketServerProtocol):
    """
    our shine communication protocol for communicating with the game clients
     - a Protocol object is created upon connection and destroyed upon disconnection
     - thus, there is no persistency for Protocol objects, only for ProtocolFactories
     - every Protocol instance has access to its factory via the self.factory attribute
    """

    # the request handlers
    protocolRequestLookup = {
        "list projects": "request_list_projects",
        "new project": "request_new_project",
        "set project": "request_set_project",
        "get project": "request_get_project",
        # "list algorithms": "request_list_algorithms",
        "new world": "request_new_world",
        "add experience": "request_add_experience",
        "new algorithm": "request_new_algorithm",
        "run algorithm": "request_run_algorithm",
        # "execute code": "requestExecuteCode",
    }
    # the response handlers
    protocolResponseLookup = {
        "hello": "response_hello",
    }

    # some error codes for protocol errors
    PROTOCOL_ERROR_FIELD_MISSING = 0
    PROTOCOL_ERROR_FIELD_ZERO_LENGTH = 1
    PROTOCOL_ERROR_FIELD_TOO_LONG = 2
    PROTOCOL_ERROR_ITEM_ALREADY_EXISTS = 3
    PROTOCOL_ERROR_ITEM_DOESNT_EXIST = 4
    PROTOCOL_ERROR_FIELD_HAS_WRONG_TYPE = 5
    PROTOCOL_ERROR_INVALID_FIELD_VALUE = 6
    PROTOCOL_ERROR_CUSTOM = 100

    # give each protocol instance the protocol-factory for access to persistent state information
    def __init__(self, _id: int, factory: WebSocketServerFactory, reactor):
        super().__init__()
        self.factory = factory
        self.reactor = reactor
        self.id = _id

        # init fields
        self.nextSendSeqNum = 0  # our own next seqNum
        self.nextClientSeqNum = 0  # the client's expected next seqNum
        self.gotHelloResponse = False  # did we already get the hello response?
        self.clientProtocolVersion = None  # the client's pyrate protocol version
        self.userName = None  # the username of the connected client
        self.userRecord = None  # user-specific DB record being looked up after login (it's basically a dict with the project names as keys and the (DB-stored) project objects as values)
        self.currentProject = None  # the currently active project

    # initialize our state stuff for this connection only
    def onConnect(self, request):
        # send hello message with protocol setup params
        log.info("sending 'hello' message to client after 1 second ...")
        self.reactor.callLater(1.0, self.send_json,
                               {"request": "hello", "maxMsgLen": conf.SHINE_SERVER_MAX_LEN_MESSAGE, "protocolVersion": conf.SHINE_PROTOCOL_VERSION})

    # ???
    def onOpen(self):
        log.debug("WebSocket onOpen")

    # finds any still running jobs and pauses them
    # TODO: later, we might want to give the client the chance to keep certain jobs running (over night?)
    def onClose(self, was_clean, code, reason):
        log.info("disconnected from client was_clean=%r; reason=%s" % (was_clean, str(reason)))
        if self.id in self.factory.protocols:
            del (self.factory.protocols[self.id])
            log.debug("removed id=%d from factory hash (new len=%d)" % (self.id, len(self.factory.protocols)))
        if self.userRecord:
            pass
            # TODO: algos are not pausable yet
            # for algo_id, algo in self.userRecord.algorithms.items():
            #    algo.pause()

    # called whenever a (finished) message string (of the len given by the preceding size-marker) has been received
    # - this string is passed into this method without the size marker
    def onMessage(self, msg, is_binary):
        # check incoming message for binary
        if is_binary:
            return self.abort("Protocol Error (msg ~#%d): Message needs to be string, not binary!\n" % self.nextClientSeqNum)

        msg = msg.decode('utf8')
        log.info("String message received: %s" % msg)

        # check incoming string for correctness
        # str too long -> terminate
        if len(msg) > conf.SHINE_SERVER_MAX_LEN_MESSAGE:
            return self.abort("Protocol Error (msg ~#%d): Message from client too long (has to be at most %d bytes)!\n" % (
                self.nextClientSeqNum, conf.SHINE_SERVER_MAX_LEN_MESSAGE))

        # check the incoming string for valid JSON format and some pyrate-protocol requirements
        try:
            json_obj = json.loads(msg)
            self.sanity_check_incoming_json(json_obj)
        # some internal error -> terminate with generic error message
        except ShineProtocolInternalException:
            return self.abort("Internal Error! Sorry, we are working on a fix. ...")
        # json generally bad -> terminate
        except Exception as e:
            return self.abort(str(e))

        self.nextClientSeqNum += 1

        if json_obj["msgType"] == "request":
            try:
                self.handle_request(json_obj)
            # some internal error -> terminate with generic error message
            except ShineProtocolInternalException:
                return self.abort("Internal Error when handling request! Sorry, we are working on a fix. ...")
            except ShineProtocolClientMessageError as e:
                return self.send_json({"response": "error", "errMsg": str(e)})
            except Exception as e:
                return self.abort("Unknown Error (msg #{:d}): Client-request message handler threw error {:s}: {:s}!\n".format(json_obj["seqNum"], type(e).__name__, str(e)))
        elif json_obj["msgType"] == "response":
            try:
                self.handle_response(json_obj)
            # some internal error -> terminate with generic error message
            except ShineProtocolInternalException:
                return self.abort("Internal Error when handling response! Sorry, we are working on a fix. ...")
            except ShineProtocolClientMessageError as e:
                return self.send_json({"notify": "error", "errMsg": str(e)})
            # terminate
            except Exception as e:
                return self.abort("Unknown Error (msg #%d): Client-response message handler threw error: %s!\n" % (json_obj["seqNum"], str(e)))
        return

    def sanity_check_incoming_json(self, json_obj):
        # check whether message is a dict
        if not isinstance(json_obj, dict):
            raise (Exception("Protocol Error: client did not send valid JSON!\n"))
        # check whether it has a valid origin field
        elif "origin" not in json_obj or json_obj["origin"] != "client":
            raise (Exception("Protocol Error: origin field missing or invalid in message (expecting 'client')!\n"))
        # check whether it has a good seqNum
        elif "seqNum" not in json_obj or not isinstance(json_obj["seqNum"], int) or json_obj["seqNum"] != self.nextClientSeqNum:
            raise (Exception("Protocol Error: seqNum field missing or invalid in message (expecting int and %d)!\n" % self.nextClientSeqNum))
        # check whether it has a good msgType
        elif "msgType" not in json_obj or not (json_obj["msgType"] == "request" or json_obj["msgType"] == "response" or json_obj["msgType"] == "notify"):
            raise (
                Exception("Protocol Error: msgType field missing or invalid in message #%d (expecting 'request|response|notify')!\n" % json_obj["seqNum"]))

    def sanity_check_message(self, json_obj, check_list):
        for check in check_list:
            # test the condition
            # 0=condition, 1=protocol error num, 2=abort?, 3=text1, 4=text2
            if check[0] is False:
                err, is_abort, error_message = check[1], check[2], "Unknown Protocol ErrorError!?"

                if err == ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING:
                    error_message = "Protocol Error (msg #{:d}): Field '{:s}' is missing!".format(json_obj["seqNum"], check[3])
                elif err == ShineProtocol.PROTOCOL_ERROR_FIELD_ZERO_LENGTH:
                    error_message = "Protocol Error (msg #{:d}): Field '{:s}' has zero-length!".format(json_obj["seqNum"], check[3])
                elif err == ShineProtocol.PROTOCOL_ERROR_FIELD_TOO_LONG:
                    error_message = "Protocol Error (msg #{:d}): Field '{:s}' is too long (allowed are max. {:d} chars!".format(json_obj["seqNum"], check[3], check[4])
                elif err == ShineProtocol.PROTOCOL_ERROR_ITEM_DOESNT_EXIST:
                    error_message = "Protocol Error (msg #{:d}): '{:s}' doesn't exist in {:s}!".format(json_obj["seqNum"], check[3], check[4])
                elif err == ShineProtocol.PROTOCOL_ERROR_ITEM_ALREADY_EXISTS:
                    error_message = "Protocol Error (msg #{:d}): '{:s}' already exists in {:s}!".format(json_obj["seqNum"], check[3], check[4])
                elif err == ShineProtocol.PROTOCOL_ERROR_FIELD_HAS_WRONG_TYPE:
                    error_message = "Protocol Error (msg #{:d}): Field '{:s}' has a wrong type. {:s} expected!".format(json_obj["seqNum"], check[3], check[4])
                elif err == ShineProtocol.PROTOCOL_ERROR_INVALID_FIELD_VALUE:
                    error_message = "Protocol Error (msg #{:d}): Unknown response %s from client!".format(check[3])
                elif err == ShineProtocol.PROTOCOL_ERROR_CUSTOM:
                    error_message = "Protocol Error (msg #{:d}): {:s}".format(json_obj["seqNum"], check[3])

                # serious error: drop the connection immediately
                if is_abort:
                    self.abort(error_message)
                # harmless protocol error -> keep connection
                else:
                    raise (Exception(error_message))

    # handles all types of client request messages and takes care of answering these requests with a "response"
    # - throws exception if suspicious behavior is detected
    # - for more benign errors, just responds with an error message
    # - all requests from a client have to come after(!) the initial 'hello' response from the client so that we know the username/userRecord
    def handle_request(self, json_obj):
        self.sanity_check_message(json_obj, [
            # no userRecord -> abort
            (self.userRecord is not None, ShineProtocol.PROTOCOL_ERROR_ITEM_DOESNT_EXIST, True, "userRecord", "database"),
            # no HelloResponse yet on file(client hasn't answered the hello request yet) -> abort
            (self.gotHelloResponse is True, ShineProtocol.PROTOCOL_ERROR_CUSTOM, True, "Server's 'hello'-request has not been answered yet by client!"),
            # no request field
            ("request" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "request"),
            # an unknown request
            (json_obj["request"] in ShineProtocol.protocolRequestLookup, ShineProtocol.PROTOCOL_ERROR_CUSTOM, False, "Unknown request ({:s}) from client!".format(json_obj["request"])),
        ])

        # call the respective handler looked up in ProtocolRequestLookup
        req = json_obj["request"]
        handler = getattr(self, ShineProtocol.protocolRequestLookup[req])
        if not callable(handler):
            raise (ShineProtocolInternalException("Internal Error: %s not found in dict protocolRequestLookup!" % req))
        handler(json_obj)

    # returns a list of all projects available under this userRecord
    def request_list_projects(self, _):
        return self.send_json({"response": "all projects", "projectList": list(self.userRecord.projects.keys())})

    # a new pyrate project (also sets the currentProject field to this new Project)
    def request_new_project(self, json_obj):
        self.sanity_check_message(json_obj, [
            ("projectName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "projectName"),
            (len(json_obj["projectName"]) > 0, ShineProtocol.PROTOCOL_ERROR_FIELD_ZERO_LENGTH, False, "projectName"),
            (len(json_obj["projectName"]) <= conf.SHINE_SERVER_MAX_LEN_PROJECT_NAME, ShineProtocol.PROTOCOL_ERROR_FIELD_TOO_LONG, False, "projectName",
             conf.SHINE_SERVER_MAX_LEN_PROJECT_NAME),
            (json_obj["projectName"] not in self.userRecord.projects, ShineProtocol.PROTOCOL_ERROR_ITEM_ALREADY_EXISTS, False, "projectName {:s}".format(json_obj["projectName"]), "your user account"),
        ])

        # generate the new project in our userRecord
        project_name = json_obj["projectName"]
        project = Project(project_name, self.userName)
        # add new Project to userRecord
        self.userRecord.projects[project_name] = project
        # and set it
        self.set_project(project)

        return self.send_json({"response": "new project created", "projectName": project_name})

    # sets currentProject to an already existing pyrate project
    def request_set_project(self, json_obj):
        if "projectName" not in json_obj:
            return self.send_json({"response": "error", "errMsg": "Protocol Error (msg #%d): field 'projectName' missing in message!" % json_obj["seqNum"]})
        elif len(json_obj["projectName"]) > conf.SHINE_SERVER_MAX_LEN_PROJECT_NAME:
            return self.send_json({"response": "error", "errMsg": "Protocol Error (msg #%d): field 'projectName' is too long (allowed are max. %d chars)!" % (
                json_obj["seqNum"], conf.SHINE_SERVER_MAX_LEN_PROJECT_NAME)})

        project_name = json_obj["projectName"]
        if project_name not in self.userRecord.projects:
            return self.send_json({"response": "error", "errMsg": "Protocol Error (msg #{:d}): given project name ({:s}) does not exist in your user account!".format(
                json_obj["seqNum"], project_name)})

        # get existing Project from userRecord
        project = self.userRecord.projects[project_name]
        # and set it
        self.set_project(project)

        return self.send_json({"response": "set project", "projectName": project_name})

    def set_project(self, project_obj):
        self.currentProject = project_obj
        # create a volatile pointer to this protocol for protocol/protocol-factory access
        self.currentProject._v_ShineProtocol = self

    # gets currentProject
    def request_get_project(self, json_obj):
        if self.currentProject:
            return self.send_json({"response": "current project", "projectName": self.currentProject.name})
        else:
            return self.send_json({"response": "error", "errMsg": "Protocol Error (msg #{:d}): No project currently set".format(json_obj["seqNum"])})

    # returns a list of all valid PyRATE WorldManager classes to the client
    # - including all their client-callable methods
    # def request_list_algorithms(self, _):
    #    self.send_json({"response": "all algorithms", "algorithmList": self.factory.I got nothing})

    # creates a new world (+ReplayMemory)
    def request_new_world(self, json_obj):
        try:
            self.sanity_check_message(json_obj, [
                ("worldName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "worldName"),
                (len(json_obj["worldName"]) > 0, ShineProtocol.PROTOCOL_ERROR_FIELD_ZERO_LENGTH, False, "worldName"),
                (len(json_obj["worldName"]) <= conf.SHINE_SERVER_MAX_LEN_WORLD_NAME, ShineProtocol.PROTOCOL_ERROR_FIELD_TOO_LONG, False, "worldName",
                    conf.SHINE_SERVER_MAX_LEN_WORLD_NAME),
                (json_obj["worldName"] not in self.currentProject.worlds, ShineProtocol.PROTOCOL_ERROR_ITEM_ALREADY_EXISTS, False, json_obj["worldName"], "project {:s}".format(self.currentProject.name))
            ])
        except ShineProtocolClientMessageError as e:
            return self.send_json({"response": "error", "errMsg": str(e)})

        # generate the new project in our userRecord
        world_name = json_obj["worldName"]
        # TODO: make world parameters in request_new_world customizable by client
        self.currentProject.worlds[world_name] = shine.World(world_name, 2, 5)  # for now: maze-runner s=(x,y), a=4 directions + do-nothing
        return self.send_json({"response": "new world created", "worldName": world_name})

    # adds a batch of experience from the client to some ReplayMemory in a world
    def request_add_experience(self, json_obj):
        try:
            self.sanity_check_message(json_obj, [
                ("worldName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "worldName"),
                (json_obj["worldName"] in self.currentProject.worlds, ShineProtocol.PROTOCOL_ERROR_ITEM_DOESNT_EXIST, False, json_obj["worldName"], "current project"),
                ("experienceList" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "experienceList"),
                (isinstance(json_obj["experienceList"], list), ShineProtocol.PROTOCOL_ERROR_FIELD_HAS_WRONG_TYPE, False, "experienceList", "list"),
            ])
        except ShineProtocolClientMessageError as e:
            return self.send_json({"response": "error", "errMsg": str(e)})

        world_name = json_obj["worldName"]
        # type checking of single items
        client_items = json_obj["experienceList"]
        experiences = []  # will be added to the ReplayMemory
        try:
            for i, item in enumerate(client_items):
                self.sanity_check_message(json_obj, [
                    (isinstance(item, list), ShineProtocol.PROTOCOL_ERROR_FIELD_HAS_WRONG_TYPE, "{:d} in experienceList", False, "tuple"),
                ])
                experiences.append(item)
        except ShineProtocolClientMessageError as e:
            return self.send_json({"response": "error", "errMsg": str(e)})

        self.currentProject.worlds[world_name].replayMemory.add_items(client_items)

    # TODO: resets an existing world (+ReplayMemory)
    # def request_reset_world(self, json_obj):
    #    pass

    # creates a new algorithm in this project
    def request_new_algorithm(self, json_obj):
        # TODO: right now, the only algo we know is tabular q-learning, so we create just that, but in the future, we have to add more options to this message
        # TODO: write function for protocol to check given JSON params against internal shine function- and method-signatures
        try:
            self.sanity_check_message(json_obj, [
                ("algorithmName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "algorithmName"),
                (len(json_obj["algorithmName"]) > 0, ShineProtocol.PROTOCOL_ERROR_FIELD_ZERO_LENGTH, False, "algorithmName"),
                (len(json_obj["algorithmName"]) <= conf.SHINE_SERVER_MAX_LEN_WORLD_NAME, ShineProtocol.PROTOCOL_ERROR_FIELD_TOO_LONG, False, "algorithmName",
                    conf.SHINE_SERVER_MAX_ALGORITHM_NAME),
                (json_obj["algorithmName"] not in self.currentProject.algorithms, ShineProtocol.PROTOCOL_ERROR_ITEM_ALREADY_EXISTS, json_obj["algorithmName"], False, "project {:s}".format(self.currentProject.name))
            ])
        except ShineProtocolClientMessageError as e:
            return self.send_json({"response": "error", "errMsg": str(e)})

        # generate the new project in our userRecord
        algo_name = json_obj["algorithmName"]
        self.currentProject.algorithms[algo_name] = shine.SimpleQLearner(algo_name, self.currentProject.algorithm_callback)
        return self.send_json({"response": "new algorithm created", "algorithmName": algo_name})

    # # TODO: sets the hyper-parameters (or some initialization features) for this algorithm
    # def request_setup_algorithm(self, json_obj):
    #    # TODO: assert: name exists in project, hyper-parameters ok
    #    pass

    # runs an algorithm on a world
    # TODO: for now: give a callback (a method of this Protocol) to the algo so we get called whenever the algo reaches some progress, is done, etc..
    def request_run_algorithm(self, json_obj):
        try:
            self.sanity_check_message(json_obj, [
                ("algorithmName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "algorithmName"),
                (json_obj["algorithmName"] in self.currentProject.algorithms, ShineProtocol.PROTOCOL_ERROR_ITEM_DOESNT_EXIST, False, json_obj["algorithmName"], "project {:s}".format(self.currentProject.name)),
                ("worldName" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "worldName"),
                (json_obj["worldName"] in self.currentProject.worlds, ShineProtocol.PROTOCOL_ERROR_ITEM_DOESNT_EXIST, False, json_obj["worldName"], "project {:s}".format(self.currentProject.name)),
            ])
        except ShineProtocolClientMessageError as e:
            return self.send_json({"response": "error", "errMsg": str(e)})

        # run the algo in the project
        algo_name = json_obj["algorithmName"]
        world_name = json_obj["worldName"]
        self.currentProject.algorithms[algo_name].run(self.currentProject.worlds[world_name])
        # TODO: support for multiprocessing algorithm runs
        return self.send_json({"notify": "algorithm completed", "algorithmName": algo_name})

    # method for when a client requests 'code execution' in a request message
    # - this method sounds scary, but it's very controlled and only allowed commands will be executed
    # - first, we try to find the variable in the message, then look up the underlying PyRATE object and do things with it (e.g. setup, world generation, algo-setup, learning)
    """def requestExecuteCode(self, jsonObj):
        # do some basic checking and look for the project to apply this code to
        if not self.currentProject:
            return self.send_json(
                {"response": "error", "errMsg": "Protocol Error (msg #%d): 'execute code' not allowed without setting a Project first!" % jsonObj["seqNum"]})
        elif "code" not in jsonObj:
            return self.send_json(
                {"response": "error", "errMsg": "Protocol Error (msg #%d): field 'code' (str) missing in 'code execution' request!" % jsonObj["seqNum"]})
        elif "codeId" not in jsonObj:
            return self.send_json(
                {"response": "error", "errMsg": "Protocol Error (msg #%d): field 'codeId' (uint) missing in 'code execution' request!" % jsonObj["seqNum"]})
        codeId = jsonObj["codeId"]
        if not isinstance(codeId, int) or codeId < 0:
            return self.send_json({"response": "error", "errMsg": "Protocol Error (msg #%d): given codeId must be of type uint!" % jsonObj["seqNum"]})

        # catch syntax errors in the code
        try:
            self.currentProject.handleExecuteCodeRequest(jsonObj["code"], codeId)
        # always just respond for code errors, never terminate
        except Exception as e:
            return self.send_json(
                {"response": "executed code", "codeId": codeId, "returned": "err", "errMsg": "Code Error (msg #%d): %s!" % (jsonObj["seqNum"], str(e))})
        else:
            return self.send_json({"response": "executed code", "codeId": codeId, "returned": "ok"})
    """

    # handles all types of client responses as a results of our requests
    def handle_response(self, json_obj):
        self.sanity_check_message(json_obj, [
            # no response field: just respond, no error
            ("response" in json_obj, ShineProtocol.PROTOCOL_ERROR_FIELD_MISSING, False, "response"),
            # an unknown response?
            (json_obj["response"] in ShineProtocol.protocolResponseLookup, ShineProtocol.PROTOCOL_ERROR_INVALID_FIELD_VALUE, False, "response"),
        ])

        res = json_obj["response"]

        # call the respective handler looked up in ProtocolResponseLookup
        handler = ShineProtocol.protocolResponseLookup[res]
        # check if we have to add 'self' to the json_obj
        if isinstance(handler, tuple) and handler[0] is True:  # handler[0]=True indicator (yes, we have to add the protocol)
            handler[1](json_obj, self)  # handler[1]=callable
        else:
            getattr(self, handler)(json_obj)

    # client answers our hello request with username, password, client version number, etc..
    def response_hello(self, json_obj):
        # TODO: for now: give sven a free pass
        if json_obj["userName"] == 'sven':
            self.factory.zodbRoot["Users"][json_obj["userName"]] = UserRecord(json_obj["userName"])

        self.sanity_check_message(json_obj, [
            (self.gotHelloResponse is False, ShineProtocol.PROTOCOL_ERROR_CUSTOM, True, "Got 'hello' response more than once from client!"),
            ("protocolVersion" in json_obj and isinstance(json_obj["protocolVersion"], int) and json_obj["protocolVersion"] > 0, ShineProtocol.PROTOCOL_ERROR_INVALID_FIELD_VALUE, True, "protocolVersion"),
            ("userName" in json_obj and isinstance(json_obj["userName"], str) and len(json_obj["userName"]) <= conf.SHINE_SERVER_MAX_LEN_USERNAME, ShineProtocol.PROTOCOL_ERROR_INVALID_FIELD_VALUE, True, "userName"),
            (json_obj["userName"] in self.factory.zodbRoot["Users"], ShineProtocol.PROTOCOL_ERROR_CUSTOM, True, "Unknown userName {:s}!".format(json_obj["userName"])),
        ])

        self.userName = json_obj["userName"]
        self.userRecord = self.factory.zodbRoot["Users"][self.userName]
        # self.userRecord = self.factory.ZODBRoot.Users[self.userName]  # ZODB!
        self.clientProtocolVersion = json_obj["protocolVersion"]
        self.gotHelloResponse = True
        # send the welcome notify to clarify that everything is ok
        self.send_json({"notify": "welcome"})

    # sends a pyrate-protocol compatible json message of the given type to the client
    # - all fields in the message have to be given in the jsonObj, except for origin, seqNum and msgType
    def send_json(self, json_obj):
        assert (isinstance(json_obj, dict))
        msg_type = "response" if "response" in json_obj else "request" if "request" in json_obj else "notify" if "notify" in json_obj else None
        assert msg_type
        # add some defaults to json object
        json_obj["origin"] = "server"
        json_obj["seqNum"] = self.nextSendSeqNum
        json_obj["msgType"] = msg_type
        self.nextSendSeqNum += 1
        try:
            msg = json.dumps(json_obj)
            log.debug("Will send json: %s" % msg)
        except:
            log.warning("In send_json: json_obj not a valid JSON message!")
            raise  # re-raise the exception
        else:
            # self.sendString(msg.encode('utf-8'))
            self.sendMessage(msg.encode('utf-8'))

    # can be called if the connection shows suspicious behavior from the client side (protocol aberrations, etc..)
    def abort(self, err_msg=None):
        self.transport.abortConnection()
        del (self.factory.protocols[self.id])
        if err_msg:
            log.error(err_msg)


class ShineProtocolFactory(WebSocketServerFactory):
    """
     A protocol factory from twisted
     - a new PyrateProtocol is created by this Factory every time a new client connects
     - the Factory is accessible for the Protocols via the self.factory field inside the Protocol objects
     - the Factory can hold persistent information even between client dis/reconnects as the Factory stays
       as long as this server runs; an example is the json formatted list of WorldManagers
    """

    # calculates some persistent stuff used by all Protocols (client connections)
    def __init__(self, reactor, address, root):  # , algo_dict, json_algo_dict):
        super().__init__(address)
        self.reactor = reactor
        self.zodbRoot = root
        # TODO: put these back??
        # self.algoDict = algo_dict
        # self.jsonAlgoList = json_algo_dict
        self.nextProtocolId = 0
        self.protocols = {}  # store our protocols by ID

    # this function is automatically defined via the c'tor given in static field 'protocol'
    def buildProtocol(self, _):  # _=factory
        # super().buildProtocol()
        _id = self.nextProtocolId
        self.nextProtocolId += 1
        protocol = ShineProtocol(_id, self, self.reactor)
        self.protocols[_id] = protocol
        log.debug("Added %d to protocols dict" % _id)
        return protocol

    def shutdown_all(self):
        for _id, protocol in self.protocols.items():
            if isinstance(protocol, ShineProtocol):
                log.debug("Closing protocol id=%d" % _id)
                protocol.transport.loseConnection()
