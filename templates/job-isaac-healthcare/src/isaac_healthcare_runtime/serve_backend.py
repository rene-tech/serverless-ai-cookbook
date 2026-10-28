"""Isolated-environment policy entrypoint; no shell evaluation or package install."""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--entry', required=True)
    parser.add_argument('backend_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    context = json.loads(args.context.read_bytes())['project']
    os.environ['I4H_WORKFLOWS'] = context['effective_root']
    sys.path[:0] = context['python_paths']
    module, separator, function = args.entry.partition(':')
    if not separator or not module or not function or ':' in function:
        raise ValueError('Policy backend entry must be a module:function')
    extra = args.backend_args[1:] if args.backend_args[:1] == ['--'] else args.backend_args
    sys.argv = [args.entry, *extra]
    return getattr(importlib.import_module(module), function)()


if __name__ == '__main__':
    raise SystemExit(main())
