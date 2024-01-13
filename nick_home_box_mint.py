#!/usr/bin/env python3

from functools import partial
from itertools import chain
import os
from subprocess import run, DEVNULL
from socket import gethostname
import sys
import tempfile
from typing import AbstractSet, Iterable, Set, TypeAlias

from heredocs import heredoc


Hostname: TypeAlias = str
FlatpakName: TypeAlias = str
GnomeExtension: TypeAlias = str
PackageName: TypeAlias = str
RepoTag: TypeAlias = str
Role: TypeAlias = str


def yumrepo(repo_lines, filestem, gpg_key_url, gpg_key_basename):
    repofile = ''.join(line+'\n' for line in repo_lines)
    return {
        'repofile': repofile,
        'file_stem': filestem,
        'import_gpg_key': gpg_key_url,
        'gpg_key_basename': gpg_key_basename,
    }


machine_roles: dict[Hostname, set[Role]] = {
    'jay': {'common', 'gnome', 'home', 'laptop', 'work'},
    #'jake': {'common', 'cinnamon', 'laptop', 'work'},
    'jake': {'common', 'mate', 'laptop', 'work'},
    'missy': {'common', 'gnome', 'laptop', 'work'},
    'ogg': {'common', 'mate', 'home'},
    'vimes': {
        'common',
        'games',
        'home',
        # 'lazyscan-deps',
        'laptop',
        'nscde-deps',
        # GUI prompts for nvidia setup - go with that
        'xfce',
    },
}


def apt_repo_line(linetype, url, distro, sections, attributes):
    if attributes:
        attributes_section =(
            '['
            + ' '.join(f'{key}={value}' for (key, value) in attributes)
            + ']'
        )
        return ' '.join([linetype, attributes_section, url, distro, *sections])
    else:
        return ' '.join([linetype, url, distro, *sections])


dnf_repos: dict[RepoTag, dict] = {
    'vscode': yumrepo(
        repo_lines=[
            'deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main'
        ],
        filestem='vscode',
        gpg_key_url='https://packages.microsoft.com/keys/microsoft.asc',
        gpg_key_basename='packages.microsoft.gpg',
    ),
}

def hold_apt_package(package):
    run(['sudo', 'apt-mark', 'hold', package], check=True)

role_early_hooks = {
    'work': [
        # partial(hold_apt_package, 'thunderbird'),
    ],
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
        # 'com.mattjakeman.ExtensionManager',
    },
    'work': {
        # 'com.brave.Browser',
            # ^ for PWAs (as first choice if works)
            # ^ and for Jitsi meetings (due to Chromium engine)
    },
}

gnome_extensions: dict[Role, frozenset[GnomeExtension]] = {
    'gnome': frozenset(),
}

roles: dict[Role, frozenset[PackageName]] = {
    'common': frozenset({
        'emacs',
        'fd-find',
            # ^ an optional dependency for doomemacs
        'hplip-gui',
        'htop',
        'python3-pip',
        'python3-mypy', # <- to type-check this script when editing
        'ripgrep',
            # ^ for doomemacs
        'seahorse',
        'stow',
    }),
    'games': frozenset({'mono-devel', 'steam'}),
    'cinnamon': frozenset({
        'nemo-seahorse',
            # gpg file encryption, decryption and signing
    }),
    'gnome': frozenset({
        'chrome-gnome-shell',
            # chrome-gnome-shell enables Firefox etc extensions integration
        'gnome-power-manager', # power statistics
        'gnome-tweaks',
        'seahorse-nautilus',
            # gpg file encryption, decryption and signing
    }),
    'mate': frozenset({
        'caja-seahorse',
            # gpg file encryption, decryption and signing
        'dconf-editor',
    }),
    'nscde-deps': frozenset({
        'cbatticon',
        'fvwm',
        'fvwm-icons',
        'gkrellm',
        'gtk3-nocsd',
        'imagemagick',
        'ksh',
        'libfile-mimeinfo-perl',
        'libstroke0',
        'pnmixer',
        'python3',
        'python3-pyqt5',
        'python3-xdg',
        'python3-yaml',
        'qt5-style-plugins',
        'qt5ct',
        'rofi',
        'stalonetray',
        'x11-utils',
        'x11-xserver-utils',
        'xclip',
        'xdotool',
        'xscreensaver',
        'xsettingsd',
        'xterm',
    }),
    'home': frozenset({
        'code',
        'deja-dup',
        #'dotnet-sdk-6.0', # For F#
        #'haskell-platform',
        #'openjdk-11-jdk',  # for the Java Udemy course
        'keepassxc',
        'neovim',
        'syncthing',
        'vim-gtk',
    }),
    'laptop': frozenset({
        'powertop',
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
        'emacs',
        'code',
        # 'dotnet-sdk-6.0',
            # ^ For "CPAN hour"
        # 'gajim',
        'git',
        'kwrite',
            # ^ Multi-window text editor
        'keepassxc',
        'neovim',
        # 'nextcloud-desktop',
        'npm',
            # ^ The elm VSCode stuff needs npm, for example.
            # ^ For further setup instructions:
            # ^     https://marketplace.visualstudio.com/items?itemName=Elmtooling.elm-ls-vscode
        'okular',
            # ^ more feature complete annotations than evince
        'vim',
        'wireguard-tools', # VPN
        'xournalpp',
    }),
    'xfce': frozenset({'gigolo'}),
}

dependent_packages: dict[PackageName, Set[Role]] = {
    # install package on the left if all the roles on the right
    # are requested
    'nextcloud-client-nautilus': {'gnome', 'work'},
    'caja-nextcloud': {'cinnamon', 'work'},
}


def union(sets: Iterable[AbstractSet]) -> frozenset:
    return frozenset().union(*sets)


def dnf(packages: Iterable[PackageName]) -> None:
    if packages:
        run(['sudo', 'apt-get', 'update'], check=True)
        run(
            ['sudo', 'apt-get', '-y', 'install', *packages],
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
    with(
        open('repo-keys/apt/microsoft.asc', 'rb') as armored_file,
        tempfile.NamedTemporaryFile() as dearmored_file,
    ):
        run(
            ['gpg', '--dearmor'],
            stdin=armored_file,
            stdout=dearmored_file,
            check=True,
        )
        run(
            [
                'sudo', 'install',
                    '-D',
                    '-o', 'root',
                    '-g', 'root',
                    '-m', '644',
                    dearmored_file.name,
                    os.path.join('/etc/apt/keyrings', repo['gpg_key_basename']),
            ],
            check=True,
        )
    run(
        ['sudo', 'tee', f"/etc/apt/sources.list.d/{repo['file_stem']}.list"],
        input=repo['repofile'],
        stdout=DEVNULL,
        encoding='utf8',
        check=True,
    )
    run(['sudo', 'apt', 'update'], check=True)
    # ret = run(['sudo', 'dnf', 'check-update'])
    # if ret.returncode == 100:
    #     # I think 100 means "there are updates" and this isn't
    #     # necessarily fatal
    #     pass
    # else:
    #     ret.check_returncode()


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
    machine_name = gethostname().split('.')[0]
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
        early_hooks = list(chain.from_iterable(
            role_early_hooks.get(role, []) for role in requested_roles
        ))
        for hook in early_hooks:
            hook()
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
