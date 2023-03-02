#coding:utf-8
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
# Copyright (c) 2021 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Model for Firebird OID registry.

"""

from __future__ import annotations
from typing import List, Dict, Optional
from enum import Enum
from weakref import proxy
import uuid
from firebird.base.types import Distinct, Error

#: IANA name before Firebird namespace. Does not contain trailing dot.
IANA_ROOT_NAME = 'iso.org.dod.internet.private.enterprise'

KEY_ATTRS = ('oid', 'name', 'number', 'description', 'contact', 'email', 'site', 'node_type', 'node_spec')

class NodeType(Enum):
    ROOT = 'root'
    LEAF = 'leaf'
    PRIVATE = 'private'
    NODE = 'node'

class Node(Distinct):
    """OID node.

    Arguments:
        parent: Parent node (`None` for root node)
        oid: Node OID. When `None`, OID is constructed from parent OID and `number` parameter.
        number: Node order number in parent. Part of node OID for child nodes.
        name: Node name.
        description: Node description.
        contact: Contact person for this node.
        email: E-mail of contact person.
        site: URL to home site of node maintainer
        parent_spec: URL to YAML specification of parent node. If not specified, it's
          taken from `parent` node.
        node_spec: URL to node TAML specification
        node_type: Node type. If not specified, it's derived from `node_spec`.
    """
    def __init__(self, *, parent: Node=None, oid: str=None, number: int=None, name: str=None,
                 description: str=None, contact: str=None, email: str=None, site: str=None,
                 parent_spec: str=None, node_spec: str=None, node_type: str=None):
        #: Parent node (or None for ROOT)
        self.parent: Node = None if parent is None else proxy(parent)
        self.__oid: str = oid
        #: OID
        self.oid: str = oid
        if number is not None and parent is not None:
            self.oid = parent.oid + '.' + str(number)
        #: UUID
        self.uid: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, self.oid)
        #: Node number (OID part after parent node OID)
        self.number: int = number
        #: Node name
        self.name: str = name
        #: Node description
        self.description: str = description
        #: Name of node administrator
        self.contact: str = contact
        #: E-mail to node administrator
        self.email: str = email
        #: URL to node administrator home
        self.site: str = site
        #: URL to parent node specification
        self.parent_spec: str = parent_spec
        if parent_spec is None and parent:
            self.parent_spec = parent.node_spec
        #: URL to node specification
        self.node_spec: Optional[str] = node_spec
        self.__node_type: NodeType = node_type
        #: Node type
        self.node_type: NodeType = None
        if node_type:
            self.node_type = NodeType._value2member_map_.get(node_type.lower())
        elif node_type is None and node_spec:
            self.node_type = NodeType._value2member_map_.get(node_spec.lower(), NodeType.NODE)
        if self.node_type in (NodeType.LEAF, NodeType.PRIVATE):
            self.node_spec = None
        #: Child nodes
        self.children: List[Node] = []
    def get_key(self) -> uuid.UUID:
        "Returns node key -> UID"
        return self.uid
    def set_parent(self, parent: Node) -> None:
        """Set new parent node.

        Important: This method does NOT change the parent's children list!
        """
        self.parent = None if parent is None else proxy(parent)
        if self.number is not None and parent is not None:
            self.oid = parent.oid + '.' + str(self.number)
        if parent is not None:
            self.parent_spec = parent.node_spec
    def as_toml_dict(self) -> Dict:
        """Returns dictionary with instance data suitable for storage in TOML format
        (values that are not of basic type are converted to string).
        """
        return {'parent': str(self.parent.uid) if self.parent else None,
                'oid': self.__oid,
                'number': self.number,
                'name': self.name,
                'description': self.description,
                'contact': self.contact,
                'email': self.email,
                'site': self.site,
                'node_spec': (self.node_type.value
                              if self.node_type in (NodeType.LEAF, NodeType.PRIVATE)
                              else self.node_spec),
                'node_type': self.__node_type,
                }
    @classmethod
    def from_spec(cls: Node, spec_url: str, data: Tuple[Dict], parent: Node=None) -> Node:
        """Returns new node from specification.

        Arguments:
          spec_url: Source URL for specification.
          data:     Parsed and validated data from OID node specification document
          parent:   Parent node.
        """
        node: Node = cls(parent=parent, node_spec=spec_url, **data['node'])
        for child in data['children']:
            node.children.append(cls(parent=node, **child))
        return node
    @property
    def full_name(self) -> str:
        "Full node name (from root node)"
        return self.name if self.parent is None else self.parent.full_name + '.' + self.name

def validate_parent_child_equality(parent: Node, child: Node) -> None:
    """Check that `KEY_ATTRS` in parent and child node are equal.

    Used when child node is merged (replaced) with equvalent node from linked specification.

    Raises:
      ValueError: If values of any checked attribute differ.
    """
    for attr in KEY_ATTRS:
        if getattr(parent, attr) != getattr(child, attr):
            raise ValueError(f"Parent and node spec. differ in attribute '{attr}'")

def build_tree(nodes: List[Node]) -> Node:
    """Returns root node of node tree assmebled from list of nodes.

    Arguments:
      nodes: List of nodes. Must contain ROOT node.

    Raises:
      Error: If list of nodes does not contain ROOT node.
    """
    def traverse(_root: Node, _node: Node=None) -> None:
        if _node is None:
            _node = _root
        for i, child in enumerate(_node.children):
            if child.node_type is NodeType.NODE:
                sub_node = node_map[child.node_spec]
                sub_node.number = child.number
                validate_parent_child_equality(child, sub_node)
                sub_node.set_parent(_node)
                _node.children[i] = sub_node
                traverse(_root, sub_node)

    node_map: Dict[str, Node] = {}
    root: Node = None
    for node in nodes:
        node_map[node.node_spec] = node
        if node.node_type is NodeType.ROOT:
            root = node
    if root is None:
        raise Error("ROOT node not found")
    #
    traverse(root)
    return root

