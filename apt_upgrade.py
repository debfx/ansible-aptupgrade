#!/usr/bin/python

# Copyright (c) 2014-2016 Felix Geyer <debfx@fobos.de>
# Copyright (c) 2005-2015 Canonical Ltd
# Copyright (c) 2012, Flowroute LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import fcntl
import fnmatch
import os

HAS_PYTHON_APT = True
try:
    import apt
    import apt.progress.base
    import apt.progress.text
    import apt_pkg
except ImportError:
    HAS_PYTHON_APT = False

LOGFILE_DPKG = "/var/run/ansible_apt_upgrade_dpkg.log"
_DISTRO_CODENAME = None
_DISTRO_ID = None


class Error(Exception):
    pass


class LogInstallProgress(apt.progress.base.InstallProgress):
    def __init__(self, logfile_dpkg):
        apt.progress.base.InstallProgress.__init__(self)
        self.logfile_dpkg = logfile_dpkg

    def _fixup_fds(self):
        required_fds = [0, 1, 2,  # stdin, stdout, stderr
                        self.writefd,
                        self.write_stream.fileno(),
                        self.statusfd,
                        self.status_stream.fileno()
                        ]
        # ensure that our required fds close on exec
        for fd in required_fds[3:]:
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
        # close all fds
        proc_fd = "/proc/self/fd"
        if os.path.exists(proc_fd):
            error_count = 0
            for fdname in os.listdir(proc_fd):
                try:
                    fd = int(fdname)
                except Exception as e:
                    print("ERROR: can not get fd for '%s'" % fdname)
                if fd in required_fds:
                    continue
                try:
                    os.close(fd)
                    # print("closed: ", fd)
                except OSError as e:
                    # there will be one fd that can not be closed
                    # as its the fd from pythons internal diropen()
                    # so its ok to ignore one close error
                    error_count += 1
                    if error_count > 1:
                        print("ERROR: os.close(%s): %s" % (fd, e))

    def _redirect_stdin(self):
        REDIRECT_INPUT = os.devnull
        fd = os.open(REDIRECT_INPUT, os.O_RDWR)
        os.dup2(fd, 0)

    def _redirect_output(self):
        logfd = self._get_logfile_dpkg_fd()
        os.dup2(logfd, 1)
        os.dup2(logfd, 2)

    def _get_logfile_dpkg_fd(self):
        logfd = os.open(
            self.logfile_dpkg, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o640)
        try:
            adm_gid = grp.getgrnam("adm").gr_gid
            os.fchown(logfd, 0, adm_gid)
        except (KeyError, OSError):
            pass
        return logfd

    def update_interface(self):
        # call super class first
        apt.progress.base.InstallProgress.update_interface(self)

    def _log_in_dpkg_log(self, msg):
        logfd = self._get_logfile_dpkg_fd()
        os.write(logfd, msg.encode("utf-8"))
        os.close(logfd)

    def fork(self):
        pid = os.fork()
        if pid == 0:
            self._fixup_fds()
            self._redirect_stdin()
            self._redirect_output()
        return pid


def get_distro_codename():
    global _DISTRO_CODENAME

    if _DISTRO_CODENAME is None:
        try:
            _DISTRO_CODENAME = subprocess.check_output(["lsb_release", "-c", "-s"], universal_newlines=True).strip()
        except (OSError, subprocess.CalledProcessError) as e:
            raise Error("Failed to run lsb_release: " + str(e))

    return _DISTRO_CODENAME

def get_distro_id():
    global _DISTRO_ID

    if _DISTRO_ID is None:
        try:
            _DISTRO_ID = subprocess.check_output(["lsb_release", "-i", "-s"], universal_newlines=True).strip()
        except (OSError, subprocess.CalledProcessError) as e:
            raise Error("Failed to run lsb_release: " + str(e))

    return _DISTRO_ID

def substitute(line):
    """ substitude known mappings and return a new string
    """
    value = line.replace("{distro_codename}", get_distro_codename())
    value = value.replace("{distro_id}", get_distro_id())
    return value

def match_whitelist_string(whitelist, origin):
    """
    take a whitelist string in the form "origin=Debian,label=Debian-Security"
    and match against the given python-apt origin. A empty whitelist string
    never matches anything.
    """
    whitelist = whitelist.strip()
    if whitelist == "":
        # empty match string matches nothing
        return False
    res = True
    # make "\," the html quote equivalent
    whitelist = whitelist.replace("\,", "%2C")
    for token in whitelist.split(","):
        # strip and unquote the "," back
        try:
            (what, value) = [s.strip().replace("%2C", ",")
                            for s in token.split("=")]
        except ValueError:
            return False
        # support substitution here as well
        value = substitute(value)
        # first char is apt-cache policy output, send is the name
        # in the Release file
        if what in ("o", "origin"):
            res &= fnmatch.fnmatch(origin.origin, value)
        elif what in ("l", "label"):
            res &= fnmatch.fnmatch(origin.label, value)
        elif what in ("a", "suite", "archive"):
            res &= fnmatch.fnmatch(origin.archive, value)
        elif what in ("c", "component"):
            res &= fnmatch.fnmatch(origin.component, value)
        elif what in ("site",):
            res &= fnmatch.fnmatch(origin.site, value)
        elif what in ("n", "codename",):
            res &= fnmatch.fnmatch(origin.codename, value)
        else:
            return False

    return res

def is_allowed_origin(ver, allowed_origins):
    if not ver:
        return False
    for origin in ver.origins:
        for allowed in allowed_origins:
            if match_whitelist_string(allowed, origin):
                return True
    return False

def matches_input_pkg(pkg, allowed_packages, allowed_sources, allowed_origins):
    for allowed in allowed_packages:
        if fnmatch.fnmatchcase(pkg.shortname, allowed):
            return True

    source = pkg.candidate.source_name
    if source:
        for allowed in allowed_sources:
            if fnmatch.fnmatchcase(source, allowed):
                return True

    if is_allowed_origin(pkg.candidate, allowed_origins):
        return True

    return False

def is_package_held_back(pkg):
    # resort to internal API as apt.Package doesn't expose this
    return pkg._pkg.selected_state == apt_pkg.SELSTATE_HOLD

def main():
    module = AnsibleModule(
        argument_spec = dict(
            update_cache = dict(default=False, aliases=['update-cache'], type='bool'),
            cache_valid_time = dict(type='int'),
            packages = dict(default=[], type='list'),
            sources = dict(default=[], type='list'),
            origins = dict(default=[], type='list'),
            security = dict(default=False, type='bool'),
        ),
        required_one_of = [['packages', 'sources', 'origins', 'security']],
        supports_check_mode = True
    )

    if not HAS_PYTHON_APT:
        module.fail_json(msg="python-apt must be installed to use check mode. If run normally this module can autoinstall it")

    params = module.params

    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    os.environ["APT_LISTCHANGES_FRONTEND"] = "mail"
    cache = apt.Cache()
    apt_pkg.config["DPkg::Options::"] = "--force-confold"

    if module.check_mode:
        apt_pkg.config.set("Debug::pkgDPkgPM", "1")

    try:
        if params['update_cache']:
            # Default is: always update the cache
            cache_valid = False
            now = datetime.datetime.now()
            if params.get('cache_valid_time', False):
                try:
                    mtime = os.stat(APT_UPDATE_SUCCESS_STAMP_PATH).st_mtime
                except:
                    # Looks like the update-success-stamp is not available
                    # Fallback: Checking the mtime of the lists
                    try:
                        mtime = os.stat(APT_LISTS_PATH).st_mtime
                    except:
                        # No mtime could be read. We update the cache to be safe
                        mtime = False

                if mtime:
                    tdelta = datetime.timedelta(seconds=params['cache_valid_time'])
                    mtimestamp = datetime.datetime.fromtimestamp(mtime)
                    if mtimestamp + tdelta >= now:
                        cache_valid = True
                        updated_cache_time = int(time.mktime(mtimestamp.timetuple()))

            if cache_valid is not True:
                cache.update()
                cache.open(progress=None)
                updated_cache = True
                updated_cache_time = int(time.mktime(now.timetuple()))
        else:
            updated_cache = False
            updated_cache_time = 0

        skip_packages = []

        origins = params["origins"]
        if params["security"]:
            if get_distro_id() == "Debian":
                origins.append("origin=Debian,codename={distro_codename},label=Debian-Security")
            elif get_distro_id() == "Ubuntu":
                origins.append("origin=Ubuntu,codename={distro_codename},suite={distro_codename}-security")

        for pkg in cache:
            if pkg.is_upgradable and not is_package_held_back(pkg):
                if matches_input_pkg(pkg, params["packages"], params["sources"], origins):
                    try:
                        pkg.mark_upgrade()
                    except SystemError, e:
                        module.fail_json(msg="Unable to upgrade " + pkg.name + ":\n" + str(e))
                else:
                    skip_packages.append(pkg.name)

        if not cache.get_changes():
            module.exit_json(changed=False, cache_updated=updated_cache, cache_update_time=updated_cache_time, skipped_packages=",".join(skip_packages))

        for pkg in cache.get_changes():
            if not matches_input_pkg(pkg, params["packages"], params["sources"], origins):
                module.fail_json(msg="No safe upgrade possible. State of package '" + pkg.name + "' would be changed.")

        if os.path.isfile(LOGFILE_DPKG):
            os.remove(LOGFILE_DPKG)

        iprogress = LogInstallProgress(LOGFILE_DPKG)
        result = cache.commit(install_progress=iprogress)

        if os.path.isfile(LOGFILE_DPKG):
            with open(LOGFILE_DPKG, "r") as f:
                dpkg_log = f.read()
            os.remove(LOGFILE_DPKG)
        else:
            dpkg_log = ""

        module.exit_json(changed=True, cache_updated=updated_cache, cache_update_time=updated_cache_time, log=dpkg_log, skipped_packages=",".join(skip_packages))
    except apt.cache.LockFailedException:
        module.fail_json(msg="Failed to lock apt for exclusive operation")
    except apt.cache.FetchFailedException:
        module.fail_json(msg="Could not fetch updated apt files")
    except Error as e:
        module.fail_json(msg=str(e))


# import module snippets
from ansible.module_utils.basic import *


if __name__ == "__main__":
    main()

# kate: space-indent on; indent-width 4; 
