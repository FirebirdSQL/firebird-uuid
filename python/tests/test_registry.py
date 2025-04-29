# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-uuid
# FILE:           tests/test_registry.py
# DESCRIPTION:    Tests for firebird.uuid._registry.py module
# CREATED:        28.4.2025
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
# Copyright (c) 20225 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""
"""

# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT

import pytest
import uuid
from queue import SimpleQueue
from tomllib import loads

from tomli_w import dumps
from firebird.base.types import Error, STOP
from firebird.base.collections import Registry

from firebird.uuid._registry import OIDRegistry, oid_registry
from firebird.uuid._model import OIDNode, OIDNodeType, build_tree

# --- Fixtures ---

# Use fixtures from test__model if available, otherwise redefine basic ones
@pytest.fixture
def root_node_data():
    """Basic data for a root node."""
    return {
        'oid': '1.3.6.1.4.1.53446',
        'name': 'firebird',
        'description': 'Firebird Foundation OID root',
        'contact': 'Firebird Foundation',
        'email': 'admin@firebirdsql.org',
        'site': 'https://firebirdsql.org',
        'parent_spec': '', # Empty string for root in spec data typically
        'node_spec': 'http://example.com/root.oid',
        'node_type': 'root',
        # number is usually not in the 'node' section of spec
    }

@pytest.fixture
def child_node_data_1():
    """Basic data for a child node (placeholder before linking)."""
    return {
        'number': 1,
        'name': 'subsystem',
        'description': 'A subsystem OID branch',
        'contact': 'Sub Contact',
        'email': 'sub@example.com',
        'site': 'http://example.com/sub',
        'node_spec': 'http://example.com/subsystem.oid',
        # 'node_type' will be derived or set explicitly if needed
    }

@pytest.fixture
def child_node_data_leaf():
    """Basic data for a leaf child node."""
    return {
        'number': 2,
        'name': 'leafnode',
        'description': 'A leaf OID',
        'contact': 'Leaf Contact',
        'email': 'leaf@example.com',
        'site': 'http://example.com/leaf',
        'node_spec': 'leaf', # Keyword indicates type
    }

@pytest.fixture
def grandchild_data():
    """Data for a grandchild node (leaf)."""
    return {
        'number': 1,
        'name': 'detail',
        'description': 'A detail leaf OID',
        'contact': 'Detail Contact',
        'email': 'detail@example.com',
        'site': 'http://example.com/detail',
        'node_spec': 'leaf',
    }

@pytest.fixture
def root_node(root_node_data):
    """Create a root OIDNode instance."""
    # Adjust data slightly for direct OIDNode init if needed
    data = root_node_data.copy()
    data['parent'] = None
    # OIDNode init expects parent_spec=None for root, not ''
    data['parent_spec'] = None
    return OIDNode(**data)

@pytest.fixture
def child_node_1(root_node, child_node_data_1):
    """Create a child OIDNode instance linked to root."""
    return OIDNode(parent=root_node, **child_node_data_1)

@pytest.fixture
def child_node_leaf(root_node, child_node_data_leaf):
    """Create a leaf child OIDNode instance linked to root."""
    return OIDNode(parent=root_node, **child_node_data_leaf)

@pytest.fixture
def grandchild_node(child_node_1, grandchild_data):
    """Create a grandchild node linked to child_node_1."""
    return OIDNode(parent=child_node_1, **grandchild_data)


@pytest.fixture
def sample_spec_data_root(root_node_data, child_node_data_1, child_node_data_leaf):
    """Simulates parsed data from a root YAML specification."""
    return {
        'node': root_node_data.copy(),
        'children': [child_node_data_1.copy(), child_node_data_leaf.copy()]
    }

@pytest.fixture
def sample_spec_data_child(root_node, child_node_data_1, grandchild_data):
    """Simulates parsed data from a child YAML specification."""
    node_data = child_node_data_1.copy()
    node_data['oid'] = f"{root_node.oid}.{child_node_data_1['number']}"
    node_data['parent_spec'] = 'http://example.com/root.oid' # Link back
    node_data['node_type'] = 'node'
    del node_data['number']

    return {
        'node': node_data,
        'children': [grandchild_data.copy()]
    }

@pytest.fixture
def empty_registry():
    """Provides a clean OIDRegistry instance for tests."""
    return OIDRegistry()

@pytest.fixture(scope="function", autouse=True)
def reset_global_registry():
    """Fixture to clear the global oid_registry before/after each test function."""
    oid_registry._reg.clear()
    yield
    oid_registry._reg.clear()

# --- Test Class ---

class TestOIDRegistry:

    def test_get_root_empty(self, empty_registry):
        assert empty_registry.get_root() is None

    def test_get_root_no_root_node(self, empty_registry, child_node_1):
        # Manually add a non-root node
        empty_registry.store(child_node_1)
        assert empty_registry.get_root() is None

    def test_get_root_found(self, empty_registry, root_node, child_node_1):
        empty_registry.store(root_node)
        empty_registry.store(child_node_1) # Add another node
        found_root = empty_registry.get_root()
        assert found_root is root_node

    def test_update_from_specifications_single_root(self, empty_registry, sample_spec_data_root):
        spec_url = 'http://example.com/root.oid'
        specifications = {spec_url: sample_spec_data_root}

        empty_registry.update_from_specifications(specifications)

        # Check root node registered
        root = empty_registry.get_root()
        assert root is not None
        assert root.node_spec == spec_url
        assert root.oid == sample_spec_data_root['node']['oid']
        assert root.name == sample_spec_data_root['node']['name']
        assert len(root.children) == 2 # Children created but are placeholders

        # Check children registered (as separate nodes initially)
        assert len(empty_registry._reg) == 3 # Root + 2 children placeholders
        child1_placeholder = empty_registry.get(uuid.uuid5(uuid.NAMESPACE_OID, f"{root.oid}.1"))
        child2_placeholder = empty_registry.get(uuid.uuid5(uuid.NAMESPACE_OID, f"{root.oid}.2"))

        assert child1_placeholder is not None
        assert child1_placeholder.name == sample_spec_data_root['children'][0]['name']
        assert child1_placeholder.node_type == OIDNodeType.NODE # Derived
        assert child1_placeholder.node_spec == sample_spec_data_root['children'][0]['node_spec']
        assert child1_placeholder.parent == root # build_tree links placeholders initially

        assert child2_placeholder is not None
        assert child2_placeholder.name == sample_spec_data_root['children'][1]['name']
        assert child2_placeholder.node_type == OIDNodeType.LEAF # Derived
        assert child2_placeholder.node_spec is None
        assert child2_placeholder.parent == root

    def test_update_from_specifications_linked(self, empty_registry, sample_spec_data_root, sample_spec_data_child):
        root_spec_url = 'http://example.com/root.oid'
        child_spec_url = sample_spec_data_root['children'][0]['node_spec'] # 'http://example.com/subsystem.oid'

        specifications = {
            root_spec_url: sample_spec_data_root,
            child_spec_url: sample_spec_data_child
        }

        empty_registry.update_from_specifications(specifications)

        # Check root node registered
        root = empty_registry.get_root()
        assert root is not None
        assert root.node_spec == root_spec_url
        assert len(root.children) == 2

        # Check child 1 (should be replaced by node from child spec by build_tree)
        child1 = root.children[0]
        assert child1.node_spec == child_spec_url # Belongs to the child spec
        assert child1.name == sample_spec_data_child['node']['name'] # Name from child spec's node section
        assert child1.oid == sample_spec_data_child['node']['oid'] # OID updated by build_tree/set_parent
        assert child1.parent == root # Link established by build_tree

        # Check grandchild exists and is linked
        assert len(child1.children) == 1
        grandchild = child1.children[0]
        assert grandchild.name == sample_spec_data_child['children'][0]['name']
        assert grandchild.parent == child1
        assert grandchild.node_type == OIDNodeType.LEAF

        # Check child 2 (leaf placeholder remains)
        child2 = root.children[1]
        assert child2.name == sample_spec_data_root['children'][1]['name']
        assert child2.node_type == OIDNodeType.LEAF
        assert child2.parent == root

        # Check registry size: root + linked child1 + grandchild + leaf child2 = 4
        assert len(empty_registry._reg) == 4

    def test_as_toml_empty(self, empty_registry):
        toml_str = empty_registry.as_toml()
        assert toml_str.strip() == "" # Empty registry -> empty TOML
        # Verify it's valid TOML (even if empty)
        parsed = loads(toml_str)
        assert parsed == {}

    def test_as_toml_populated(self, empty_registry, root_node, child_node_1, child_node_leaf):
        # Build a simple tree manually
        root_node.children.append(child_node_1)
        root_node.children.append(child_node_leaf)
        empty_registry.store(root_node)
        empty_registry.store(child_node_1)
        empty_registry.store(child_node_leaf)

        toml_str = empty_registry.as_toml()
        parsed = loads(toml_str)

        assert len(parsed) == 3
        # Check keys are string UIDs
        assert str(root_node.uid) in parsed
        assert str(child_node_1.uid) in parsed
        assert str(child_node_leaf.uid) in parsed

        # Spot check root node data
        root_toml_data = parsed[str(root_node.uid)]
        assert root_toml_data['name'] == root_node.name
        assert root_toml_data['oid'] == root_node.oid # original oid stored
        assert 'parent' not in root_toml_data
        assert root_toml_data['node_type'] == root_node.node_type.value

        # Spot check child node data
        child1_toml_data = parsed[str(child_node_1.uid)]
        assert child1_toml_data['name'] == child_node_1.name
        assert child1_toml_data['number'] == child_node_1.number
        assert child1_toml_data['parent'] == str(root_node.uid)
        assert child1_toml_data['node_spec'] == child_node_1.node_spec

        # Spot check leaf node data
        leaf_toml_data = parsed[str(child_node_leaf.uid)]
        assert leaf_toml_data['name'] == child_node_leaf.name
        assert leaf_toml_data['node_spec'] == child_node_leaf.node_type.value # 'leaf'

    def test_update_from_toml_root_only(self, empty_registry, root_node):
        root_toml_dict = root_node.as_toml_dict()
        toml_data = {str(root_node.uid): root_toml_dict}
        toml_str = dumps(toml_data)

        empty_registry.update_from_toml(toml_str)

        assert len(empty_registry._reg) == 1
        reg_root = empty_registry.get_root()
        assert reg_root is not None
        assert reg_root.uid == root_node.uid
        assert reg_root.name == root_node.name
        assert reg_root.parent is None

    def test_update_from_toml_root_and_children(self, empty_registry, root_node, child_node_1, child_node_leaf):
        # Prepare TOML data
        toml_data = {
            str(root_node.uid): root_node.as_toml_dict(),
            str(child_node_1.uid): child_node_1.as_toml_dict(),
            str(child_node_leaf.uid): child_node_leaf.as_toml_dict(),
        }
        toml_str = dumps(toml_data)

        empty_registry.update_from_toml(toml_str)

        assert len(empty_registry._reg) == 3
        reg_root = empty_registry.get_root()
        assert reg_root is not None
        assert len(reg_root.children) == 2 # Check build_tree linked children

        # Verify children are linked correctly
        child_uids = {str(c.uid) for c in reg_root.children}
        assert str(child_node_1.uid) in child_uids
        assert str(child_node_leaf.uid) in child_uids

        # Check parent refs
        reg_child1 = empty_registry.get(child_node_1.uid)
        reg_leaf = empty_registry.get(child_node_leaf.uid)
        assert reg_child1.parent == reg_root
        assert reg_leaf.parent == reg_root

    def test_update_from_toml_existing_parent(self, empty_registry, root_node, child_node_1):
        # Pre-populate registry with root
        empty_registry.store(root_node)

        # Prepare TOML for child only
        toml_data = {str(child_node_1.uid): child_node_1.as_toml_dict()}
        toml_str = dumps(toml_data)

        empty_registry.update_from_toml(toml_str)

        assert len(empty_registry._reg) == 2 # Root + loaded child
        reg_root = empty_registry.get_root()
        reg_child1 = empty_registry.get(child_node_1.uid)

        assert reg_child1 is not None
        assert reg_child1.parent == reg_root # Should be linked
        assert len(reg_root.children) == 1
        assert reg_root.children[0].uid == child_node_1.uid

    def test_update_from_toml_dependent_nodes(self, empty_registry, root_node, child_node_1, grandchild_node):
        # Order in TOML shouldn't matter due to queue
        toml_data = {
            str(grandchild_node.uid): grandchild_node.as_toml_dict(), # Grandchild first
            str(root_node.uid): root_node.as_toml_dict(),
            str(child_node_1.uid): child_node_1.as_toml_dict(),
        }
        toml_str = dumps(toml_data)

        empty_registry.update_from_toml(toml_str)

        assert len(empty_registry._reg) == 3
        reg_root = empty_registry.get_root()
        reg_child1 = empty_registry.get(child_node_1.uid)
        reg_grandchild = empty_registry.get(grandchild_node.uid)

        assert reg_root is not None
        assert reg_child1 is not None
        assert reg_grandchild is not None

        # Check links
        assert reg_child1.parent == reg_root
        assert reg_grandchild.parent == reg_child1
        assert len(reg_root.children) == 1
        assert reg_root.children[0] == reg_child1
        assert len(reg_child1.children) == 1
        assert reg_child1.children[0] == reg_grandchild

    def test_update_from_toml_error_no_root_no_parent(self, empty_registry, child_node_1):
        # TOML only contains child, registry is empty
        toml_data = {str(child_node_1.uid): child_node_1.as_toml_dict()}
        toml_str = dumps(toml_data)

        with pytest.raises(Error, match="TOML does not define either root node or any node with registered parent"):
            empty_registry.update_from_toml(toml_str)

    def test_update_from_toml_error_root_conflict(self, empty_registry, root_node):
        # Add existing root
        empty_registry.store(root_node)

        # Create TOML for a *different* root node
        other_root_data = root_node.as_toml_dict()
        other_root_uid = uuid.uuid5(uuid.NAMESPACE_OID, "9.9.9") # Different UID
        other_root_data['oid'] = "9.9.9"
        other_root_data['node_type'] = 'root' # Make sure it's marked as root

        toml_data = {str(other_root_uid): other_root_data}
        toml_str = dumps(toml_data)

        with pytest.raises(Error, match=f"Root node {other_root_uid} does not match registered root"):
            empty_registry.update_from_toml(toml_str)

    def test_update_from_toml_error_orphan_nodes(self, empty_registry):
        # Create nodes where parent doesn't exist in TOML or registry
        orphan_uid = uuid.uuid4()
        non_existent_parent_uid = uuid.uuid4()
        orphan_data = {
            'name': 'orphan', 'number': 1, 'node_type': 'leaf',
             'parent': str(non_existent_parent_uid) # Parent will never be found
        }
        toml_data = {str(orphan_uid): orphan_data}
        toml_str = dumps(toml_data)

        # Expect error after queue fails to link
        with pytest.raises(Error, match="TOML does not define either root node or any node with registered parent"):
            empty_registry.update_from_toml(toml_str)

    def test_update_from_toml_error_no_parent_key(self, empty_registry):
        # Node is not root, but parent key is missing in TOML data
        non_root_uid = uuid.uuid4()
        bad_data = {
            'name': 'bad', 'number': 1,
             'node_type': 'leaf', # Clearly not root type
             # 'parent' key is missing
        }
        toml_data = {str(non_root_uid): bad_data}
        toml_str = dumps(toml_data)

        with pytest.raises(Error, match="TOML does not define either root node or any node with registered parent"):
            empty_registry.update_from_toml(toml_str)

    # Test the global instance briefly
    def test_global_registry_instance(self):
        assert isinstance(oid_registry, OIDRegistry)
        # Check it's initially empty (due to reset fixture)
        assert oid_registry.get_root() is None
        assert len(oid_registry._reg) == 0

        # Add something and check
        root = OIDNode(oid='1.2.3', name='test_root', node_type='root')
        oid_registry.store(root)
        assert oid_registry.get_root() is root
