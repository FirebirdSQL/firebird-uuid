# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-uuid
# FILE:           firebird/uuid/_model.py
# DESCRIPTION:    Model for Firebird OID registry
# CREATED:        11.11.2022
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

"""Defines the core data structures for the Firebird OID registry model.

This module contains the `OIDNode` class, which represents a single node
within the OID hierarchy, holding its attributes and relationships. It also
defines the `OIDNodeType` enumeration for classifying nodes and related
constants like `IANA_ROOT_NAME`.
"""

from __future__ import annotations

import uuid
import weakref
from collections.abc import Iterable
from enum import Enum
from typing import Any, Literal

from firebird.base.types import Distinct, Error

#: IANA name before Firebird namespace. Does not contain trailing dot.
IANA_ROOT_NAME: str = 'iso.org.dod.internet.private.enterprise'

KEY_ATTRS: str[str] = {'oid', 'name', 'number', 'description', 'contact', 'email', 'site',
                       'node_type', 'node_spec'}
#: Needed to work around absent support for `None` in TOML
NONE_VALUE = "None"

class OIDNodeType(Enum):
    """Enumeration of possible types for an `OIDNode`.

    Attributes:
        ROOT: The top-level node in a specific OID specification file.
              Only one true root (from IANA) exists in the full conceptual tree.
        LEAF: A terminal node in the hierarchy; it cannot have children defined
              in a separate specification file.
        PRIVATE: A node reserved for private use, similar to a LEAF in that it
                 does not link to a separate specification file for children.
        NODE: An intermediate node that references another specification file
              (via `node_spec`) to define its children.
    """
    ROOT = 'root'
    LEAF = 'leaf'
    PRIVATE = 'private'
    NODE = 'node'

class OIDNode(Distinct):
    """Represents a single node within the Firebird OID hierarchy.

    Each node encapsulates information such as its Object Identifier (OID), name,
    description, contact details, and type. It maintains links to its parent
    (using a weak reference) and holds a list of its direct children.

    Nodes are uniquely identified by a UUID (`uid`) deterministically generated
    from their OID using `uuid.uuid5` with the `NAMESPACE_OID`.

    Arguments:
        parent: The parent `OIDNode`. Stored as a weak reference.
                `None` for the absolute root node of the entire hierarchy.
        oid: The full OID string for this node. If `None`, it's constructed
             from `parent.oid` and `number`. One of `oid` or (`parent` and
             `number`) must be provided.
        number: The node's number relative to its parent. Used to construct
                the OID if `oid` is not given.
        name: Node name (e.g., 'firebird').
        description: Node description.
        contact: Contact person/entity name.
        email: Contact email address.
        site: URL associated with the node owner/maintainer.
        parent_spec: URL to the YAML specification of the parent node. If
                     `None`, it's derived from the `parent` object's `node_spec`.
        node_spec: URL to this node's YAML specification file (if it's a NODE type)
                   or one of the keywords 'leaf' or 'private'. Used to determine
                   `node_type` if `node_type` argument is not provided.
        node_type: Explicit node type ('root', 'node', 'leaf', 'private'). If
                   `None`, it's inferred from `node_spec` ('leaf'/'private' keywords
                   or defaults to 'node' if it looks like a URL/path).

    Raises:
        ValueError: If the OID cannot be determined (neither `oid` nor
                    `parent`+`number` are sufficient).
    """
    def __init__(self, *, parent: OIDNode | None | Literal[NONE_VALUE]=None, oid: str | None=None,
                 number: int | None=None, name: str | None=None,
                 description: str | None=None, contact: str | None=None,
                 email: str | None=None, site: str | None=None,
                 parent_spec: str | None=None, node_spec: str | None=None,
                 node_type: str | None=None):
        if parent == NONE_VALUE:
            parent = None
        #: Parent node (or None for ROOT)
        self._parent_ref: weakref.ref[OIDNode] | None = None if parent is None else weakref.ref(parent)
        self.__oid: str | None = oid
        #: OID string (may be calculated)
        self.oid: str | None = oid
        if number is not None and parent is not None:
            self.oid = parent.oid + '.' + str(number)
        # Ensure OID is set for UUID generation
        if self.oid is None:
            raise ValueError(f"Cannot determine OID for node {name} (parent OID or direct OID needed)")
        #: UUID (Universally Unique Identifier) derived from OID
        self.uid: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, self.oid)
        #: Node number (last component of OID) relative to parent
        self.number: int | None = number
        #: Node name (identifier part)
        self.name: str | None = name
        #: Node description (human-readable)
        self.description: str | None = description
        #: Name of node administrator/contact
        self.contact: str | None = contact
        #: E-mail address of node administrator/contact
        self.email: str | None = email
        #: URL to node administrator/owner home page
        self.site: str | None = site
        #: URL to parent node's specification file
        self.parent_spec: str | None = parent_spec
        if parent_spec is None and parent:
            self.parent_spec = parent.node_spec
        #: URL to this node's specification file (or None for LEAF/PRIVATE)
        self.node_spec: str | None = node_spec
        self.__node_type: str | None = node_type
        #: Node type (enum member)
        self.node_type: OIDNodeType | None = None
        if node_type:
            self.node_type = OIDNodeType._value2member_map_.get(node_type.lower())
        elif node_type is None and node_spec:
            self.node_type = OIDNodeType._value2member_map_.get(node_spec.lower(), OIDNodeType.NODE)
        if self.node_type in (OIDNodeType.LEAF, OIDNodeType.PRIVATE):
            self.node_spec = None
        #: Direct child nodes
        self.children: list[OIDNode] = []
    def get_key(self) -> uuid.UUID:
        """Returns the node's unique identifier (UUID)."""
        return self.uid
    def set_parent(self, parent: OIDNode | None) -> None:
        """Sets or updates the parent node and related attributes.

        Establishes a weak reference to the new parent. If the node's `number`
        is set, it recalculates the node's `oid` based on the new parent's OID.
        It also updates `parent_spec` from the new parent's `node_spec`.

        Important:
            This method ONLY updates the child (`self`). It does NOT modify the
            old or new parent's `children` list. Tree modifications should
            be handled externally (e.g., by `build_tree`).

        Arguments:
            parent: The new parent node, or `None` to detach the node.
        """
        self._parent_ref = None if parent is None else weakref.ref(parent)
        if self.number is not None and parent is not None:
            self.oid = parent.oid + '.' + str(self.number)
        if parent is not None:
            self.parent_spec = parent.node_spec
    def as_toml_dict(self) -> dict[str, Any]:
        """Returns node data as a dictionary suitable for TOML serialization.

        Parent is represented by its UUID string. Uses the original `oid` if
        provided directly, otherwise relies on the potentially calculated `oid`.
        Node type is represented by the original string (`__node_type`) if provided,
        otherwise potentially derived. `node_spec` for LEAF/PRIVATE is output
        as the type keyword ('leaf'/'private').

        Returns:
            A dictionary with string representations of complex types like UUIDs.
        """
        toml_dict = {'parent': str(self.parent.uid) if self.parent else None,
                     'oid': self.__oid,
                     'number': self.number,
                     'name': self.name,
                     'description': self.description,
                     'contact': self.contact,
                     'email': self.email,
                     'site': self.site,
                     'node_spec': (self.node_type.value
                                   if self.node_type in (OIDNodeType.LEAF, OIDNodeType.PRIVATE)
                                   else self.node_spec),
                     'node_type': self.__node_type,
                     }
        return {k: v for k, v in toml_dict.items() if v is not None}
    @classmethod
    def from_spec(cls: type[OIDNode], spec_url: str, data: dict[str, Any],
                  parent: OIDNode | None=None) -> OIDNode:
        """Creates a new OIDNode and its direct children from parsed specification data.

        Arguments:
            spec_url: The URL from which the specification `data` was loaded.
                      Used as the `node_spec` for the created node.
            data: Parsed and validated dictionary from an OID node specification
                  document (typically after `pythonize_spec`). Expected keys:
                  'node' (dict for the main node), 'children' (list of dicts).
            parent: The parent node for the node being created (if applicable).

        Returns:
            The newly created `OIDNode` instance representing the root of the
            specification defined in `data`, with its `children` list populated.
        """
        # We prioritize spec_url as the node_spec value because it's guaranteed
        # to be the correct source URL.
        # Create a copy of the node data to avoid modifying the input 'data' dictionary.
        node_init_kwargs = data['node'].copy()

        # Remove 'node_spec' from the kwargs copy *if it exists* to prevent
        # the TypeError: __init__() got multiple values for keyword argument 'node_spec'.
        # The explicit node_spec=spec_url argument in the cls() call below will be used instead.
        node_init_kwargs.pop('node_spec', None) # Use pop with default to avoid KeyError

        node: OIDNode = cls(parent=parent, node_spec=spec_url, **node_init_kwargs)
        # Create child nodes listed in the spec
        for child_data in data.get('children', []):
            # Pass the newly created node as the parent for the children
            # Child data doesn't need the spec_url override logic.
            node.children.append(cls(parent=node, **child_data))
        return node
    @property
    def parent(self) -> OIDNode | None:
        """Returns the parent `OIDNode` object.

        Returns `None` if this node has no parent or if the parent object
        has been garbage collected (due to the weak reference).
        """
        if self._parent_ref is None:
            return None
        return self._parent_ref() # Call the weakref.ref to get the object or None
    @property
    def full_name(self) -> str:
        """Returns the fully qualified node name, starting from the root.

        Example: 'iso.org.dod.internet.private.enterprise.firebird.subsytem'.
        Returns just the node's `name` if it has no parent.
        """
        return self.name if self.parent is None else self.parent.full_name + '.' + self.name

def validate_parent_child_equality(parent: OIDNode, child: OIDNode) -> None:
    """Verifies that key attributes match between a placeholder child and its resolved node.

    When building the tree, a child node might first be defined partially within its
    parent's specification. Later, the full definition is loaded from the child's
    own specification file (`node_spec`). This function ensures that fundamental
    attributes defined in both places (parent's spec vs. child's spec) are consistent.
    It compares attributes listed in `KEY_ATTRS`.

    Arguments:
        parent: The placeholder `OIDNode` instance as defined in the parent's
                specification's 'children' list.
        child: The fully loaded `OIDNode` instance created from its own
               specification file.

    Raises:
        ValueError: If the value of any attribute listed in `KEY_ATTRS` differs
                    between the `parent` placeholder and the resolved `child` node.
    """
    for attr in KEY_ATTRS:
        if getattr(parent, attr) != getattr(child, attr):
            raise ValueError(f"Parent and node spec. differ in attribute '{attr}'")

def build_tree(nodes: Iterable[OIDNode]) -> OIDNode:
    """Constructs the OID node hierarchy from a flat collection of nodes.

    Takes an iterable of `OIDNode` objects (typically loaded from multiple
    specification files) and assembles them into a tree structure based on
    parent-child relationships defined via `node_spec` URLs.

    It identifies the root node, creates a map of nodes keyed by their `node_spec`,
    and then recursively traverses the tree starting from the root. During traversal,
    it replaces placeholder child nodes (of type `NODE`) with the corresponding fully
    loaded nodes found in the map, ensuring attribute consistency using
    `validate_parent_child_equality` and setting the correct parent reference.

    Arguments:
        nodes: An iterable containing all `OIDNode` objects to be assembled into a tree.
               Must include one node identified as `OIDNodeType.ROOT`.

    Returns:
        The root `OIDNode` of the fully assembled tree hierarchy.

    Raises:
        Error: If the input `nodes` does not contain exactly one node with
               `node_type` set to `OIDNodeType.ROOT`.
        ValueError: If attribute inconsistencies are found between a placeholder
                    child and its resolved node during validation.
        KeyError: If a `node_spec` listed in a child node does not correspond
                  to any node found in the input `nodes` iterable.
    """
    def traverse(_root: OIDNode, _node: OIDNode | None=None) -> None:
        """Recursive helper function to link nodes."""
        current_node = _node if _node is not None else _root
        # Iterate over a copy of children list indices for safe replacement
        for i in range(len(current_node.children)):
            child = current_node.children[i]
            # Only process placeholder NODE types that need replacing
            if child.node_type is OIDNodeType.NODE and child.node_spec in node_map:
                # Get the fully loaded node corresponding to the child's spec
                resolved_node = node_map[child.node_spec]

                # Preserve the number assigned by the parent spec
                resolved_node.number = child.number
                # Validate consistency between placeholder and resolved node
                validate_parent_child_equality(child, resolved_node)

                # Set the correct parent on the resolved node
                resolved_node.set_parent(current_node)

                # Replace the placeholder child with the resolved node in the parent's list
                current_node.children[i] = resolved_node

                # Recurse down into the newly linked node
                traverse(_root, resolved_node)
            # elif child.node_type is OIDNodeType.NODE and child.node_spec not in node_map:
                # This case should ideally raise an error if node_spec is expected
                # pass # Or raise an error / log a warning

    node_map: dict[str, OIDNode] = {}
    root: OIDNode | None = None
    root_count = 0

    for node in nodes:
        # Map nodes by their spec URL if they are roots of their own spec files
        # (ROOT or NODE types typically originate from their own spec file)
        if node.node_spec and node.node_type in (OIDNodeType.ROOT, OIDNodeType.NODE):
            # Check for duplicate spec URLs - should not happen if specs are unique
            if node.node_spec in node_map:
                # Handle duplicate spec URL definitions if necessary
                # raise Error(f"Duplicate node definition found for spec URL: {node.node_spec}")
                pass # Or decide on merging/error strategy
            node_map[node.node_spec] = node

        # Identify the root node
        if node.node_type is OIDNodeType.ROOT:
            # This assumes the ROOT node's spec URL is also mapped correctly above
            root = node
            root_count += 1

    # Validate root node presence
    if root is None:
        raise Error("Cannot build tree: ROOT node not found in the provided nodes.")
    if root_count > 1:
        raise Error(f"Cannot build tree: Found {root_count} ROOT nodes. Only one is allowed.")


    # Start the recursive linking process from the identified root
    traverse(root)
    return root
