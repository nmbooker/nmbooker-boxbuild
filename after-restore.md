# After running the appropriate script for the OS

## All users

### Restore backups (deja-dup for home account at least)
Restore the bits of the home directory you care about.

If same base OS, make sure it's up to date and restore the entirety of the home directory.

If different base OS, including DE variant, selectively restore documents and only settings files that aren't related to your DE.

### Put an entry in HOSTNAME\_REINSTALL\_LOG.txt

Specify a datestamp of when the install was completed and, if known, the timestamp of the last deja-dup backup before the reinstall.

### Get ~/.dotfiles

Either direct from git or from the backup

### Fix doomemacs

Make sure ~/.config/emacs was restored from the backup (or install latest doomemacs from scratch if it wasn't there).

Reinstate the doomemacs config:
```
cd ~/.dotfiles
stow doomemacs
```

Check the link:
```
ls -ld ~/.config/doom
```

Fix doomemacs to work with OS's installed emacs version:
```
~/.config/emacs/bin/doom build && ~/.config/emacs/bin/doom sync
```

### Setup / fix vscode
Install the VIM plugin in VSCODE

Load this project in vscode
```
code ~/boxbuild
```

Test Ctrl+P brings up quick open rather than just moving cursor.
If Ctrl+P filename search isn't working, see here: https://stackoverflow.com/a/77097976
This needs to go in keybindings.json:
```
{
    "key": "ctrl+p",
    "command": "workbench.action.quickOpen"
}
```

## nick



## work
