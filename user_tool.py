#!/usr/bin/python

import argparse
import sys
import json
import os
import io
import stat
import logging
import subprocess
import base64

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

supportedTags = ['redteam', 'core', 'volunteer', 'infra']

def parse_json(json_file):
    h = None

    try:
        with open(json_file, "r") as f:
            h = json.loads(f.read())
    except FileNotFoundError:
        sys.stderr.write("json file %s not found.  Use new to make it\n" % json_file)
        sys.exit(1)
    return h

def write_json(json_file, data):
    new_json_blob = json.dumps(data, sort_keys=True, indent=4)
    with open(json_file, "w") as f:
        f.write(new_json_blob)

def run(cmd):
    logger.info("running '%s'" % cmd)
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError:
        logger.error("cmd '%s' failed" % cmd)
        sys.exit(1)

def username_collision(h, u):
    username = u.encode('utf-8')
    usernames = []
    for u in h[u"users"]:
        usernames.append(u[u"username"])
    if username in usernames:
        return True
    return False

def username_validation(username):
    if username[0].isdigit():
        sys.stderr.write("Usernames may not start with a digit\n")
        return False
    if " " in username:
        sys.stderr.write("Usernames may not have spaces\n")
        return False
    return True

def name_validation(name):
    badcars = [",", ":", "="]
    for bad in badcars:
        if (bad in name):
            sys.stderr.write("invalid char in username: '%s'\n" % bad)
            return False
    return True

def authorized_keys_validation(keys):
    if "PRIVATE" in keys:
        sys.stderr.write("That's a private key.  Use a public key\n")
        return False
    return True

def tag_validation(tags):
    for tag in tags:
        if tag not in supportedTags:
            sys.stderr.write("tag %s not supported\n" % tag)
            sys.exit(1)
    if (len(tags) == 1) and (tags[0] == 'volunteer'):
        sys.stderr.write("volunteer without redteam is not supported\n")
        sys.exit(1)

def new_cmd(json_file):
    h = { 'users' : [] }
    write_json(json_file, h)

def add_cmd(json_file, name, username, authorized_keys, tags, shell):
    uid = 6000 # start at uid 6000
    h = parse_json(json_file)

    if username_collision(h, username):
        sys.stderr.write("usenrame {} is already in the set of users\n".format(username))
        sys.exit(1)

    if not username_validation(username):
        sys.exit(1)

    keys = authorized_keys.read().decode("utf-8")
    if not authorized_keys_validation(keys):
        sys.exit(1)

    # find last uid in file
    uids = []
    for user in h["users"]:
        uids.append(user["uid"])

    uids.sort()
    if uids:
        uid = uids[-1]+1

    if not tags:
        tags = ['volunteer', 'redteam']

    tag_validation(tags)

    based = base64.b64encode(keys)
    h["users"].append({'uid': uid,
                       'name' : name,
                       'username' : username,
                       'authorized_keys' : based,
                       'shell': shell,
                       'tags' : tags})
    write_json(json_file, h)
    return uid

def write_authorized_keys(user):
    import pwd
    name = user["name"]
    username = user["username"]
    uid = user["uid"]
    pwent = pwd.getpwuid(uid)
    dotssh = os.path.expanduser("~%s/.ssh" % username)
    authorized_keys_file = os.path.join(dotssh, "authorized_keys")
    if not os.path.isdir(dotssh):
            os.mkdir(os.path.expanduser(dotssh), stat.S_IRWXU)
    with open(authorized_keys_file, "wb") as f:
        f.write(base64.b64decode(user["authorized_keys"]))
    os.chmod(authorized_keys_file, stat.S_IWUSR | stat.S_IRUSR)
    os.chown(dotssh, pwent.pw_uid, pwent.pw_gid)
    os.chown(authorized_keys_file, pwent.pw_uid, pwent.pw_gid)

def apply_cmd(json_file, tags):
    utf8_tags = list(map(lambda s: unicode(s), tags))
    import pwd
    import grp
    REDTEAMSUDOERS = "/etc/sudoers.d/redteam"
    if not os.path.exists(REDTEAMSUDOERS):
        with open (REDTEAMSUDOERS, "w+") as f:
            f.write("%redteam   ALL=(ALL) NOPASSWD:ALL\n")
            os.fchmod(f.fileno(), stat.S_IREAD)
    try:
        grp.getgrnam("redteam")
    except KeyError:
        run("groupadd redteam")
    try:
        grp.getgrnam("infra")
    except KeyError:
        run("groupadd infra")
    h = parse_json(json_file)
    for user in h["users"]:
        uid = user["uid"]
        tags = set(user["tags"])
        shell = user["shell"]
        try:
            tags_in_common = tags.intersection(utf8_tags)
            if not tags_in_common:
               continue

            pwent = pwd.getpwuid(uid)

            # users exists, what changes are necessary
            username = user["username"]
            home = "/home/%s" % username
            name = user["name"]

            # see 8 usermod.  If username is changed, then nothing else will be changed
            cmd = "usermod -l '%s' '%s'" % (username, pwent.pw_name)
            run(cmd)
            cmd = "usermod -m -d '%s' '%s'" % (home, username)
            run(cmd)
            cmd = "chfn -f '%s' %s" % (name, username)
            run(cmd)
            tags_in_common = tags.intersection(utf8_tags)
            if (not user["authorized_keys"]):
                cmd = "usermod -p '!' '%s'" % username
                run(cmd)
                cmd = "chsh -s '/bin/false' %s" % username
                run(cmd)
            else:
                grp = []
                # user is not disabled
                cmd = "chsh -s '%s' %s" % (shell, username)
                run(cmd)
                cmd = "usermod -p '*' '%s'" % username
                run(cmd)
                if "redteam" in tags:
                    grp.append("redteam")
                if "infra" in tags:
                    grp.append("infra")
                grpstring = ""
                if grp:
                    grpstring = "-G " + ",".join(grp)
                    cmd = "usermod %s %s" % (grpstring, username)
                run(cmd)
            write_authorized_keys(user)

        except KeyError:
            # user needs creation
            logger.info("uid '%s' doesn't exist" % uid)
            username = user["username"]
            name = user["name"]
            uid = user["uid"]
            grp = []
            if "redteam" in tags:
                grp.append("redteam")
            if "infra" in tags:
                grp.append("infra")
            grpstring = ""
            if grp:
                grpstring = "-G " + ",".join(grp)
            cmd = "useradd -m %s -s %s -u %d -U -p '*' -c '%s' '%s'" % (grpstring, shell, uid, name, username)
            run(cmd)
            write_authorized_keys(user)

def mod_cmd(json_file, uid, name, username, authorized_keys, tags, shell):
    h = parse_json(json_file)
    u = None
    for user in h["users"]:
        if user["uid"] == uid:
            u = user
            break
    if not u:
        sys.stderr.write("could not find uid %d in json\n" % uid)
        sys.exit(1)
    if username and username_collision(h, username):
        sys.stderr.write("username {} is already in the set of users\n".format(username))
        sys.exit(1)
    if username and not username_validation(username):
        sys.exit(1)
    if tags:
        tag_validation(tags)
    if name:
        u["name"] = name
    if username:
        u["username"] = username
    if authorized_keys:
        u["authorized_keys"] = base64.b64encode(authorized_keys.read()).decode("utf-8")
    if tags:
        u['tags'] = tags
    if shell:
        u['shell'] = shell
    write_json(json_file, h)

def del_cmd(json_file, uid):
    h = parse_json(json_file)
    u = None
    if not uid:
        sys.stderr.write("you must specify a uid to disable\n")
        sys.exit(1)
    for user in h["users"]:
        if user["uid"] == uid:
            u = user
            u["authorized_keys"] = ""
            write_json(json_file, h)
    if not u:
        sys.stderr.write("could not find uid %d in json file\n" % uid);
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('cmd', choices=['new', 'apply', 'add', 'del', 'mod'])

    parser.add_argument('-j', help='json file', type=str,
                        dest='json_file', required=True)
    parser.add_argument('--uid', help='uid to use', type=int, dest='uid')
    parser.add_argument('-u', help='username to use', type=str, dest='username')

    parser.add_argument('-n', help='name of person', type=str, dest='name')
    parser.add_argument('-k', help='authorized_keys filename', type=argparse.FileType('rb'),
                        dest='authorized_keys')
    parser.add_argument('-t', help='tags for user. If using multiple tags, supply -t for each.', type=str, action='append', dest='tags')
    parser.add_argument('-s', help='shell for the user', type=str, dest='shell', default='/bin/bash')
    args = parser.parse_args()

    if args.username and " " in args.username:
        sys.stderr.write("you can't have spaces in a username\n");
        sys.exit(1)

    if args.cmd == 'new':
        new_cmd(args.json_file)

    elif args.cmd == 'apply':
        if os.getuid() != 0:
            sys.stderr.write("You must be root to apply\n")
            sys.exit(1)
        if not args.tags:
            sys.stderr.write("You must supply tags\n")
            sys.exit(1)
        apply_cmd(args.json_file, args.tags)

    elif args.cmd == 'add':
        if not args.username or not args.name or not args.authorized_keys:
            sys.stderr.write("You must supply username, name, and authorized_keys\n")
            sys.exit(1)
        if args.uid:
            sys.stderr.write("UID should not be specificed with the add cmd\n")
            sys.exit(1)
        uid = add_cmd(args.json_file, args.name, args.username,
                      args.authorized_keys, args.tags, args.shell)
        print("uid:", uid)

    elif args.cmd == 'del':
        if not args.uid:
            sys.stderr.write("UID must be specified with the del cmd\n")
            sys.exit(1)
        del_cmd(args.json_file, args.uid)

    elif args.cmd == 'mod':
        if not args.uid:
            sys.stderr.write("UID must be specified with the mod cmd\n")
            sys.exit(1)
        mod_cmd(args.json_file, args.uid, args.name, args.username,
                args.authorized_keys, args.tags, args.shell)
    print("Have a nice day")
    sys.exit(0)

#
# Editor modelines  -  https://www.wireshark.org/tools/modelines.html
#
# Local variables:
# c-basic-offset: 4
# indent-tabs-mode: nil
# End:
#
# vi: set shiftwidth=4 expandtab:
# :indentSize=4:noTabs=true:
#
