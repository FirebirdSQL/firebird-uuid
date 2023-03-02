#coding:utf-8
#
# PROGRAM/MODULE: firebird-uuid
# FILE:           firebird/uuid/registry.py
# DESCRIPTION:    Firebird OID registry
# CREATED:        14.11.2022
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2021 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Firebird OID registry.

"""

from __future__ import annotations
from typing import List, Optional
import uuid
from queue import SimpleQueue
from toml import dumps, loads
from firebird.base.types import Error, STOP
from firebird.base.collections import Registry
from ._model import NodeType, Node, build_tree

class OIDRegistry(Registry):
    """Firebird OID registry.
    """
    def get_root(self) -> Optional[Node]:
        """Returns ROOT node, or None if root node is not registered.
        """
        return self.find(lambda x: x.node_type is NodeType.ROOT)
    def update_from_specifications(self, specifications: Dict[str, str]) -> None:
        """Updates registered nodes from specifications.

        Arguments:
          specifications: Dictionary with `url: spec_dict` as returned by
            `.parse_specifications`.
        """
        nodes: List[Node] = [Node.from_spec(url, data) for url, data in specifications.items()]
        for node in nodes:
            self.update(node.children)
        self.update(nodes)
        build_tree(self._reg.values())
    def update_from_toml(self, toml: str) -> None:
        """Updates registered nodes from TOML document.

        Arguments:
          toml: TOML document (as created by `as_toml` method).
        """
        data = loads(toml)
        # Validate data
        known = set(self.keys())
        has_root_node = False
        has_known_parent = False
        for uid, kwargs in data.items():
            uid = uuid.UUID(uid)
            if 'parent' in kwargs:
                if self.get(uuid.UUID(kwargs['parent'])) in known:
                    has_known_parent = True
            elif kwargs['node_type'] == 'root':
                has_root_node = True
                root: Node = None
                if root := self.get_root() is not None:
                    if root.uid != uid:
                        raise Error(f"Root node {uid} does not match registered root")
        if not (has_root_node or has_known_parent):
            raise Error("TOML does not define either root node or any node with registered parent")
        #
        que = SimpleQueue()
        for uid, kwargs in data.items():
            que.put((uid, kwargs))
        qsize = que.qsize()
        que.put(STOP)
        while not que.empty():
            item = que.get()
            if item is STOP:
                if not que.empty():
                    if que.qsize() >= qsize:
                        raise Error(f"TOML contains {qsize - que.qsize()} unlinkable nodes")
                    else:
                        qsize = que.qsize()
                        que.put(STOP)
            else:
                uid, kwargs = item
                parent: Node = None
                if 'parent' in kwargs:
                    parent = self.get(uuid.UUID(kwargs['parent']))
                    if parent is None:
                        que.put(item)
                    else:
                        kwargs['parent'] = parent
                        node = Node(**kwargs)
                        parent.children.append(node)
                        self.store(node)
                elif kwargs['node_type'] == 'root':
                    self.store(Node(**kwargs))
                else:
                    raise Error(f"Node {uid} is not root and has no parent node")
        build_tree(self._reg.values())
    def as_toml(self) -> str:
        """Returns registry content as TOML document.
        """
        nodes = {str(node.uid): node.as_toml_dict() for node in self._reg.values()}
        toml = dumps(nodes)
        return toml

#: Firebird OID registry
oid_registry = OIDRegistry()
