# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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
# Copyright (c) 2022 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Provides the `OIDRegistry` class for managing Firebird OID nodes.

This module defines the central registry responsible for storing, updating,
and retrieving `OIDNode` objects, as well as handling serialization
and the construction of the node hierarchy.
"""

from __future__ import annotations

import uuid
from queue import SimpleQueue
from tomllib import loads
from typing import Any

from tomli_w import dumps

from firebird.base.collections import Registry
from firebird.base.types import STOP, Error

from ._model import NONE_VALUE, OIDNode, OIDNodeType, build_tree


class OIDRegistry(Registry):
    """A specialized registry for managing `OIDNode` objects, keyed by their UUID.

    This class inherits from `firebird.base.collections.Registry` and provides
    methods specifically tailored for handling the Firebird OID hierarchy.
    It allows populating the registry from parsed specification data or TOML
    documents, retrieves nodes (including the designated root node), triggers
    the linking of nodes into a tree structure via `build_tree`, and enables
    serializing the registry content back into TOML format.
    """
    def get_root(self) -> OIDNode | None:
        """Retrieves the root node of the OID hierarchy from the registry.

        Searches the registered nodes for the unique node whose `.node_type`
        attribute is `OIDNodeType.ROOT`.

        Returns:
            The root `OIDNode` object if found in the registry, otherwise `None`.
        """
        return self.find(lambda x: x.node_type is OIDNodeType.ROOT)
    def update_from_specifications(self, specifications: dict[str, dict[str, Any]]) -> None:
        """Populates or updates the registry from parsed OID specification data.

        Processes a dictionary where keys are specification URLs and values are
        the corresponding parsed/validated/pythonized specification data.
        For each specification, it instantiates `OIDNode` objects for both the
        main node defined in the spec ('node' key) and all its listed children
        ('children' key). All created nodes are added or updated in the registry
        using their UUIDs as keys.

        After processing all specifications, it calls `.build_tree` on the
        registry's current contents to link the nodes into a hierarchical
        structure based on `.node_spec` references and parent relationships.

        Arguments:
            specifications: A dictionary mapping specification URLs (str) to
                            their corresponding parsed data (`dict[str, Any]`),
                            as returned by `.parse_specifications`.
        """
        nodes: list[OIDNode] = [OIDNode.from_spec(url, data) for url, data in specifications.items()]
        for node in nodes:
            self.update(node.children)
        self.update(nodes)
        build_tree(self._reg.values())
    def update_from_toml(self, toml: str) -> None:
        """Updates the registry by loading node data from a TOML document string.

        Parses the TOML string, which is expected to contain a dictionary mapping
        node UUID strings to dictionaries of node attributes (as produced by the
        `as_toml` method).

        Performs validation checks before loading:

        - Ensures the TOML data either defines a root node (`node_type`='root'
          and no 'parent') or contains at least one node whose parent UUID
          already exists in the current registry.
        - If a root node is defined in the TOML and a root node is already
          registered, verifies that their UUIDs match.

        Nodes are then instantiated and added to the registry iteratively. A queue
        is used to handle dependencies: if a node's parent hasn't been loaded yet,
        the node is re-queued until its parent becomes available.

        After all nodes from the TOML are successfully loaded and registered,
        `.build_tree` is called on the registry's contents to reconstruct the
        full node hierarchy.

        Arguments:
            toml_data: A string containing the TOML document representation of
                       the OID nodes to load.

        Raises:
            Error: If validation fails (e.g., no linkable starting node, root UUID
                   mismatch, unresolvable parent dependencies after attempting
                   to load all nodes).
            toml.TOMLDecodeError: If the `toml_data` string is not valid TOML.
            uuid.ValueError: If a UUID string key or parent value in the TOML
                             is malformed.
            KeyError: If essential keys like 'node_type' are missing in the TOML data
                      for a node.
        """
        data: dict[str, Any] = loads(toml)
        # Validate data
        known: set[uuid.UUID] = set(self.keys())
        has_root_node: bool = False
        has_known_parent: bool = False
        root: OIDNode | None
        for uid_str, kwargs in data.items():
            uid = uuid.UUID(uid_str)
            if 'parent' in kwargs and kwargs['parent'] != NONE_VALUE:
                if self.get(uuid.UUID(kwargs['parent'])) in known:
                    has_known_parent = True
            elif kwargs['node_type'] == 'root':
                has_root_node = True
                root: OIDNode = None
                if (root := self.get_root()) is not None:
                    if root.uid != uid:
                        raise Error(f"Root node {uid} does not match registered root")
        if not (has_root_node or has_known_parent):
            raise Error("TOML does not define either root node or any node with registered parent")
        #
        que: SimpleQueue[tuple[str, dict[str, Any]] | type[STOP]] = SimpleQueue()
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
                parent: OIDNode = None
                if 'parent' in kwargs and kwargs['parent'] != NONE_VALUE:
                    parent = self.get(uuid.UUID(kwargs['parent']))
                    if parent is None:
                        que.put(item)
                    else:
                        kwargs['parent'] = parent
                        node = OIDNode(**kwargs)
                        parent.children.append(node)
                        self.store(node)
                elif kwargs['node_type'] == 'root':
                    self.store(OIDNode(**kwargs))
                else:
                    raise Error(f"Node {uid} is not root and has no parent node")
        build_tree(self._reg.values())
    def as_toml(self) -> str:
        """Serializes the entire registry content into a TOML formatted string.

        Iterates through all `OIDNode` objects currently held in the registry.
        For each node, it calls its `.as_toml_dict()` method to get a TOML-
        compatible dictionary representation.

        The final output is a single TOML string where the top level is a
        table (dictionary) mapping node UUID strings to their corresponding
        attribute dictionaries.

        Returns:
            A string containing the TOML representation of the registry's nodes.
            An empty string if registry is empty.
        """
        return dumps({str(node.uid): node.as_toml_dict() for node in self._reg.values()})

#: Firebird OID registry
oid_registry: OIDRegistry = OIDRegistry()
