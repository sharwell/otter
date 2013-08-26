
from ConfigParser import SafeConfigParser
from os import environ
from sys import exit

cfg = SafeConfigParser()

with open('preprod.config.template') as f:
    cfg.read(f)

envvars = [
    'CC_USER_PASSWORD',
    'CC_USER_API_KEY',
    'CC_NON_AS_PASSWORD',
]

def env_not_set(envvar):
    if environ.get(envvar):
        return False
    else:
        return True

unset_vars = filter(env_not_set, envvars)
if unset_vars:
    for unset_var in unset_vars:
        print("Must export {} environment variable".format(unset_var))
    exit(1)

cfg.set('user', 'password', environ['CC_USER_PASSWORD'])
cfg.set('user', 'api_key', environ['CC_USER_API_KEY'])
cfg.set('user', 'non_autoscale_password', environ['CC_NON_AS_PASSWORD'])

with open('preprod.config', 'w') as f:
    cfg.write(f)
