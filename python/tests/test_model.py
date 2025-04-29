# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-uuid
# FILE:           tests/test_model.py
# DESCRIPTION:    Tests for firebird.uuid._model.py module
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

import pytest
import uuid
from weakref import ReferenceType
from firebird.base.types import Distinct, Error
from firebird.uuid._model import (
    OIDNode, OIDNodeType, IANA_ROOT_NAME, KEY_ATTRS, NONE_VALUE,
    validate_parent_child_equality, build_tree
)

# --- Fixtures ---

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
        'parent_spec': None, # Explicitly None for root
        'node_spec': 'http://example.com/root.oid',
        'node_type': 'root',
        'number': None # Root node number is typically implicit/None
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
def child_node_data_private():
    """Basic data for a private child node."""
    return {
        'number': 3,
        'name': 'privatenode',
        'description': 'A private OID branch',
        'contact': 'Private Contact',
        'email': 'private@example.com',
        'site': 'http://example.com/private',
        'node_spec': 'private', # Keyword indicates type
    }


@pytest.fixture
def root_node(root_node_data):
    """Create a root OIDNode instance."""
    # Remove number explicitly as it's not used for root init usually
    data = root_node_data.copy()
    del data['number']
    return OIDNode(parent=None, **data)

@pytest.fixture
def child_node_1(root_node, child_node_data_1):
    """Create a child OIDNode instance linked to root."""
    return OIDNode(parent=root_node, **child_node_data_1)

@pytest.fixture
def child_node_leaf(root_node, child_node_data_leaf):
    """Create a leaf child OIDNode instance linked to root."""
    return OIDNode(parent=root_node, **child_node_data_leaf)

@pytest.fixture
def child_node_private(root_node, child_node_data_private):
    """Create a private child OIDNode instance linked to root."""
    return OIDNode(parent=root_node, **child_node_data_private)

@pytest.fixture
def sample_spec_data(root_node_data, child_node_data_1, child_node_data_leaf):
    """Simulates data parsed from a root YAML specification."""
    # Use copies to avoid modifying fixture data directly
    root_data_copy = root_node_data.copy()
    # parent_spec for root should be None or empty in YAML, handle in from_spec
    if root_data_copy['parent_spec'] is None:
        root_data_copy['parent_spec'] = '' # Typical YAML representation

    return {
        'node': root_data_copy,
        'children': [child_node_data_1.copy(), child_node_data_leaf.copy()]
    }

@pytest.fixture
def sample_child_spec_data(child_node_data_1):
    """Simulates data parsed from a child YAML specification (e.g., subsystem.oid)."""
    # The child node becomes the root of its own spec file
    node_data = child_node_data_1.copy()
    node_data['oid'] = '1.3.6.1.4.1.53446.1' # Full OID needed in spec's node section
    node_data['parent_spec'] = 'http://example.com/root.oid' # Link back to parent spec
    node_data['node_type'] = 'node' # Usually explicit in the child spec node
    del node_data['number'] # Number isn't part of the 'node' section data usually

    grandchild_data = {
        'number': 1,
        'name': 'detail',
        'description': 'A detail leaf OID',
        'contact': 'Detail Contact',
        'email': 'detail@example.com',
        'site': 'http://example.com/detail',
        'node_spec': 'leaf',
    }
    return {
        'node': node_data,
        'children': [grandchild_data]
    }

# --- Test Class for OIDNode ---

class TestOIDNode:

    def test_oidnode_init_root(self, root_node, root_node_data):
        assert root_node.parent is None
        assert root_node.oid == root_node_data['oid']
        assert root_node.number is None
        assert root_node.name == root_node_data['name']
        assert root_node.description == root_node_data['description']
        assert root_node.contact == root_node_data['contact']
        assert root_node.email == root_node_data['email']
        assert root_node.site == root_node_data['site']
        assert root_node.parent_spec is None # Explicitly None for root init
        assert root_node.node_spec == root_node_data['node_spec']
        assert root_node.node_type == OIDNodeType.ROOT
        assert isinstance(root_node.uid, uuid.UUID)
        expected_uid = uuid.uuid5(uuid.NAMESPACE_OID, root_node_data['oid'])
        assert root_node.uid == expected_uid
        assert root_node.children == []

    def test_oidnode_init_child_with_number(self, root_node, child_node_1, child_node_data_1):
        assert isinstance(child_node_1.parent, OIDNode)
        assert child_node_1.parent is root_node # weakref proxy comparison works
        assert child_node_1.number == child_node_data_1['number']
        expected_oid = f"{root_node.oid}.{child_node_data_1['number']}"
        assert child_node_1.oid == expected_oid
        assert child_node_1.name == child_node_data_1['name']
        assert child_node_1.node_spec == child_node_data_1['node_spec']
        # Type derived from node_spec (URL -> NODE)
        assert child_node_1.node_type == OIDNodeType.NODE
        # Parent spec inherited from parent's node_spec
        assert child_node_1.parent_spec == root_node.node_spec
        expected_uid = uuid.uuid5(uuid.NAMESPACE_OID, expected_oid)
        assert child_node_1.uid == expected_uid

    def test_oidnode_init_child_with_explicit_oid(self, root_node):
        # Initialize child providing full OID instead of number
        explicit_oid = root_node.oid + ".5"
        child = OIDNode(parent=root_node, oid=explicit_oid, name='explicit_child')
        assert child.oid == explicit_oid
        assert child.number is None # Number wasn't provided
        assert child.parent is root_node
        expected_uid = uuid.uuid5(uuid.NAMESPACE_OID, explicit_oid)
        assert child.uid == expected_uid

    def test_oidnode_init_child_with_oid_and_number(self, root_node):
        # If both OID and number are given, number+parent takes precedence for OID calculation
        explicit_oid_ignored = root_node.oid + ".99"
        number = 6
        expected_oid = root_node.oid + f".{number}"
        child = OIDNode(parent=root_node, oid=explicit_oid_ignored, number=number, name='num_prec')
        assert child.oid == expected_oid # OID calculated from parent+number
        assert child.number == number
        assert child.parent is root_node

    def test_oidnode_init_node_type_derivation(self, root_node):
        # 1. Keyword 'leaf'
        child_l = OIDNode(parent=root_node, number=10, name='l', node_spec='leaf')
        assert child_l.node_type == OIDNodeType.LEAF
        assert child_l.node_spec is None # Cleared for leaf/private

        # 2. Keyword 'private'
        child_p = OIDNode(parent=root_node, number=11, name='p', node_spec='private')
        assert child_p.node_type == OIDNodeType.PRIVATE
        assert child_p.node_spec is None # Cleared for leaf/private

        # 3. URL -> NODE
        child_n = OIDNode(parent=root_node, number=12, name='n', node_spec='http://a.b/c.oid')
        assert child_n.node_type == OIDNodeType.NODE
        assert child_n.node_spec == 'http://a.b/c.oid' # Not cleared

        # 4. Explicit type overrides node_spec derivation
        child_expl = OIDNode(parent=root_node, number=13, name='expl', node_spec='http://a.b/c.oid', node_type='leaf')
        assert child_expl.node_type == OIDNodeType.LEAF
        assert child_expl.node_spec is None # Cleared because final type is LEAF

        # 5. Unknown type string -> None
        child_unk = OIDNode(parent=root_node, number=14, name='unk', node_type='invalid')
        assert child_unk.node_type is None

        # 6. node_spec looks like keyword but isn't -> NODE
        child_maybe = OIDNode(parent=root_node, number=15, name='maybe', node_spec='nodeish')
        assert child_maybe.node_type == OIDNodeType.NODE
        assert child_maybe.node_spec == 'nodeish'


    def test_oidnode_init_parent_spec_handling(self, root_node):
        # Inherits if not provided
        child_inh = OIDNode(parent=root_node, number=20, name='inh')
        assert child_inh.parent_spec == root_node.node_spec

        # Uses provided value if given
        explicit_parent_spec = 'http://explicit.com/parent.oid'
        child_expl = OIDNode(parent=root_node, number=21, name='expl', parent_spec=explicit_parent_spec)
        assert child_expl.parent_spec == explicit_parent_spec

    def test_oidnode_get_key(self, root_node):
        assert root_node.get_key() == root_node.uid
        assert isinstance(root_node.get_key(), uuid.UUID)

    def test_oidnode_full_name(self, root_node):
        child1 = OIDNode(parent=root_node, number=1, name='child1')
        child2 = OIDNode(parent=child1, number=1, name='child2')
        assert root_node.full_name == 'firebird'
        assert child1.full_name == 'firebird.child1'
        assert child2.full_name == 'firebird.child1.child2'

    def test_oidnode_set_parent(self, root_node):
        original_parent = OIDNode(oid='9.9.9', name='orig_parent', node_spec='orig.oid')
        child = OIDNode(parent=original_parent, number=1, name='c')
        assert child.parent is original_parent
        assert child.oid == '9.9.9.1'
        assert child.parent_spec == 'orig.oid'

        # Set new parent (root_node)
        child.set_parent(root_node)
        expected_oid = f"{root_node.oid}.1"
        assert isinstance(child.parent, OIDNode)
        assert child.parent is root_node
        assert child.number == 1 # Should be preserved if not None
        assert child.oid == expected_oid # OID updated
        assert child.parent_spec == root_node.node_spec # parent_spec updated

        # Set parent to None
        child.set_parent(None)
        assert child.parent is None
        assert child.oid == expected_oid # OID not changed if parent is None
        assert child.parent_spec == root_node.node_spec # parent_spec not changed

    def test_oidnode_as_toml_dict(self, root_node, child_node_1, child_node_leaf, child_node_private):
        # Root node
        root_toml = root_node.as_toml_dict()
        assert 'parent' not in root_toml
        assert root_toml['oid'] == root_node.oid # Stores original OID if given
        assert 'number' not in root_toml
        assert root_toml['name'] == root_node.name
        assert root_toml['description'] == root_node.description
        assert root_toml['contact'] == root_node.contact
        assert root_toml['email'] == root_node.email
        assert root_toml['site'] == root_node.site
        assert root_toml['node_spec'] == root_node.node_spec # Normal URL
        assert root_toml['node_type'] == root_node.node_type.value # Original type string

        # Child node (type NODE)
        child1_toml = child_node_1.as_toml_dict()
        assert child1_toml['parent'] == str(root_node.uid)
        assert 'oid' not in child1_toml
        assert child1_toml['number'] == child_node_1.number
        assert child1_toml['name'] == child_node_1.name
        assert child1_toml['node_spec'] == child_node_1.node_spec # Normal URL
        assert 'node_type' not in child1_toml

        # Child node (type LEAF)
        leaf_toml = child_node_leaf.as_toml_dict()
        assert leaf_toml['parent'] == str(root_node.uid)
        assert 'oid' not in leaf_toml
        assert leaf_toml['number'] == child_node_leaf.number
        assert leaf_toml['name'] == child_node_leaf.name
        assert leaf_toml['node_spec'] == OIDNodeType.LEAF.value # Keyword stored
        assert 'node_type' not in leaf_toml

        # Child node (type PRIVATE)
        private_toml = child_node_private.as_toml_dict()
        assert private_toml['parent'] == str(root_node.uid)
        assert 'oid' not in private_toml
        assert private_toml['number'] == child_node_private.number
        assert private_toml['name'] == child_node_private.name
        assert private_toml['node_spec'] == OIDNodeType.PRIVATE.value # Keyword stored
        assert 'node_type' not in private_toml

    def test_oidnode_from_spec(self, sample_spec_data):
        spec_url = 'http://example.com/root.oid'
        node = OIDNode.from_spec(spec_url, sample_spec_data, parent=None)

        # Check node itself
        assert node.parent is None
        assert node.oid == sample_spec_data['node']['oid']
        assert node.name == sample_spec_data['node']['name']
        assert node.node_spec == spec_url # Set from argument
        assert node.node_type == OIDNodeType.ROOT

        # Check children created
        assert len(node.children) == 2

        # Check child 1 (placeholder)
        child1_data = sample_spec_data['children'][0]
        child1_node = node.children[0]
        assert child1_node.parent is node
        assert child1_node.number == child1_data['number']
        assert child1_node.name == child1_data['name']
        assert child1_node.node_spec == child1_data['node_spec']
        assert child1_node.oid == f"{node.oid}.{child1_data['number']}"
        assert child1_node.node_type == OIDNodeType.NODE # Derived from URL

        # Check child 2 (leaf)
        child2_data = sample_spec_data['children'][1]
        child2_node = node.children[1]
        assert child2_node.parent is node
        assert child2_node.number == child2_data['number']
        assert child2_node.name == child2_data['name']
        assert child2_node.node_spec is None # Cleared for leaf
        assert child2_node.oid == f"{node.oid}.{child2_data['number']}"
        assert child2_node.node_type == OIDNodeType.LEAF # Derived from keyword


# --- Test standalone functions ---

def test_validate_parent_child_equality_ok(child_node_1):
    # Create an almost identical node (e.g., from a loaded spec)
    # Ensure KEY_ATTRS match
    node_from_spec = OIDNode(parent=None, # Parent doesn't matter for comparison itself
                             oid=child_node_1.oid,
                           number=child_node_1.number,
                           name=child_node_1.name,
                           description=child_node_1.description,
                           contact=child_node_1.contact,
                           email=child_node_1.email,
                           site=child_node_1.site,
                           node_spec=child_node_1.node_spec,
                           node_type=child_node_1.node_type.value if child_node_1.node_type else None)

    # Should not raise error
    validate_parent_child_equality(child_node_1, node_from_spec)

@pytest.mark.parametrize("attr_to_change", [
    pytest.param('oid', id='oid_differs'),
    pytest.param('name', id='name_differs'),
    pytest.param('number', id='number_differs'),
    pytest.param('description', id='description_differs'),
    pytest.param('contact', id='contact_differs'),
    pytest.param('email', id='email_differs'),
    pytest.param('site', id='site_differs'),
    pytest.param('node_type', id='node_type_differs'),
    pytest.param('node_spec', id='node_spec_differs'),
])
def test_validate_parent_child_equality_differs(child_node_1, attr_to_change):
    # Create a node that differs in one attribute
    node_data = {attr: getattr(child_node_1, attr) for attr in KEY_ATTRS}
    node_data['parent'] = None # Parent doesn't matter for comparison itself
    # Convert node_type back to string if necessary
    if 'node_type' in node_data and isinstance(node_data['node_type'], OIDNodeType):
        node_data['node_type'] = node_data['node_type'].value

    # Change one attribute to be different
    if isinstance(node_data[attr_to_change], str):
        node_data[attr_to_change] = (node_data[attr_to_change] or "") + "_changed"
    elif isinstance(node_data[attr_to_change], int):
        node_data[attr_to_change] = (node_data[attr_to_change] or 0) + 1
    elif attr_to_change == 'node_type': # Handle OIDNodeType enum comparison
        # Find a different valid type string
        current_type_val = node_data[attr_to_change]
        all_types = [t.value for t in OIDNodeType]
        node_data[attr_to_change] = next(t for t in all_types if t != current_type_val)
    else: # Handle None vs value
        node_data[attr_to_change] = "was_none" if node_data[attr_to_change] is None else None

    node_from_spec = OIDNode(**node_data)

    with pytest.raises(ValueError, match=f"Parent and node spec. differ in attribute '{attr_to_change}'"):
        validate_parent_child_equality(child_node_1, node_from_spec)


def test_build_tree_ok(sample_spec_data, sample_child_spec_data):
    # Simulate loading nodes from specifications
    root_spec_url = 'http://example.com/root.oid'
    child_spec_url = sample_spec_data['children'][0]['node_spec'] # e.g., 'http://example.com/subsystem.oid'

    root = OIDNode.from_spec(root_spec_url, sample_spec_data)
    # The actual node corresponding to the placeholder child
    child1_full = OIDNode.from_spec(child_spec_url, sample_child_spec_data, parent=None) # Parent set during build

    nodes_list = [root, child1_full]

    # Build the tree
    assembled_root = build_tree(nodes_list)

    # Check root is correct
    assert assembled_root is root

    # Check children of root
    assert len(assembled_root.children) == 2

    # Check Child 1 (was placeholder, now replaced)
    linked_child1 = assembled_root.children[0]
    assert linked_child1 is child1_full # Should be the instance from the list
    assert linked_child1.parent is assembled_root
    assert linked_child1.number == sample_spec_data['children'][0]['number'] # Number from original placeholder
    assert linked_child1.oid == f"{root.oid}.{sample_spec_data['children'][0]['number']}" # OID updated
    assert linked_child1.parent_spec == root.node_spec # Parent spec updated

    # Check grandchild (was created by child1_full from its spec)
    assert len(linked_child1.children) == 1
    grandchild = linked_child1.children[0]
    assert grandchild.name == sample_child_spec_data['children'][0]['name']
    assert grandchild.parent is linked_child1
    assert grandchild.number == sample_child_spec_data['children'][0]['number']
    assert grandchild.node_type == OIDNodeType.LEAF

    # Check Child 2 (was already leaf, unchanged instance)
    leaf_child = assembled_root.children[1]
    assert leaf_child.name == sample_spec_data['children'][1]['name']
    assert leaf_child.node_type == OIDNodeType.LEAF
    assert leaf_child.parent is assembled_root


def test_build_tree_no_root(child_node_1):
    nodes_list = [child_node_1] # List without a root node
    with pytest.raises(Error, match="ROOT node not found"):
        build_tree(nodes_list)

def test_build_tree_validation_fails(sample_spec_data, sample_child_spec_data):
    # Simulate loading nodes where the placeholder and the actual node differ
    root_spec_url = 'http://example.com/root.oid'
    child_spec_url = sample_spec_data['children'][0]['node_spec']

    root = OIDNode.from_spec(root_spec_url, sample_spec_data)

    # Modify the child spec data so it *won't* match the placeholder
    child_spec_data_modified = sample_child_spec_data.copy()
    child_spec_data_modified['node']['name'] = 'different_name_in_spec'

    # Create the node from the modified spec
    child1_full_differs = OIDNode.from_spec(child_spec_url, child_spec_data_modified, parent=None)

    nodes_list = [root, child1_full_differs]

    # Expect build_tree to raise ValueError from validate_parent_child_equality
    with pytest.raises(ValueError, match="Parent and node spec. differ in attribute 'name'"):
        build_tree(nodes_list)
