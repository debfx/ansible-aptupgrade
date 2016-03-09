# Ansible Module: Selectively upgrade packages on Debian

An Ansible module that upgrades a specific set of packages on Debian systems.
It will only try to upgrade the packages you specify. If other packages are
pulled in by the upgrade it will abort.

## Requirements

The package python-apt needs to be installed on target hosts.

## Module variables

The module has the following parameters:

- update_cache (bool, defaults to False)

  Run apt-get update before upgrading packages.

- packages

  A comma separated list of binary packages to upgrade.

- sources

  A comma separated list of source packages to upgrade.

## Example invocations

- ansible -M . -m apt_upgrade -a "update_cache=True packages=mutt,rsyslog"
- ansible -M . -m apt_upgrade -a "update_cache=True packages=curl,libcurl*"
- ansible -M . -m apt_upgrade -a "update_cache=False sources=curl"
