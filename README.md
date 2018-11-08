# WTF

This project houses reference deployment recipies that can be used to build Red Team Infrastructure. As such, there are no security guarantees or promises. Use at your own risk.

# Contributing

See `contributing.md`

## What

This tool is for the maintenance of users and ssh keys for our
operations.  The tool encodes data into a json file.  It can also use
the json file to change the current state of the system to include the
users in the json file.

Note the UID is the consistent thing between runs.  Never delete a UID
from the json file.

# I Just Want to Add my SSH Key

**AUTHORIZED_KEYS ARE YOUR PUBLIC KEYS OR KEY, NEVER A PRIVATE KEY**

**DO NOT COMMIT WITH GITHUB ENTERPRISE**

Run this or have a friend do it:

1. ```git config user.name "<USERID>" && git config user.email "<EMAIL>"```
1. ```user_tool.py add -j users.json -u '<USERID>' -n '<YOUR NAME>' -k <PATH OF AUTHROZIED_KEYS> [-t <tag>] [-t <tag>] [-s <shell>]```
1. ```git add users.json```
1. ```git commit -m 'adding <YOUR NAME>'```
1. ```git push origin master```

## user attributes
* uid
* name
* username
* authorized_keys
* tags

### Tags

The following tags are supported

- `redteam` signifies the public key belongs to a member of the redteam
- `core` signifies redteam core
- `volunteer` signifies redteam volunteer

The default tags are `redteam`, `volunteer` if `-t` is not specified.

Multiple tags will be needed for some users in which case `-t` will be issued twice. Example: `-t redteam -t volunteer`.

## Example json

```
{
    "users" : [
	{
	    "uid" : 6001,
	    "name" : "Some Name 1",
	    "username" : "somename1",
	    "authorized_keys" : "BASE64 GARBAGE",
		"shell" : "/bin/bash",
		"tags" : [
            "volunteer" ,
            "redteam"
        ],
	},
	{
	    "uid" : 6002,
	    "name" : "Some Name 2",
	    "username" : "somename2",
	    "authorized_keys" : "BASE64 GARBAGE"
		"shell" : "/bin/bash",
		"tags" : [
            "core",
            "redteam"
       ]
	}
}
```

# Usage Modes

* ```user_tool.py new -j <json_file>```

Create a new json file with no users in it

* ```user_tool.py apply -j <json_file> -t <tag> [-t <tag>]```

Make this system match the configuration in the json file

* ```user_tool.py add -j <json_file> -n <name> -u <username> -k <authorized_keys_file> [-t <tag>] [-s <shell>]```

Add a user to the json file.  The allocated UID is returned.

* ```user_tool.py del -j <json_file> --uid <uid>```

Deactivate a user from the json file.  This just clears the authorized keys.  Users are not deleted, but rather are unable to log in.

* ```user_tool.py mod -j <json_file> --uid <uid> [-n <name>] [-u <username>] [-k <authorized_keys_file>]  [-t <tag>]```

Modify a user.  This can be name, keys, username, or tags.

Add an ssh key for a user.

1.  Find the authorized keys attribute in the users.json for the user in question and paste into a file called based.
1.  ```cat based | base64 -d > authorized_keys```
1.  add your public key to authorized_keys
1.  ```user_tool.py mod -j <json_file> --uid <uid> -k ./authorized_keys```

# sync_tool

This tool is a script that is run via your internal host that syncronizes the ssh repo to homebases that are deployed in AWS.  This tool is executed every 30 minutes via cron as the sshsyncrobot user.  This user has a public key that is stored in the users.json such that it can push to AWS.  The shell for this user is git-shell, however.  Due to the way groups are done, which should probably be improved in the future, this user is a redteam user on homebase, which does give it sudo access.  However, git-shell keeps it from executing commands.  The invocation of this tool is similar to `user_tool.py` above.

* Add a homebase

```sync_tool.py add -i <ipaddr>```

* Del a homebase

```sync_tool.py del -i <ipaddr>```

* Push to all the hosts in instances.json

Note that this logs into syslog.

```sync_tool.py push -k <keypath>```

## Running Automatically
Put the following in the sshsyncrobot user's crontab

```*/30 * * * * ~/sync_tool.py push -k ~/.ssh/id_ed25519```
