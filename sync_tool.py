#!/usr/bin/python3

import argparse
import sys
import json
import os
import tempfile
import logging
from logging import handlers
import subprocess
from shutil import rmtree

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = handlers.SysLogHandler(address = '/dev/log')
logger.addHandler(handler)
formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

FILENAME = "instances.json"
USER = "sshsyncrobot"

def create_if_not_exists():
    if not os.path.exists(FILENAME):
        h = { "instances" : [] }
        write_json(h)

def write_json(h):
    new_json_blob = json.dumps(h, sort_keys=True, indent=4)
    with open(FILENAME, "w") as f:
        f.write(new_json_blob)

def read_json():
    h = None
    with open(FILENAME, "r") as f:
        h = json.loads(f.read())
    return h

def cmd_add(ipaddr):
    create_if_not_exists()
    h = read_json()
    h[u'instances'].append(ipaddr)
    write_json(h)

def cmd_del(ipaddr):
    h = None
    h = read_json()
    try:
        h[u'instances'].remove(ipaddr)
        write_json(h)
    except ValueError:
        sys.stderr.write("ip address {} not in instances.json\n".format(ipaddr))
        sys.exit(1)


def test_host_port(host, port):
    cmd = "timeout 1 nc -X 5 -x YOURPROXYSERVER -z '%s' '%d'" % (host, port)
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (stdout, stderr) = p.communicate()
    if p.returncode != 0:
        logger.error("Cannot connect to %s:%d" % (host, port))
        return False
    return True


def push_cmd(keypath):
    h = read_json()
    d = tempfile.mkdtemp("-synctool")
    try:
        logging.debug("tempdir: {}".format(d))
        cmd = "git clone https://YOURSSHGITREPO"
        logging.info("executing: {}".format(cmd))
        p = subprocess.Popen(cmd, shell=True, cwd=d,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            logger.error("git: {}".format(stdout))
            loger.error("git returned {}! aborting\n".format(return_code))
            sys.exit(1)
        for instance in h[u'instances']:
            if not test_host_port(instance, 22):
                continue
            ssh_options = [
                'UserKnownHostsFile=/dev/null',
                'StrictHostKeyChecking=no',
                'ProxyCommand="nc -X 5 -x YOURPROXY %h %p"',
                'IdentityFile={}'.format(keypath),
                'IdentitiesOnly=True',
                'LogLevel=INFO',
                'BatchMode=yes'
                ]
            options = ""
            for option in ssh_options:
                options += " -o{}".format(option)
            env = {
                'GIT_SSH_COMMAND' : 'ssh ' + options #+ ' $*'
                }
            logger.debug("env: {}".format(env))
            cmd = "git push --verbose --force {}@{}:/var/lib/git/sshKeys master".format(USER, instance)
            logger.info("executing: {}".format(cmd))
            directory = os.path.join(d, "sshkeys")
            p = subprocess.Popen(cmd, shell=True, cwd=directory, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (stdout, stderr) = p.communicate()
            return_code = p.returncode
            if return_code != 0:
                logger.error("git: {}".format(stdout))
                sys.stderr.write("git returned {}, but continuing anyway\n".format(return_code))
    finally:
        rmtree(d)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('cmd', choices=['add', 'del', 'push'])
    parser.add_argument('-i', help='ip address of aws machine', dest='ipaddr')
    parser.add_argument('-k', help='path to private key for push', dest='keypath')
    args = parser.parse_args()

    if args.cmd == "add":
        if not args.ipaddr:
            sys.stderr.write("ipaddr required to for add\n")
            sys.exit(1)
        cmd_add(args.ipaddr)
    elif args.cmd == "del":
        if not args.ipaddr:
            sys.stderr.write("ipaddr required to for del\n")
            sys.exit(1)
        cmd_del(args.ipaddr)
    elif args.cmd == "push":
        if not args.keypath:
            sys.stderr.write('keypath is required for push\n')
            sys.exit(1)
        push_cmd(args.keypath)
