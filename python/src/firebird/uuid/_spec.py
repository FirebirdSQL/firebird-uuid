# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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
# Copyright (c) 2022 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Firebird OID registry specification handling.

This module provides tools for fetching, parsing, validating, and processing
OID (Object Identifier) hierarchy specifications defined in YAML files. These
specifications describe nodes within the Firebird OID tree, linking parent
nodes to children.

The OID hierarchy is controlled by a set of YAML files, each describing one
level (a parent node and its direct children). The `root.oid` file, typically
referenced by `ROOT_SPEC`, describes the top-level OID assigned by IANA.

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

import os
import re
from collections.abc import Mapping
from typing import Any, TypeAlias
from urllib.request import url2pathname

import requests
import yaml

KeySet: TypeAlias = set[str]

class LocalFileAdapter(requests.adapters.BaseAdapter):
    """A requests Session adapter to allow fetching `file://` URLs.

    Standard `requests` does not handle local file paths directly. This adapter
    enables `requests.Session` objects to GET content from `file://` URIs
    by mounting it to the 'file://' prefix.
    """
    @staticmethod
    def _chkpath(method: str, path: str) -> tuple[int, str]:
        """Checks filesystem path validity and access for common HTTP methods.

        Arguments:
            method: The HTTP method requested (e.g., 'GET', 'HEAD').
            path: The local filesystem path derived from the URL.

        Returns:
            A tuple containing an HTTP-like status code (int) and a
            reason phrase (str). Checks for method allowance, path type
            (file vs. directory), existence, and read permissions.
        """
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

    def send(self, req: requests.PreparedRequest, **kwargs) -> requests.Response:  # noqa: ARG002
        """Handles a prepared request for a `file://` URL.

        Normalizes the path, checks its validity using `_chkpath`, and if valid
        (status 200), attempts to open the file for reading. It constructs and
        returns a `requests.Response` object containing the file content (raw)
        or an appropriate error status.

        Arguments:
            req: The `requests.PreparedRequest` object.
            **kwargs: Additional keyword arguments (unused, part of adapter signature).

        Returns:
            A `requests.Response` object.
        """
        path = os.path.normcase(os.path.normpath(url2pathname(req.path_url)))
        response = requests.Response()

        response.status_code, response.reason = self._chkpath(req.method, path)
        if response.status_code == 200 and req.method.lower() != 'head': # noqa: PLR2004
            try:
                response.raw = open(path, 'rb')
            except OSError as err:
                response.status_code = 500
                response.reason = str(err)

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        response.request = req
        response.connection = self

        return response

    def close(self) -> None:
        """Closes the adapter.

        This is a no-op for the file adapter as there are no persistent
        connections to close.
        """

#: URL for ROOT specification
ROOT_SPEC: str = 'https://raw.githubusercontent.com/FirebirdSQL/firebird-uuid/master/root.oid'

ITEM_NODE: str = 'node'
ITEM_OID: str = 'oid'
ITEM_CHILDREN: str = 'children'
ITEM_NAME: str = 'name'
ITEM_DESCRIPTION: str = 'description'
ITEM_CONTACT: str = 'contact'
ITEM_EMAIL: str = 'email'
ITEM_SITE: str = 'site'
ITEM_PARENT_SPEC: str = 'parent-spec'
ITEM_TYPE: str = 'type'
ITEM_NODE_SPEC: str = 'node-spec'
ITEM_NUMBER: str = 'number'

SPEC_ITEMS: KeySet = {ITEM_NODE, ITEM_CHILDREN}
NODE_ITEMS: KeySet = {ITEM_OID, ITEM_NAME, ITEM_DESCRIPTION, ITEM_CONTACT, ITEM_EMAIL,
                      ITEM_SITE, ITEM_PARENT_SPEC, ITEM_TYPE}
CHILD_ITEMS: KeySet = {ITEM_NUMBER, ITEM_NAME, ITEM_DESCRIPTION, ITEM_CONTACT, ITEM_EMAIL,
                       ITEM_SITE, ITEM_NODE_SPEC}

RE_EMAIL: re.Pattern[str] = re.compile(r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])""")
RE_OID: re.Pattern[str] = re.compile(r"^(?:\d+|\d+(\.\d+)+)$")
RE_NAME: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-]+$")
RE_URL_OR_PATH: re.Pattern[str] = re.compile(r'^(?:(?:https?|file)://|/|(?:\./|\.\./))(?:[^\s"]*)', re.IGNORECASE)
TYPE_VALUES: set[str] = {'root', 'node', 'leaf'}
NODE_KEYWORDS: set[str] = {'private', 'leaf'}

def _check_string(data: dict, item: str) -> None:
    """Checks if the value for `item` in `data` is a non-empty string.

    Raises:
        ValueError: If the value is not a non-empty string.
    """
    value = data[item]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"String value required for '{item}', found '{value}'")

def _check_number(data: Mapping[str, Any], item: str) -> None:
    """Checks if the value for `item` in `data` is a non-negative integer.

    Raises:
        ValueError: If the value is not a non-negative integer.
    """
    value = data[item]
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Non-negative number value required for '{item}', found '{value}'")


def _check_email(data: Mapping[str, Any], item: str) -> None:
    """Checks if the value for `item` in `data` is a valid, non-empty email string.

    Raises:
        ValueError: If the value is not a string or does not match the email pattern.
    """
    _check_string(data, item)
    value = data[item]
    if RE_EMAIL.fullmatch(value) is None:
        raise ValueError(f"E-mail value required for '{item}', found '{value}'")

def _check_oid(data: Mapping[str, Any], item: str) -> None:
    """Checks if the value for `item` in `data` is a valid, non-empty OID string.

    Raises:
        ValueError: If the value is not a string or does not match the OID pattern.
    """
    _check_string(data, item)
    value = data[item]
    if RE_OID.fullmatch(value) is None:
        raise ValueError(f"OID value required for '{item}'")

def _check_name(data: Mapping[str, Any], item: str) -> None:
    """Checks if the value for `item` in `data` is a valid, non-empty name.

    Raises:
        ValueError: If the value is not a string or does not match the name pattern.
    """
    _check_string(data, item)
    value = data[item]
    if RE_NAME.fullmatch(value) is None or value.lower() != value:
        raise ValueError(f"Single lowercase word required for '{item}', found '{value}'")

def _check_parent_spec(data: Mapping[str, Any], item: str) -> None:
    if data['type'] != 'root' and (not isinstance(item, str) or not item.strip()):
        raise ValueError(f"String value required for '{item}'")

def _check_node_spec(data: Mapping[str, Any], item: str) -> None:
    _check_string(data, item)
    value = data[item]
    if value in NODE_KEYWORDS:
        return
    if RE_URL_OR_PATH.fullmatch(value):
        # Optional: Add more specific checks using urlparse if needed
        # from urllib.parse import urlparse
        # try:
        #     parsed = urlparse(value)
        #     if not parsed.scheme or not (parsed.netloc or parsed.path):
        #          raise ValueError("Parsed URL seems invalid")
        # except ValueError:
        #      raise ValueError(f"Value for '{item}' ('{value}') is not a valid keyword or parsable URL/path.")
        return
    raise ValueError(f"Either URL or keyword required for '{item}'")

def _check_type(data: Mapping[str, Any], item: str) -> None:
    """Checks if the value for `item` in `data` is a valid node type.

    Raises:
        ValueError: If the value is not a string or is not from alloved node type names.
    """
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

def validate_dict(expected: KeySet, data: Mapping[str, Any]) -> None:
    """Validates a dictionary's keys and the format/type of its values.

    Checks if the dictionary `data` contains exactly the keys specified in
    `expected`. It then uses specific checker functions (defined in
    `_VALIDATE_MAP`) to validate the type and format of values for known keys.

    Arguments:
        expected: A set of expected key names (strings).
        data: The dictionary to validate.

    Raises:
        ValueError: If keys are missing, unexpected keys are present, or if
            any value fails its specific validation check.
    """
    given = set(data.keys())
    if expected != given:
        missing = expected.difference(given)
        additional = given.difference(expected)
        if missing and not additional:
            raise ValueError(f'Missing keys: {", ".join(missing)}')
        elif additional and not missing:
            raise ValueError(f'Found unexpected keys: {", ".join(additional)}')
        else:
            raise ValueError('Missing and unexpected keys found')
    # Validate items
    for item, checker in _VALIDATE_MAP.items():
        if item in data:
            checker(data, item)

def validate_spec(data: Mapping[str, Any]) -> None:
    """Validates the structure and content of a parsed OID specification dictionary.

    Ensures the top-level structure is correct (`node`, `children`) and then uses
    `validate_dict` to check the contents of the 'node' dictionary and each
    dictionary within the 'children' list against their respective required
    formats and value constraints.

    Arguments:
        data: Dictionary parsed from an OID YAML specification file.

    Raises:
        ValueError: If the structure is invalid, keys are missing/unexpected,
            or values do not conform to the specification format rules.
    """
    validate_dict(SPEC_ITEMS, data)
    validate_dict(NODE_ITEMS, data['node'])
    for child in data['children']:
        validate_dict(CHILD_ITEMS, child)

def pythonize(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalizes dictionary keys for use as Python keyword arguments.

    Converts keys with hyphens (e.g., 'parent-spec') to use underscores
    (e.g., 'parent_spec'). Also renames the 'type' key to 'node_type'.
    Typically used on 'node' or 'children' item dictionaries parsed from YAML.

    Arguments:
        data: The input dictionary (e.g., a node or child definition).

    Returns:
        A new dictionary with normalized keys.
    """
    result = {key.replace('-', '_'): value for key, value in data.items()}
    if 'type' in result:
        result['node_type'] = result['type']
        del result['type']
    return result

def pythonize_spec(data: Mapping[str, Any]) -> dict[str, any]:
    """Applies key normalization (`pythonize`) to an entire OID specification dictionary.

    Processes the 'node' dictionary and all dictionaries within the 'children'
    list, preparing the whole structure for easier use within Python code,
    such as instantiating `OIDNode` objects.

    Args:
        data: The complete, parsed OID specification dictionary.

    Returns:
        A new dictionary representing the specification with normalized keys.
    """
    result = {}
    result['node'] = pythonize(data['node'])
    result['children'] = data.get('children', [])
    for i, child in enumerate(result['children']):
        result['children'][i] = pythonize(child)
    return result

def get_specification(url: str) -> str:
    """Fetches the text content of an OID specification from a URL.

    Supports both HTTP(S) and local `file://` URLs via a configured
    `requests.Session`.

    Arguments:
        url: The URL (http, https, or file) of the OID specification YAML file.

    Returns:
        The YAML text content of the specification.

    Raises:
        requests.exceptions.RequestException: If a network or file access error occurs.
        requests.exceptions.HTTPError: If an HTTP error response (e.g., 404) is received.
    """
    requests_session = requests.session()
    requests_session.mount('file://', LocalFileAdapter())

    spec_req: requests.Response = requests_session.get(url, allow_redirects=True)
    if not spec_req.ok:
        spec_req.raise_for_status()
    return spec_req.text

def get_specifications(root: str=ROOT_SPEC) -> tuple[dict[str, str], dict[str, Exception]]:
    """Recursively fetches all OID YAML specifications starting from a root URL.

    Traverses the tree of specifications by following 'node-spec' URLs found in
    child definitions. It collects the raw YAML text of successfully fetched
    specifications and records any exceptions encountered during fetching or
    initial YAML parsing (needed to find child URLs).

    This function performs only minimal validation necessary to navigate the tree.

    Arguments:
        root: The URL of the root specification to start traversal from.
              Defaults to `ROOT_SPEC`.

    Returns:
        A tuple containing two dictionaries:

        1.  `spec_map`: `dict[str, str]` mapping URL to successfully fetched
            YAML content (string).
        2.  `err_map`: `dict[str, Exception]` mapping URL to the Exception
            encountered while trying to fetch or minimally parse that spec.
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
            err_map[node] = Exception("Missing children specification")
            return
        for i, child in enumerate(data[ITEM_CHILDREN]):
            if ITEM_NODE_SPEC not in child:
                err_map[node] = Exception(f"Children {i} does not contain node-spec")
                return
            elif child[ITEM_NODE_SPEC].lower() not in ('leaf', 'private'):
                load_tree(child[ITEM_NODE_SPEC])

    spec_map: dict[str, str] = {}
    err_map: dict[str, Exception] = {}
    load_tree(root)
    return (spec_map, err_map)

def parse_specifications(specifications: dict[str, str]) -> tuple[dict[str, dict], dict[str, Exception]]:
    """Parses, validates, and normalizes multiple OID YAML specifications.

    Takes a dictionary of raw YAML specification strings (typically from
    `get_specifications`), parses each string into a Python dictionary,
    validates its structure and content against the defined format, and
    normalizes keys (e.g., 'node-spec' to 'node_spec') using `pythonize_spec`.

    Arguments:
        specifications: A dictionary mapping specification URLs (str) to their
                        raw YAML content (str).

    Returns:
        A tuple containing two dictionaries:

        1.  `data_map`: `dict[str, dict]` mapping URL to the successfully parsed,
            validated, and key-normalized specification data (dictionary).
        2.  `err_map`: `dict[str, Exception]` mapping URL to the Exception
            encountered during YAML parsing or validation for that spec.
    """
    data_map: dict[str, dict] = {}
    err_map: dict[str, Exception] = {}
    for url, spec in specifications.items():
        try:
            data: dict = yaml.safe_load(spec)
            validate_spec(data)
            data = pythonize_spec(data)
            data_map[url] = data
        except Exception as exc:
            err_map[url] = exc
    return (data_map, err_map)
