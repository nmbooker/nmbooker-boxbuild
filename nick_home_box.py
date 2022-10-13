#!/usr/bin/env python3

from subprocess import run, DEVNULL
from socket import gethostname
import sys
from typing import AbstractSet, Iterable, Set, TypeAlias

Hostname: TypeAlias = str
FlatpakName: TypeAlias = str
GnomeExtension: TypeAlias = str
PackageName: TypeAlias = str
RepoTag: TypeAlias = str
Role: TypeAlias = str


def heredoc(astring: str) -> str:
    r"""Unindent an indented multi-line string.

    This is to allow multi-line strings to be indented similar to
    Python code without the indentation making it into the final result.
    Line endings are preserved as written.

    >>> indented_multiline('''
        hello:
         world
        ''')
    'hello:\n world\n'

    It's not possible to directly build a string whose last line
    does not end with a new line, but you can use .rstrip('\n')
    on the result if that's what you want.  I anticipate you'll be building
    a text file using this so a trailing newline is nearly always what
    you want.
    """
    lines = astring.splitlines(keepends=True)
    first_line = lines[0]
    content_lines = lines[1:-1]
    last_line = lines[-1]
    assert first_line.isspace(), 'first line must be all whitespace'
    assert last_line.isspace(), 'last line must be all whitespace'
    indentation_template = last_line.rstrip('\n')
    assert all(l.startswith(indentation_template) for l in content_lines), \
        'all content lines must begin with same whitespace as last one'
    unindented_lines = \
        [l.removeprefix(indentation_template) for l in content_lines]
    return ''.join(unindented_lines)


def yumrepo(name, filestem, baseurl, gpg_key_url):
    repofile = heredoc(f"""
        [code]
        name={name}
        baseurl={baseurl}
        enabled=1
        gpgcheck=1
        gpgkey={gpg_key_url}
        """)
    return {
        'repofile': repofile,
        'file_stem': filestem,
        'import_gpg_key': gpg_key_url,
    }


machine_roles: dict[Hostname, set[Role]] = {
    'jay': {'common', 'gnome', 'home', 'work'},
    'jake': {'common', 'gnome', 'work'},
    'missy': {'common', 'gnome', 'work'},
    'vimes': {'common', 'games', 'gnome', 'home', 'lazyscan-deps', 'nvidia'},
}

dnf_repos: dict[RepoTag, dict] = {
    'vscode': yumrepo(
        name='Visual Studio Code',
        filestem='vscode',
        baseurl='https://packages.microsoft.com/yumrepos/vscode',
        gpg_key_url='https://packages.microsoft.com/keys/microsoft.asc',
    ),
}

package_dnf_repos: dict[PackageName, set[RepoTag]] = {
    # singletons for flattening
    'code': {'vscode'},
}

flatpaks: dict[Role, Set[FlatpakName]] = {
    'common': {
        'com.github.tchx84.Flatseal',
    },
    'gnome': {
        'com.mattjakeman.ExtensionManager',
    },
    'work': {
        'com.brave.Browser',
            # ^ for PWAs (as first choice if works)
            # ^ and for Jitsi meetings (due to Chromium engine)
    },
}

gnome_extensions: dict[Role, frozenset[GnomeExtension]] = {
    'gnome': frozenset(),
}

roles: dict[Role, frozenset[PackageName]] = {
    'common': frozenset({
        'firewall-config',
        'python-mypy', # <- to type-check this script when editing
    }),
    'games': frozenset({'mono-core', 'mono-devel', 'steam'}),
    'gnome': frozenset({'chrome-gnome-shell', 'gnome-tweaks'}),
        # chrome-gnome-shell enables Firefox etc extensions integration
    'home': frozenset({
        'code',
        'deja-dup',
        'dotnet-sdk-6.0', # For F#
        'haskell-platform',
        'java-11-openjdk-devel',  # for the Java Udemy course
        'keepassxc',
        'neovim',
        'syncthing',
        'vim-enhanced',
    }),
    'lazyscan-deps': frozenset({
        'ImageMagick',
        'perl(App::cpanminus)',
        'perl(autodie)',
        'perl(Exporter::Easy)',
        'perl(Number::Range)',
        'perl(failures)',
        'perl(File::Slurp)',
        'perl(List::MoreUtils)',
        'perl(local::lib)',
        'perl(LockFile::Simple)',
        'perl(Moo)',
        'perl(Tk)',
        'perl(Try::Tiny)',
        'sane-backends',
        'xterm',
    }),
    'nvidia': frozenset({'akmod-nvidia'}),
    'work': frozenset({
        'code',
        'dotnet-sdk-6.0',
            # ^ For "CPAN hour"
        'epiphany',
            # ^ For PWA track.toggl.com
        'gajim',
        'kwrite',
            # ^ Multi-window text editor
        'keepassxc',
        'neovim',
        'nextcloud-client',
        'okular',
            # ^ more feature complete annotations than evince
        'thunderbird',
        'thunderbird-wayland',
        'vim-enhanced',
        'xournalpp',
    }),
}

dependent_packages: dict[PackageName, Set[Role]] = {
    # install package on the left if all the roles on the right
    # are requested
    'nextcloud-client-nautilus': {'gnome', 'work'},
}


def union(sets: Iterable[AbstractSet]) -> frozenset:
    return frozenset().union(*sets)


def dnf(packages: Iterable[PackageName]) -> None:
    if packages:
        run(
            ['sudo', 'dnf', 'install', '-y', *packages],
            check=True,
        )


def enable_flathub() -> None:
    run(
        ['sudo', 'flatpak', 'remote-add', '--if-not-exists', 'flathub',
            'https://flathub.org/repo/flathub.flatpakrepo'],
        check=True,
    )


def install_flatpaks_from_flathub(required_flatpaks: Iterable[FlatpakName]) \
        -> None:
    if required_flatpaks:
        run(
            [
                'sudo', 'flatpak', 'install',
                    '--assumeyes',
                    'flathub',
                    *required_flatpaks,
            ],
            check=True,
        )


def install_repo(repo: dict) -> None:
    run(['sudo', 'rpm', '--import', repo['import_gpg_key']], check=True)
    run(
        ['sudo', 'tee', f"/etc/yum.repos.d/{repo['file_stem']}.repo"],
        input=repo['repofile'],
        stdout=DEVNULL,
        encoding='utf8',
        check=True,
    )
    ret = run(['sudo', 'dnf', 'check-update'])
    if ret.returncode == 100:
        # I think 100 means "there are updates" and this isn't
        # necessarily fatal
        pass
    else:
        ret.check_returncode()


def extra_repos_for_packages(required_packages: Iterable[PackageName]) \
        -> list[dict]:
    extra_repo_names: frozenset[RepoTag] = \
        union(
            package_dnf_repos.get(pkgname, set())
            for pkgname in required_packages
        )
    return [dnf_repos[reponame] for reponame in extra_repo_names]


def flatpaks_for_individual_roles(requested_roles: AbstractSet[Role]) \
        -> frozenset[FlatpakName]:
    return union(
        flatpaks.get(rolename, frozenset())
        for rolename in requested_roles
    )


def packages_for_individual_roles(requested_roles: AbstractSet[Role]) \
        -> frozenset[PackageName]:
    return union(roles[rolename] for rolename in requested_roles)


def packages_for_role_combinations(requested_roles: AbstractSet[Role]) \
        -> frozenset[PackageName]:
    extra_packages: set[PackageName] = set()
    for package_name, required_roles in dependent_packages.items():
        if required_roles <= set(requested_roles):
            extra_packages.add(package_name)
    return frozenset(extra_packages)


def packages_for_roles(requested_roles: AbstractSet[Role]) \
        -> frozenset[PackageName]:
    return(
        packages_for_individual_roles(requested_roles)
        | packages_for_role_combinations(requested_roles)
    )


def main() -> None:
    machine_name = gethostname()
    if machine_name not in machine_roles:
        sys.stderr.write(heredoc(f"""
            Hostname {machine_name} not declared in machine_roles
            You need to either:
                * declare roles for that hostname in that variable
                * set your hostname using `hostnamectl hostname <intended-hostname>
            Valid hostnames are: {sorted(machine_roles.keys())!r}
            """))
        sys.exit(4)
    else:
        requested_roles = machine_roles[machine_name]
        required_packages = packages_for_roles(requested_roles)
        extra_repos = extra_repos_for_packages(required_packages)
        for repo in extra_repos:
            install_repo(repo)
        dnf(required_packages)
        enable_flathub()
        required_flatpaks =\
            flatpaks_for_individual_roles(requested_roles)
        install_flatpaks_from_flathub(required_flatpaks)



if __name__ == "__main__":
    main()
