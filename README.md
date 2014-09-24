# Ansible Role: Selectively upgrade packages on Debian

An Ansible role that upgrades a specific set of packages on Debian systems.

## Requirements

The package python-apt needs to be installed on target hosts.

## Role variables

The role has two parameters:

- update (bool, defaults to False)

  Run apt-get update before upgrading packages.

- packages (required)

  A comma (or space) separated list of packages to upgrade.
  It supports globbing and selecting whole source packages through src:&lt;name&gt;.

  The role will abort before upgrading if other packages would have to be
  upgraded or installed.

## Example playbook

    - hosts: all
      gather_facts: False
      roles:
        - aptupgrade

## Example invocations

- ansible-playbook upgrade.yml -e "update=True packages=mutt,rsyslog"
- ansible-playbook upgrade.yml -e "update=True packages=curl,libcurl*"
- ansible-playbook upgrade.yml -e "update=False packages=src:curl"
