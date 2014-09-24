#!/usr/bin/python

# Copyright (C) 2014 Felix Geyer <debfx@fobos.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 or (at your option)
# version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import apt
import apt.progress.base
import apt.progress.text
import apt_pkg
import fnmatch
import os
import sys

if len(sys.argv) <= 1:
    sys.exit(2)

if sys.argv[1] == "--help":
    print >> sys.stderr, "Upgrades a selected set of packages and makes sure no other packages are affected."
    print >> sys.stderr, "Returns 0 on success, 1 on error and 2 if none of the specified packages are upgradable."

    print >> sys.stderr, "Usage: " + sys.argv[0]              + " [pkg],[pkg],..."
    print >> sys.stderr, "       " + (" " * len(sys.argv[0])) + " [pkg] [pkg] ...\n"

    print >> sys.stderr, "[pkg] is a package name without the architecture. \"*\" wildcards are supported."
    print >> sys.stderr, "      It's also possible to include all binary packages from a source package"
    print >> sys.stderr, "      using the src:<pkg> syntax.\n"

    print >> sys.stderr, "Examples:"
    print >> sys.stderr, "  " + sys.argv[0] + " \"curl,libcurl*\""
    print >> sys.stderr, "  " + sys.argv[0] + " src:curl"
    print >> sys.stderr, "  " + sys.argv[0] + " mutt rsyslog"

    sys.exit(0)

packages_input = sys.argv[1].split(",") + sys.argv[2:]
packages_bin = []
packages_src = []

for pkg in packages_input:
    if pkg.startswith("src:"):
        packages_src.append(pkg[4:])
    else:
        packages_bin.append(pkg)

os.environ["DEBIAN_FRONTEND"] = "noninteractive"
os.environ["APT_LISTCHANGES_FRONTEND"] = "mail"

cache = apt.Cache()

apt_pkg.config["DPkg::Options::"] = "--force-confold"

def matches_input_pkg(pkg):
    for input in packages_bin:
        if fnmatch.fnmatchcase(pkg.shortname, input):
            return True

    source = pkg.candidate.source_name
    if source:
        for input in packages_src:
            if fnmatch.fnmatchcase(source, input):
                return True

    return False

def is_package_held_back(pkg):
    # resort to internal API as apt.Package doesn't expose this
    return pkg._pkg.selected_state == apt_pkg.SELSTATE_HOLD

for pkg in cache:
    if pkg.is_upgradable and not is_package_held_back(pkg):
        if matches_input_pkg(pkg):
            try:
                pkg.mark_upgrade()
            except SystemError, e:
                print >> sys.stderr, "Unable to upgrade " + pkg.name + ":\n" + str(e)
                sys.exit(1)

if not cache.get_changes():
    # nothing to do
    sys.exit(2)

for pkg in cache.get_changes():
    if not matches_input_pkg(pkg):
        print >> sys.stderr, "No safe upgrade possible. State of package '" + pkg.name + "' would be changed."
        sys.exit(1)

result = cache.commit(apt.progress.text.AcquireProgress(),
                      apt.progress.base.InstallProgress())

if result:
    sys.exit(0)
else:
    sys.exit(1)
