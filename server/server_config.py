"""
 ---------------------------------------------------------------------------------
 a simple shine server config file for server constants and other settable
 parameters

 by Code Sourcerer
 (c) 2017 ducandu GmbH
 ---------------------------------------------------------------------------------
"""


# general server setup
SHINE_PROTOCOL_VERSION = 1  # 1=v0.0.1; 14=v0.0.14; 100=v0.1.0; 10000=v1.0.0
SHINE_SERVER_MAX_LEN_MESSAGE = 65536-1  # max len of an incoming json string (not counting the leading int32 (4-byte) msg-len marker)

# project settings
SHINE_SERVER_MAX_LEN_USERNAME = 32  # the max len of a username for shine client/server sessions
SHINE_SERVER_MAX_LEN_PROJECT_NAME = 32  # the max len of a name for a Project (projects are stored under a unique-per-user name)
SHINE_SERVER_MAX_ALGORITHM_NAME = 32  # the max len of a name for an Algorithm object (worlds are stored under a unique name per-user-per-project)
SHINE_SERVER_MAX_LEN_WORLD_NAME = 32  # the max len of a name for a World object (algorithms are stored under a unique name per-user-per-project)

