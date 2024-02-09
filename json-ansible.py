import json
import base64

# read JSON
with open('users.json', 'r') as json_file:
    data = json.load(json_file)

users = data['users']
groups = set()

# ansible playbook header
playbook_content = """---
- name: Ensure users are configured
  hosts: all
  become: true
  tasks:
    - name: allow group 'redteam' to sudo
      copy:
        dest: /etc/sudoers.d/redteam
        owner: root
        mode: 0600
        content: |
          %redteam ALL=(ALL) NOPASSWD:ALL
    - name: Add groups
      group:
        name: "{{ item }}"
        state: present
      loop:
        - redteam
"""

for user in users:
    for tag in user['tags']:
        if tag != 'redteam':
          groups.add(tag)

# create the groups
for group in groups:
    playbook_content += f"""        - {group}\n"""


for user in users:
    if (len(user['authorized_keys']) > 0):
        authorized_key = base64.b64decode(user['authorized_keys']).decode('utf-8')
        user_groups = ', '.join([group for group in user['tags'] if not group == 'redteam']).strip()
        playbook_content += f"""
    - name: Add user {user['username']}
      ansible.builtin.user:
        name: {user['username']}
        comment: "{user['name']}"
        shell: {user['shell']}
        uid: {user['uid']}
        password: "*"
        state: present
        group: redteam
        groups: {user_groups}

    - name: Add ssh public key for {user['username']}
      ansible.posix.authorized_key:
        user: {user['username']}
        state: present
        exclusive: true
        key: |
          {authorized_key}
"""

# print(playbook_content)

# write the playbook content to a YML file
with open('users.yml', 'w') as playbook:
    playbook.write(playbook_content)

print("Ansible playbook 'users.yml' has been created.")
