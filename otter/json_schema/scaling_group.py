"""
JSON Schemas for the scaling group - the launch config and the general scaling
group configuration.  There are also example configs and launch configs.
"""

# This is built using union types which may not be available in Draft 4
# see: http://stackoverflow.com/questions/9029524/json-schema-specify-field-is-
# required-based-on-value-of-another-field
# and https://groups.google.com/forum/?fromgroups=#!msg/json-
# schema/uvUFu6KE_xQ/O5aTuw5pRYEJ

# It is possible to create an invalid launch config (one that fails to create
# a server) - (1) we don't validate against nova yet, (2) even if it validates
# against nova at creation time, they may delete an image or network, and (3)
# it is possible for the user to create a server that is not connected to
# either the public net or the ServiceNet.

# TODO: we need some strategy for perhaps warning the user that their launch
# config has problems.  Perhaps a no-op validation endpoint that lists all the
# problems with their launch configuration, or perhaps accept the launch
# configuration and return a warning list of all possible problems.

launch_server = {
    "type": "object",
    "description": ("'Launch Server' launch configuration options.  This type "
                    "of launch configuration will spin up a next-gen server "
                    "directly with the provided arguments, and add the server "
                    "to one or more load balancers (if load balancer "
                    "arguments are specified."),
    "properties": {
        "type": {
            "enum": ["launch_server"],
        },
        "args": {
            "properties": {
                "server": {
                    "type": "object",
                    # The schema for the create server attributes should come
                    # from Nova, or Nova should provide some no-op method to
                    # validate creating a server.  Autoscale should not
                    # attempt to re-create Nova's validation.
                    "description": (
                        "Attributes to provide to nova create server: "
                        "http://docs.rackspace.com/servers/api/v2/"
                        "cs-devguide/content/CreateServers.html."
                        "Whatever attributes are passed here will apply to "
                        "all new servers (including the name attribute).")
                },
                "loadBalancers": {
                    "type": "array",
                    "description": (
                        "One or more load balancers to add new servers to. "
                        "All servers will be added to these load balancers "
                        "with their ServiceNet addresses, and will be "
                        "enabled, of primary type, and equally weighted. If "
                        "new servers are not connected to the ServiceNet, "
                        "they will not be added to any load balancers."),
                    # The network is ServiceNet because CLB doesn't work with
                    # isolated networks, and using public networks will just
                    # get the customer charged for the bandwidth anyway, so it
                    # doesn't seem like a good idea.
                    "required": False,
                    "minItems": 0,
                    "uniqueItems": True,
                    "items": {
                        "type": "object",
                        "description": (
                            "One load balancer all new servers should be "
                            "added to."),
                        "properties": {
                            # load balancer id's are NOT uuid's.  just an int.
                            "loadBalancerId": {
                                "type": "integer",
                                "description": (
                                    "The ID of the load balancer to which new "
                                    "servers will be added."),
                                "required": True
                            },
                            "port": {
                                "type": "integer",
                                "description": (
                                    "The port number of the service (on the "
                                    "new servers) to load balance on for this "
                                    "particular load balancer."),
                                "required": True
                            }
                        },
                        "additionalProperties": False
                    }
                },

            },
            "additionalProperties": False
        }
    }
}

# base launch config
launch_config = {
    "type": [launch_server],
    "properties": {
        "type": {
            "type": "string",
            "description": "The type of launch config this is.",
            "required": True
        },
        "args": {
            "type": "object",
            "required": True
        }
    },
    "additionalProperties": False
}


# Valid launch config examples - used for testing the schema and for
# documentation purposes
launch_server_config_examples = [
    {
        "type": "launch_server",
        "args": {
            "server": {
                "flavorRef": 3,
                "name": "webhead",
                "imageRef": "0d589460-f177-4b0f-81c1-8ab8903ac7d8",
                "OS-DCF:diskConfig": "AUTO",
                "metadata": {
                    "mykey": "myvalue"
                },
                "personality": [
                    {
                        "path": '/root/.ssh/authorized_keys',
                        "contents": (
                            "ICAgICAgDQoiQSBjbG91ZCBkb2VzIG5vdCBrbm93IHdoeSBp")
                    }
                ],
                "networks": [
                    {
                        "uuid": "11111111-1111-1111-1111-111111111111"
                    }
                ],
            },
            "loadBalancers": [
                {
                    "loadBalancerId": 2200,
                    "port": 8081
                }
            ]
        }
    },
    {
        "type": "launch_server",
        "args": {
            "server": {
                "flavorRef": 2,
                "name": "worker",
                "imageRef": "a09e7493-7429-41e1-8d3f-384d7ece09c0",
            },
            "loadBalancers": [
                {
                    "loadBalancerId": 441,
                    "port": 80
                },
                {
                    "loadBalancerId": 2200,
                    "port": 8081
                }
            ]
        }
    },
    {
        "type": "launch_server",
        "args": {
            "server": {
                "flavorRef": 2,
                "name": "worker",
                "imageRef": "a09e7493-7429-41e1-8d3f-384d7ece09c0",
            },
        }
    }
]


config = {
    "type": "object",
    "description": ("Configuration options for the scaling group, "
                    "controlling scaling rate, size, and metadata"),
    "properties": {
        "name": {
            "type": "string",
            "description": "Name of the scaling group.",
            "maxLength": 256,
            "required": True
        },
        "cooldown": {
            "type": "integer",
            "description": ("Cooldown period before more entities are added, "
                            "given in seconds.  This number must be an "
                            "integer."),
            "minimum": 0,
            "required": True
        },
        "minEntities": {
            "type": "integer",
            "description": ("Minimum number of entities in the scaling group. "
                            "This number must be an integer."),
            "minimum": 0,
            "required": True,
        },
        "maxEntities": {
            "type": ["integer", "null"],
            "description": ("Maximum number of entities in the scaling group. "
                            "Defaults to null, meaning no maximum.  When "
                            "given, this number must be an integer."),
            "minimum": 0,
            "default": None
        },
        "metadata": {
            "type": "object",
            "description": ("User-provided key-value metadata.  Both keys and "
                            "values should be strings not exceeding 256 "
                            "characters in length."),
            "patternProperties": {
                "^.{0,256}$": {
                    "type": "string",
                    "maxLength": 256
                }
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}

# Valid config examples
config_examples = [
    {
        "name": "webheads",
        "cooldown": 30,
        "minEntities": 1
    },
    {
        "name": "workers",
        "cooldown": 60,
        "minEntities": 5,
        "maxEntities": 100,
        "metadata": {
            "firstkey": "this is a string",
            "secondkey": "1",
        }
    }
]


policy_schema = {
    "type": "object",
    "description": "A policy for scaling the group.",
    "properties": {
        "name": {
            "type": "string",
            "description": "Name of the scaling policy.",
            "maxLength": 256,
            "required": True
        },
        "cooldown": {
            "type": "integer",
            "description": ("Cooldown period before more entities are added,"
                            "given in seconds."
                            "This number must be an integer."),
            "minimum": 0,
            "required": True
        },
        "change": {
            "type": ["integer", "null"],
            "description": ("Scale the group by this number of entities."
                            "This number must be an integer."),
            "minimum": 0,
            "default": None
        },
        "changePercent": {
            "type": ["integer", "null"],
            "description": ("Scale the group by this percent."
                            "This number must be an integer."),
            "minimum": 0,
            "default": None
        },
        "steadyState": {
            "type": ["integer", "null"],
            "description": ("Set the group to this number of entities."
                            "This number must be an integer."),
            "minimum": 0,
            "default": None
        }
    },
    "additionalProperties": False
}

policy_examples = [
        {
            "id": 1,
            "name": "scale up by one server",
            "change": 1,
            "cooldown": 150
        },
        {
            "id": 2,
            "name": "scale up ten percent",
            "changePercent": 10,
            "cooldown": 150
        },
        {
            "id": 3,
            "name": "scale down one server",
            "change": -1,
            "cooldown": 150
        },
        {
            "id": 4,
            "name": "scale down ten percent",
            "changePercent": -10,
            "cooldown": 150
        }
    ]
