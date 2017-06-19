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

- origins

  A comma separated list of origins where are packages are upgraded from.
  Remember to escape commas in a single origin filter ("," -> "\,")

  The accepted keywords are:
  - a,archive,suite (eg, "stable")
  - c,component     (eg, "main", "contrib", "non-free")
  - l,label         (eg, "Debian", "Debian-Security")
  - o,origin        (eg, "Debian", "Unofficial Multimedia Packages")
  - n,codename      (eg, "jessie", "jessie-updates")
  - site            (eg, "http.debian.net")

  The following variables are substituted:
  - {distro_id}        Installed distro name (eg. "Debian")
  - {distro_codename}  Installed codename (eg, "jessie")

  Examples:
  - origin=Debian\,codename={distro_codename}\,label=Debian-Security
  - o=Debian\,n=jessie

- security (bool, defaults to False)

  Shortcut for adding the distro provided security repo to origins.
  Works only on Debian and Ubuntu.

- official (boot, defaults to False)

  Shortcut for adding the distro provided release and update repo to origins.
  Works only on Debian and Ubuntu.
  Notably this doesn't include backports.

## Example invocations

- ansible -M . -m apt_upgrade -a "update_cache=True packages=mutt,rsyslog"
- ansible -M . -m apt_upgrade -a "update_cache=True packages=curl,libcurl*"
- ansible -M . -m apt_upgrade -a "update_cache=False sources=curl"
