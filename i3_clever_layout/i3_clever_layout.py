import argparse
import contextlib
import itertools
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading

import fasteners

if sys.version_info[0] != 3:
    # FileNotFoundError does not exist in python 2
    raise Exception('Only works with python 3')



LOGGER = logging.getLogger()

def build_parser():
    parser = argparse.ArgumentParser(description='')
    if 'HOME' in os.environ:
        default_config_dir = os.path.join(os.environ['HOME'], '.config', 'i3-clever-layout')
    else:
        default_config_dir = None

    parser.add_argument(
        '--config-dir', '-C',
        default=default_config_dir,
        help='Directory to store configuration and data')
    PARSERS = parser.add_subparsers(dest='command')

    parser.add_argument('--debug', action='store_true', help='Include debug output (to stderr)')

    config_parser = PARSERS.add_parser('config', help='Updating configuration options')
    config_parser.add_argument('option', type=str, help='Update this option (omit to list)', nargs='?')
    config_parser.add_argument('value', type=str, help='Update this option (omit to list)', nargs='?')

    dump_parser = PARSERS.add_parser('dump', help='Dump out information about a layout (No guarantees that this will not change)')
    dump_parser.add_argument('name', type=str)

    load_parser = PARSERS.add_parser('load', help='Load a layout')
    load_parser.add_argument('name', type=str)
    load_parser.add_argument(
        '--no-run', action='store_false', default=True,
        dest='run',
        help='Do not run spawn commands')

    save_parser = PARSERS.add_parser('save', help='Save the current layout')
    save_parser.add_argument('name', type=str)
    save_parser.add_argument(
        '--swallow-command', type=escape_split,
        help='Command to populate the swallows field in json output')
    save_parser.add_argument(
        '--run-command', type=escape_split,
        help='Command to guess how to run a layout')
    return parser


def split_space(s):
    return s.split(' ')



def ensure_dir(x):
    if not os.path.isdir(x):
    	os.mkdir(x)
    

def main():
    
    args = build_parser().parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    layout_dir = os.path.join(args.config_dir, 'layouts')

    LOGGER.debug('Using configuration directory %r', args.config_dir)
    
    ensure_dir(args.config_dir)
    ensure_dir(layout_dir)
    settings_file = os.path.join(args.config_dir, 'config.json')

    with with_data(settings_file) as settings:
        settings.setdefault('swallow_command', None)
        settings.setdefault('run_command', None)



        if args.command == 'save':
            swallow_command = args.swallow_command or settings["swallow_command"]
            run_command = args.run_command or settings["run_command"]

            LOGGER.debug('Swallow option maker: %r', swallow_command)
            LOGGER.debug('Run option maker: %r', run_command)

            if swallow_command is None:
                raise Exception('No swallow command set')
            if run_command is None:
                raise Exception('No run command set')

            if args.name == "-":
                layout_file = "/dev/stdout"
            else:
                layout_file = os.path.join(layout_dir, args.name)

            with open(layout_file, 'w') as stream:
                save_layout(stream, swallow_command, run_command)

        elif args.command == 'load':
            filename = os.path.join(layout_dir, args.name)
            with tempfile.NamedTemporaryFile(delete=False) as f:
                print(f.name)
                with open(filename) as stream:
                    nodes = json.loads(stream.read())

                for node in nodes:
                    f.write(json.dumps(node, indent=2, sort_keys=True).encode('utf8'))
                    f.write(b'\n')

                f.flush()


                command = [b'i3-msg', b'-t', b'run_command', b"append_layout " + f.name.encode('utf8')]
                LOGGER.debug('Running layout load command: %r', command)
                subprocess.check_call(command)

                for node in nodes:
                    if node["run"] is None:
                        LOGGER.debug('node %r has no command', node["name"])
                        continue

                    command = [part.encode('utf8') for part in node["run"]]
                    LOGGER.debug('Running command load command: %r', command)
                    subprocess.check_call(command)

        elif args.command == 'dump':
            filename = os.path.join(layout_dir, args.name)
            with open(filename) as stream:
                 print(stream.read())

        elif args.command == 'config':
            if args.option is not None:
                if args.value is None:
                    print(args.option, settings[args.option])
                else:
                    settings[args.option] = escape_split(args.value)
            else:
                for k, v in settings.items():
                    print(k, repr(v))
        else:
            raise ValueError(args.command)

def read_json(filename):
    if os.path.exists(filename):
        with open(filename) as stream:
            return json.loads(stream.read())
    else:
        return dict()


DATA_LOCK = threading.Lock()
@contextlib.contextmanager
def with_data(data_file):
    "Read from a json file, write back to it when we are finished"
    with fasteners.InterProcessLock(data_file + '.lck'):
        with DATA_LOCK:
            data = read_json(data_file)
            yield data

            output = json.dumps(data)
            with open(data_file, 'w') as stream:
                stream.write(output)

def walk_descendents(node):
    children = node["nodes"]
    for child in children:
        yield child

    for child in children:
        yield from walk_descendents(child)

def get_leaves(root):
    for node in walk_descendents(root):
        if not node["nodes"]:
            yield node

def get_focus_path(node):
    children = node["nodes"]
    if node["focused"]:
        return [node]
    else:
        for child in node["nodes"]:
            child_path = get_focus_path(child)
            if child_path:
                return [node] + child_path
        else:
            return None



def save_layout(layout_file, swallow_command, run_command):
    tree = get_tree()
    focus_path = get_focus_path(tree)
    for node in focus_path:
        if node["type"] == "workspace":
            focused_workspace = node
            break
    else:
        raise Exception('Could not find focused workspace')

    for leaf in get_leaves(focused_workspace):
        leaf_json = json.dumps(leaf, indent=4)
        LOGGER.debug('Getting run_command and swallow match for: %s', leaf_json)
        add_swallows(swallow_command, leaf)
        add_run(run_command, leaf)

    output = format_layout(focused_workspace)
    layout_file.write(output)

def add_swallows(command, leaf):
    command = [c.encode('utf8') for c in command]
    leaf_json = json.dumps(leaf).encode('utf8')
    raw_output = subprocess.check_output(command, input=leaf_json)
    LOGGER.debug('Trying to parse: %r', raw_output)
    try:
        swallow_obj = json.loads(raw_output)
        leaf["swallows"] =  swallow_obj
        LOGGER.debug('Swallow matcher: %s', json.dumps(swallow_obj, indent=4))
    except:
        raise Exception('Failed to parse: {!r}'.format(raw_output))

def escape_split(s):
    result = []
    part = []
    mode = None
    def add_part():
        nonlocal part
        if part:
            result.append(''.join(part))
        part = []

    for c in s:
        if mode is None:
            if c == '"':
                mode = c
                add_part()
            elif c == "'":
                mode = c
            elif c == " ":
                add_part()
            elif c == "\\":
                mode = "\\"
            else:
                part.append(c)
        elif mode == "\\":
            if c == "\\":
                part.append("\\")
                mode = None
            else:
                part.append(c)
                mode = None
        elif mode == '"':
            if c == '"':
                mode = None
                add_part()
            else:
                part.append(c)
        elif mode == "'":
            if c == "'":
                mode = None
                add_part()
            else:
                part.append(c)
        else:
            raise ValueError(mode)
    add_part()
    return result

def add_run(command, leaf):
    command = [c.encode('utf8') for c in command]
    raw = subprocess.check_output(command, input=json.dumps(leaf).encode('utf8')).decode('utf8').strip('\n')
    if raw == '':
        LOGGER.debug('No command for %r', leaf['name'])
        leaf["run"] = None
    else:
        LOGGER.debug('Run command: %s', raw)
        leaf["run"] = escape_split(raw.strip('\n'))

def sieve_keys(keys, tree):
    keys = keys + ['nodes']
    result = {k:v for k, v in tree.items() if k in keys}
    result["nodes"] = [sieve_keys(keys, child) for child in result["nodes"]]
    if not result["nodes"]:
        del result["nodes"]
    return result

LAYOUT_KEYS = [
    "geometry", "floating", "name", "percent", "swallows", "run", "border",
    "current_border_width", "type"
]
def format_layout(node):
    output = [sieve_keys(LAYOUT_KEYS, n) for n in  node["nodes"]]
    return json.dumps(output, indent=2, sort_keys=True)





def get_active_workspace(tree):
    for node in walk_descendents(tree):
        if node["type"] == "workspace":
            print(node['name'])
            print(node['focused'])
            if node["focused"]:
                return node
    else:
        raise Exception('Could not find active workspace')

def get_tree():
    return json.loads(subprocess.check_output(['i3-msg', '-t', 'get_tree']))
