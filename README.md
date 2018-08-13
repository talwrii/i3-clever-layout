# i3-clever-layout

Save and restore your [i3wm](https://i3wm.org/) layout, spawning applications to start windows.
Hopefully, a more convenient version of *i3-save-tree*.

Requires Python3 (but can happily coexist with Python2).

# Usage

*"Any problem in computer science can be solved with another level of indirection."
       David Wheeler*

*i3-clever-layout* attempts to automate the saving and restoring of i3 layouts, together with (optionally) running the applications contained in a layout.

Working out which applications to run and where they should be placed in a layout is in general very hard. But for many use cases it is trivial; therefore, we solve this problem through *configuration* for the user's specific use case. The price of using such a *framework* approach is some loss of generality and ability to debug.

The user of *i3-clever-layout* must provide two commands:

* **run_command** which derives for each window a command to spawn it anew
* **swallow_command** which works out how to match up newly made windows to the *slots* that i3's [append_layout](https://i3wm.org/docs/layout-saving.html#_append_layout_command) command provides.

Each of these commands is fed a node from `i3-msg -t get_tree` on standard input.

An (unrealistically simplified) example using [jq](https://stedolan.github.io/jq/) may be informative:

```
i3-clever-layout save --run-command 'jq .name' --swallow-command 'jq [{title:.name}]' test
i3-clever-layout restore test
```

This attempts to run a command with the same name as the window title to spawn a window, and places new windows with the same title as the current window in the slot, in the slot.

A real world example [is included](examples/i3-layout-guess).

A default run- and swallow- command can be set using the config command

```
i3-clever-layout config swallow_command 'jq [{title:.name}]'
i3-clever-layout config run_command 'jq .name'
```

The `--debug` flag may be used to debug your swallow and run commands.
`i3-clever-layout save -` produces output that can be used with `append_layout` for debugging purposes. This output can also be inspected manually.

# Installation

```
sudo apt-get install python3-pip # requires python 3
pip3 install git+https://github.com/talwrii/clixpath#egg=clixpath
```

# Background

See also: [this reddit post](https://www.reddit.com/r/i3wm/comments/7j4siz/state_of_the_art_for_i3savetree/).

*i3* allows one to create [complicated nested layouts](https://i3wm.org/docs/tree-migrating.html#_tree) and modify the [size of windows in these layouts](https://i3wm.org/docs/userguide.html#_resizing). There are also tools to navigate very complicated collections of windows like [marks](https://i3wm.org/docs/userguide.html#vim_like_marks), [workspaces](https://i3wm.org/docs/userguide.html#_using_workspaces), the application [i3-easyfocus](https://github.com/cornerman/i3-easyfocus), and indeed the [easy ability to define custom key-bindings](https://i3wm.org/docs/userguide.html#keybindings).

However, this ability leads one to create complicated layouts (often for one-off tasks)
which are lost when one restarts a machine. 
Developers have observed the value of saving and restoring these layouts and [provided functionality for doing so](https://i3wm.org/docs/layout-saving.html). But given that working out how to *create* the windows in a layout is *in general* impossible, i3's tools are very much at the level of "general purpose library functions" rather than convenience tools.

*i3-clever-layout* attempts to extend i3's layout-saving functionality some way towards a convenience tool.

# Design considerations

This tools in many ways extends and reimplements `i3-save-tree`. This was influenced by the authors familiarity with python and his beliefs about python's superior discoverability.

This tool is in many ways just a massive ball of glue, but "the last mile" of making tools convenient to use tends produce such code.

# Further work

This tool may act as a stepping stone towards a more "do what I mean" layout saver and restorer.
It seems unlikely that a single author could (or would be motivated) to create such a tool, but individuals may be motivated to solve their own problems and share the results if given the opportunity to do so.

One scenario would be that a a standard "do-what-I-mean" `run_command` and `swallow_command` was created (possibly one that had a number of configuration options) with users tweaking this command for their own use cases and sharing these improvements. It remains to be seen whether this is something that the world cares about.

# Alternatives and prior work

* [i3](https://github.com/i3/i3) provides "library level" functionality to save an restore desktops. [i3-save-tree](https://i3wm.org/docs/layout-saving.html) automates using these libraries somewhat, but requires manual steps that [need to be used each time a layout is saved](https://www.reddit.com/r/i3wm/comments/7j4siz/state_of_the_art_for_i3savetree/dr3qwq5/).
* [i3-lm](https://github.com/borysn/i3-lm) has similar, approach hard-coding the saving and restoring of a number of applications.

# Development

Due to the interactive nature of this tool tests are annoying to write.
There are no tests, but `tox` is used to check dependencies, installation and syntax errors.
