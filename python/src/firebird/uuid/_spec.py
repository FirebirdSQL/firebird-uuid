#coding:utf-8
#
# PROGRAM/MODULE: firebird-uuid
# FILE:           firebird/uuid/spec.py
# DESCRIPTION:    Firebird OID registry specification
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

"""Firebird OID registry specification.

The OID hierarchy is controlled by a set of YAML files, each file describing one level in
the tree hierarchy (that is, the root node of the child tree and all assigned nodes for
children). The `root.oid` file describes the OID of highest level (assigned by IANA).

Each file has the following format::

  # Description of root node for this sub-tree
  node:
      oid:           # Full OID, for example 1.3.6.1.4.1.53446
      name:          # Node name
      description:   # Node description
      contact:       # Name of the contact person
      email:         # E-mail of the contact person
      site:          # URL to website of node owner
      parent-spec:   # URL of parent YAML file, empty for top level (root) node
      type:          # enumeration: "root", "node", "leaf"

  # List of children nodes in order of numbers assigned to them
  # could be omitted for leaf node (see node.type)
  children:
      - number:      # Number assigned to this child node, oid = node.oid + '.' + number
        name:        # Node name
        description: # Node description, could be empty
        contact:     # Name of the contact person
        email:       # E-mail of the contact person
        site:        # URL to website of node owner
        node-spec:   # one of: keywords "leaf" or "private" or URL to YAML file describing this child node
"""

from __future__ import annotations
from typing import Tuple
import os
import re
from urllib.request import url2pathname
import requests
import yaml


class LocalFileAdapter(requests.adapters.BaseAdapter):
    """Protocol Adapter to allow Requests to GET file:// URLs
    """
    @staticmethod
    def _chkpath(method, path):
        """Return an HTTP status for the given filesystem path."""
        if method.lower() in ('put', 'delete'):
            return 501, "Not Implemented"  # TODO
        elif method.lower() not in ('get', 'head'):
            return 405, "Method Not Allowed"
        elif os.path.isdir(path):
            return 400, "Path Not A File"
        elif not os.path.isfile(path):
            return 404, "File Not Found"
        elif not os.access(path, os.R_OK):
            return 403, "Access Denied"
        else:
            return 200, "OK"

    def send(self, req, **kwargs):  # pylint: disable=unused-argument
        """Return the file specified by the given request
        """
        path = os.path.normcase(os.path.normpath(url2pathname(req.path_url)))
        response = requests.Response()

        response.status_code, response.reason = self._chkpath(req.method, path)
        if response.status_code == 200 and req.method.lower() != 'head':
            try:
                response.raw = open(path, 'rb')
            except (OSError, IOError) as err:
                response.status_code = 500
                response.reason = str(err)

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        response.request = req
        response.connection = self

        return response

    def close(self):
        pass

#: URL for ROOT specification
ROOT_SPEC = 'https://raw.githubusercontent.com/FirebirdSQL/firebird-uuid/master/root.oid'

ITEM_NODE = 'node'
ITEM_OID = 'oid'
ITEM_CHILDREN = 'children'
ITEM_NAME = 'name'
ITEM_DESCRIPTION = 'description'
ITEM_CONTACT = 'contact'
ITEM_EMAIL = 'email'
ITEM_SITE = 'site'
ITEM_PARENT_SPEC = 'parent-spec'
ITEM_TYPE = 'type'
ITEM_NODE_SPEC = 'node-spec'
ITEM_NUMBER = 'number'

#KEY_ITEMS = (ITEM_OID, ITEM_NAME, ITEM_DESCRIPTION, ITEM_CONTACT, ITEM_EMAIL, ITEM_SITE,
             #ITEM_TYPE, ITEM_NODE_SPEC)

SPEC_ITEMS = set((ITEM_NODE, ITEM_CHILDREN))
NODE_ITEMS = set((ITEM_OID, ITEM_NAME, ITEM_DESCRIPTION, ITEM_CONTACT, ITEM_EMAIL,
                  ITEM_SITE, ITEM_PARENT_SPEC, ITEM_TYPE))
CHILD_ITEMS = set((ITEM_NUMBER, ITEM_NAME, ITEM_DESCRIPTION, ITEM_CONTACT, ITEM_EMAIL,
                   ITEM_SITE, ITEM_NODE_SPEC))

RE_EMAIL = re.compile(r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])""")
RE_OID = re.compile(r"^(\d+\.)+\d+$")
RE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")
TYPE_VALUES = ('root', 'node', 'leaf')
NODE_KEYWORDS = ('private', 'leaf')

def _check_string(data: Dict, item: str) -> None:
    value = data[item]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"String value required for '{item}', found '{value}'")

def _check_number(data: Dict, item: str) -> None:
    value = data[item]
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Non-negative number value required for '{item}', found '{value}'")


def _check_email(data: Dict, item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if RE_EMAIL.fullmatch(value) is None:
        raise ValueError(f"E-mail value required for '{item}', found '{value}'")

def _check_oid(data: Dict, item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if RE_OID.fullmatch(value) is None:
        raise ValueError(f"OID value required for '{item}'")

def _check_name(data: Dict, item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if RE_NAME.fullmatch(value) is None or value.lower() != value:
        raise ValueError(f"Single lowercase word required for '{item}', found '{value}'")

def _check_parent_spec(data: Dict, item: str) -> None:
    if data['type'] != 'root' and (not isinstance(item, str) or not item.strip()):
        raise ValueError(f"String value required for '{item}'")

def _check_node_spec(data: Dict, item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if RE_NAME.fullmatch(value) is not None and value not in NODE_KEYWORDS:
        raise ValueError(f"Either URL or keyword required for '{item}'")

def _check_type(data: Dict, item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if value not in TYPE_VALUES:
        raise ValueError(f"Invalid node type '{value}'")

_VALIDATE_MAP = {ITEM_OID: _check_oid,
                 ITEM_NAME: _check_name,
                 ITEM_DESCRIPTION: _check_string,
                 ITEM_CONTACT: _check_string,
                 ITEM_EMAIL: _check_email,
                 ITEM_SITE: _check_string,
                 ITEM_PARENT_SPEC: _check_parent_spec,
                 ITEM_TYPE: _check_type,
                 ITEM_NUMBER: _check_number,
                 }

def validate_dict(expected: Set, data: Dict) -> None:
    """Validates dictionary.

    Arguments:
      expected: Set of expected keys.
      data:     Validated dictionary.

    Raises:
      ValueError: When any keys are missing or additional keys are present, or when
        values do not conform to specification.
    """
    given = set(data.keys())
    if expected != given:
        missing = expected.difference(given)
        additional = given.difference(expected)
        if missing and not additional:
            raise ValueError(f'Missing keys: {missing.keys()}')
        elif additional and not missing:
            raise ValueError(f'Found unexpected keys: {additional.keys()}')
        else:
            raise ValueError(f'Missing and unexpected keys found')
    # Validate items
    for item, checker in _VALIDATE_MAP.items():
        if item in data:
            checker(data, item)

def validate_spec(data: Dict) -> Dict:
    """Validates OID specification dictionary.

    Arguments:
      data:     Dictiorary with parsed OID YAML specification.

    Raises:
      ValueError: When any keys are missing or additional keys are present, or when
        values do not conform to specification.
    """
    validate_dict(SPEC_ITEMS, data)
    validate_dict(NODE_ITEMS, data['node'])
    for child in data['children']:
        validate_dict(CHILD_ITEMS, child)

def pythonize(data: Dict) -> Dict:
    """Returns dictionary with normalized key names for use as keyword parameters to
    `.Node` __init__ method.

    Arguments:
      data: Dictionary for normalization.
    """
    result = {key.replace('-', '_'): value for key, value in data.items()}
    if 'type' in result:
        result['node_type'] = result['type']
        del result['type']
    return result

def pythonize_spec(data: Dict) -> Dict:
    """Returns dictionary of parsed OID specification with normalized key names for use as
    keyword parameters to `.Node` __init__ method.

    Arguments:
      data: Dictionary for normalization.
    """
    data['node'] = pythonize(data['node'])
    for i, child in enumerate(data['children']):
        data['children'][i] = pythonize(child)

def get_specification(url: str) -> str:
    """Returns YAML text of OID specification from URL.

    Arguments:
        url: URL of OID specification.

    Raises:
      requests.HTTPError: If one occurred.
    """
    requests_session = requests.session()
    requests_session.mount('file://', LocalFileAdapter())

    spec_req: requests.Response = requests_session.get(url, allow_redirects=True)
    if not spec_req.ok:
        spec_req.raise_for_status()
    return spec_req.text

#def parse_spec(spec: str) -> Dict:
    #"""Returns dictionary with parsed OID specification.

    #Dictionary keys are normalized to Python identifiers (dash replaced with undersore),
    #and `type` is renamed to `node_type`.

    #Arguments:
        #spec: OID specification in YAML format.

    #Raises:
      #YAMLError: If specification is not valid YAML.
      #ValueError: If specification does not conform to specification format.
    #"""
    #data = yaml.safe_load(spec)
    #validate_spec(data)
    #pythonize_spec(data)
    #return data

def get_specifications(root: str=ROOT_SPEC) -> Tuple[Dict[str, str], Dict[str, Exception]]:
    """Function traverses the tree of OID YAML specifications, and returns accessible YAML
    specifications and errors encountered during tree traversal.

    This function does not perform any validation of loaded specifications beoynd checks
    and transformations needed to parse the YAML to get links to child specifications.

    Returns tuple with two dictionaries:
      - First dictionary contains `url: spec_yaml` with all YAML specifications
        that were successfuly fetched.
      - Second dictionary contains `url: Exception` with all errors encountered
        during tree traversal.

    Arguments:
      root: URL to root specification where tree traversal should begin.
    """
    def load_tree(node: str) -> None:
        try:
            spec = get_specification(node)
            spec_map[node] = spec
            data = yaml.safe_load(spec)
        except Exception as exc:
            err_map[node] = exc
            return
        if ITEM_CHILDREN not in data:
            err_map[node] = "Missing children specification"
            return
        for i, child in enumerate(data[ITEM_CHILDREN]):
            if ITEM_NODE_SPEC not in child:
                err_map[node] = f"Children {i} does not contain node-spec"
                return
            else:
                if child[ITEM_NODE_SPEC].lower() not in ('leaf', 'private'):
                    load_tree(child[ITEM_NODE_SPEC])


    spec_map = {}
    err_map = {}
    load_tree(ROOT_SPEC)
    return (spec_map, err_map)

def parse_specifications(specifications: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, Exception]]:
    """Function that parses OID YAML specifications.

    Returns tuple with two dictionaries:
      - First dictionary contains `url: spec_dict`, where dictionaries contain data
        from successfuly parsed and validated OID YAML specifications.
      - Second dictionary contains `url: Exception` with errors encountered during parsing
        and validation.

    Arguments:
      specifications: Dictionary with YAML specifications returned by
        `.get_all_specifications()` function.
    """
    data_map = {}
    err_map = {}
    for url, spec in specifications.items():
        try:
            data: Dict = yaml.safe_load(spec)
            validate_spec(data)
            pythonize_spec(data)
            data_map[url] = data
        except Exception as exc:
            err_map[url] = exc
    return (data_map, err_map)
