# git-watch

## Introduction

`git-watch` is a bash script that will automatically synchronize `git` repositories in response to several possible triggers. It is meant to offer a solution similar to Dropbox and OneDrive, using `git`.

With sync, it is meant that the following git commands are issued:

1. `git add -A`
2. `git commit -m "message"`
3. `git fetch`
4. `# if branch is behind`
   1. `git merge`
   2. `# if conflict`
      1. `git add -A`
      2. `git commit -m "message"`
5. `# if branch is ahead`
   1. `git push`

The commands after the first one will only be issued when there are changes in the working directory.

Possible triggers are:

| Name      | Description                                                                                             |
| --------- | ------------------------------------------------------------------------------------------------------- |
| inotify   | A file has been added, deleted, moved, or changed. See [Inotify trigger](#inotify-trigger) for details. |
| periodic  | A certain period of time has elapsed                                                                    |
| reconnect | The connection to the notification server was reestablished                                             |
| remote    | A remote repository pushed a commit                                                                     |
| resume    | Synchronization has been resumed after pause                                                            |
| startup   | The script was started                                                                                  |
| user      | The user requested a synchronization (pressed the `s` key)                                              |
| \*        | See [Custom triggers](#custom-triggers)                                                                 |

## Usage

```
# git-watch -h
Usage: git-watch [-hvx] [-e <TRACE|DEBUG|INFO|WARN|ERROR|OFF>] [-i DELAY] [-l FILE] [-o DELAY] [-p PORT] [-s SERVER] [-t TRIGGERS] dirs...
        -e   Log level. Default = INFO
        -h   Display help
        -i   Inotify delay in seconds. Default = 60
        -l   File to log inotify events to. Events will not be logged if not specified.
        -o   Periodic delay in seconds. Default = 300
        -p   Notification port. Default = 19725
        -s   Notification server. Default = localhost
        -t   Comma separated list of triggers to enable. Possible triggers: inotify, periodic, reconnect, remote, resume, startup,
             user, * (any string, which will trigger a sync when it's written to the sync directory's pipe)
             Default = inotify,resume,startup,user
        -v   Display version
        -x   Enable debug mode
        dirs The directories to watch
```

## Commit message

By default, the commit message is the result of `eval 'echo -n "Commit on $(hostname), trigger=$TRIGGER"'`.
This can be changed by creating a file `.git-watch` in the root of the directory being watched, and adding a line
`commit_msg_command=expression` to it. The expression will be evaluated with `eval`.

## User interaction

The following keys are available to interact with the program.

```
h: help
l: list pipes
p: pause
q: quit
r: resume
s: sync now
v: print version
```

Note that the `s` key will only be available when the user trigger is enabled. By default it's enabled.

## Example output

```
# git-watch -t inotify,resume,startup,user,remote synced_dir
git-watch v1.31.0
Supported keys:
  h: help
  l: list pipes
  p: pause
  q: quit
  r: resume
  s: sync now
  v: print version
2024-07-09 20:27:59 | connected to localhost:19725
2024-07-09 20:27:59 | synced_dir  | sync triggered by startup
2024-07-09 20:27:59 | synced_dir  | sync complete
2024-07-09 20:43:12 | synced_dir  | sync triggered by remote
2024-07-09 20:43:12 | synced_dir  | sync complete
2024-07-09 20:44:48 | synced_dir  | sync triggered by inotify
2024-07-09 20:44:48 | synced_dir  | sync complete
```

## Inotify trigger

The `inotify` trigger will be issued one minute after the last file change. If there were syncs due to other triggers in the meantime, another sync is not performed.

The `inotify` trigger will not be issued when a file changed that is ignored by `.gitignore`. Some programs like `vim` and `libreoffice` create temporary files, which triggers unwanted `inotify`s. This can be omitted by adding these temporary files to `.gitignore`. To know exactly which files are being created and changed, use the `-l` option to specify a file to log the inotify events to. Example of this file when creating the file `file_in_vim` in `vim`:

```
# tail -f inotify_log
2021-10-02 16:21:09 IGNORE CREATE git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:09 IGNORE CREATE git-watch_demo/ .file_in_vim.swpx
2021-10-02 16:21:09 IGNORE DELETE git-watch_demo/ .file_in_vim.swpx
2021-10-02 16:21:09 IGNORE DELETE git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:09 IGNORE CREATE git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:09 IGNORE MODIFY git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:15 IGNORE MODIFY git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:17 PASS CREATE git-watch_demo/ file_in_vim
2021-10-02 16:21:17 PASS MODIFY git-watch_demo/ file_in_vim
2021-10-02 16:21:17 PASS MODIFY git-watch_demo/ file_in_vim
2021-10-02 16:21:17 IGNORE MODIFY git-watch_demo/ .file_in_vim.swp
2021-10-02 16:21:17 IGNORE DELETE git-watch_demo/ .file_in_vim.swp
```

The third field `IGNORE`/`PASS` indicates if the file is ignored or not.

The `.gitignore` file would in this case look like:

```
*.swp
!*.swp/
*.swpx
!*.swpx/
```

The `inotify` trigger is disabled during the `git pull` step during sync.

## Custom triggers

Triggers are issued on named pipes. There is one named pipe per directory being watched. It's possible to issue custom triggers on a pipe by writing to it. E.g.

```
echo string > /tmp/git-watch.XXXXX/YYYYY
```

`YYYYY` represents the inode of the directory being watched. The pipes can be listed by pressing the `l` key. The trigger represented by the string must be enabled via the `-t` option.

## Setup

Before running `git-watch`, make sure that the watched repos are initialized and that it's possible to push. For the `inotify` trigger to work (i.e. sync in response to file changes), you need to have `inotifywait` installed. In Debian, `inotifywait` is part of the `inotify-tools` package.

## Notification Server

`git-watch` can send notifications to other clients to trigger a sync when a push was performed. These notifications are sent to a server on which you need to run `notification-server.java`, included in this repo. For it to run, you need to have Java 21 or later installed and it can be run as a script, i.e. it doesn't have to be compiled. `git-watch` will try to connect to the notification server when the `remote` trigger is enabled.

As an alternative to the notification server included in this repo, it's possible to run a notifcation server with `socat`:

```bash
socat tcp-listen:19725,fork,reuseaddr \
'system:
PIPE="$(mktemp -u -t git-watch_ns-XXXX)"
mkfifo "$PIPE"
trap \"rm "$PIPE"; exit 0;\" INT
while read NOTIFICATION<"$PIPE"; do echo "$NOTIFICATION"; done &
PID=$!
read CLIENT
echo "Client connect: $SOCAT_PEERPORT \\(${CLIENT:-null}\\)" > /dev/tty
echo "connected" > "$PIPE"
while read NOTIFICATION; do
  for OTHER_PIPE in $(ls ${PIPE%/*}/git-watch_ns-*); do
    [ "$PIPE" != "$OTHER_PIPE" ] && echo "$NOTIFICATION" > "$OTHER_PIPE"
  done
done
echo "Client disconnect: $SOCAT_PEERPORT \\(${CLIENT:-null}\\)" > /dev/tty
kill $PID
rm $PIPE'\
,sigint
```

## Hints and tips

- When you have a lot of binary files in your repo and to omit that it grows exponentially, use [git-lfs](https://github.com/git-lfs/git-lfs).
- If you want to use `git-watch` on Android, set it up within Termux.
- If you want to use `git-watch` on Windows, set it up within [WSL2](https://docs.microsoft.com/en-us/windows/wsl/install-win10). Note that accessing Windows files from within WSL2 is too slow for `git` to work well ([see issue on github](https://github.com/microsoft/WSL/issues/4197)), hence keep the repo within WSL2. Files within WSL2 can be accessed from Windows via network share `\\wsl$\`.
- The script will also work on Windows with MSYS2. For the inotify trigger to work, install [inotify-win](https://github.com/thekid/inotify-win).
