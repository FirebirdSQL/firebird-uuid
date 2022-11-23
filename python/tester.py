from __future__ import annotations
from typing import List, Tuple
import sys
from pprint import pprint
from io import StringIO
from toml import loads
from firebird.uuid.spec import get_specifications, parse_specifications
from firebird.uuid.model import Node, build_tree
from firebird.uuid.registry import registry

def print_node(node: Node, indent=0, _to=None) -> None:
    out = sys.stdout if _to is None else _to
    print(f'{"  " * indent}{"-" * 20}', file=out)
    print(f'{"  " * indent}OID: {node.oid}', file=out)
    print(f'{"  " * indent}UID: {node.uid}', file=out)
    print(f'{"  " * indent}Number: {node.number}', file=out)
    print(f'{"  " * indent}Name: {node.name}', file=out)
    print(f'{"  " * indent}Full name: {node.full_name}', file=out)
    print(f'{"  " * indent}Description: {node.description}', file=out)
    print(f'{"  " * indent}Contact: {node.contact}', file=out)
    print(f'{"  " * indent}E-mail: {node.email}', file=out)
    print(f'{"  " * indent}Site: {node.site}', file=out)
    print(f'{"  " * indent}Parent spec: {node.parent_spec}', file=out)
    print(f'{"  " * indent}Node spec: {node.node_spec}', file=out)
    print(f'{"  " * indent}Type: {node.node_type}', file=out)
    if node.children:
        print(f'{"  " * indent}Children:', file=out)
        for child in node.children:
            print_node(child, indent + 1, _to)


def main():
    specifications, errors = get_specifications()
    specifications, errors2 = parse_specifications(specifications)
    errors.update(errors2)
    if errors:
        print('Specifications:')
        for url, data in specifications.items():
            print(url)
            #pprint(data)
        print('Errors:')
        for url, exc in errors.items():
            print(url, '\n', exc)
    #
    #nodes = [Node.from_spec(url, data) for url, data in specifications.items()]
    #for node in nodes:
        #print_node(node)
        #print('=' * 10)
    #root = build_tree(nodes)
    #print_node(root)
    #printout = StringIO()
    #print_node(root, _to=printout)
    #txt_1 = printout.getvalue()
    #print_node(root)
    ##
    registry.update_from_specifications(specifications)
    #spec2, err2 = get_specifications('https://raw.githubusercontent.com/FirebirdSQL/saturnin-core/master/oid/micros.oid')
    #spec2, err2 = parse_specifications(spec2)
    #registry.update_from_specifications(spec2)
    printout = StringIO()
    print_node(registry.get_root(), _to=printout)
    txt_1 = printout.getvalue()
    #
    toml = registry.as_toml()
    print(toml)
    #
    registry.clear()
    registry.update_from_toml(toml)
    #print_node(registry.get_root())
    printout = StringIO()
    print_node(registry.get_root(), _to=printout)
    txt_2 = printout.getvalue()
    #data = loads(toml)
    #nodes = []
    #for kwargs in data.values():
        #nodes.append(Node(**kwargs))
    #pprint(nodes)
    #
    print(txt_1 == txt_2)
    print('done')


if __name__ == '__main__':
    main()
