# firebird-uuid
Repository to manage names in Firebird OID namespace.

# Basics

## UUIDs

UUIDs [rfc4122](http://tools.ietf.org/html/rfc4122) are excellent Uniform Resource Names (URN). The standard defines five UUID types, where types 3 and 5 can be used to create a hierarchy of (very probably) unique URNs.

Roughly speaking, a type 3 or type 5 UUID is generated by hashing together a namespace identifier with a name. Type 3 UUIDs use MD5 and type 5 UUIDs use SHA1. Only 128-bits are available and 5 bits are used to specify the type, so all of the hash bits don't make it into the UUID. (Also MD5 is considered cryptographically broken, and SHA1 is on its last legs, so don't use this to verify data that needs to be "very secure"). That said, it gives you a way of creating a repeatable/verifiable "hash" function mapping a possibly hierarchical name onto a probabilistically unique 128-bit value, potentially acting like a hierarchical hash or MAC.

The generated type 3 or type 5 UUID holds a (partial) hash of the namespace id (which itself is an UUID) and name-within-namespace (key). It no more holds the namespace UUID than does a message MAC hold the contents of the message it is encoded from. The name is an "arbitrary" (octet) string from the perspective of the uuid algorithm. Its meaning however depends on your application. It could be a filename within a logical directory, object-id within an object-store, etc.

While this works well for a moderately large number of namespaces and keys, it eventually runs out of steam if you are aiming for a very large numbers of keys that are unique with very high probability. The Wikipedia entry for the [Birthday Problem](http://en.wikipedia.org/wiki/Birthday_problem#Probability_table) (aka Birthday Paradox) includes a table that gives the probabilities of at least one collision for various numbers of keys and table sizes. For 128-bits, hashing 26 billion keys this way has a probability of collision of `p=10^-18` (negligible), but 26 trillion keys, increases the probability of at least one collision to `p=10^-12` (one in a trillion), and hashing `26*10^15 keys`, increases the probability of at least one collision to `p=10^-6` (one in a million). Adjusting for 5 bits that encode the UUID type, it will run out somewhat faster, so a trillion keys have roughly a 1-in-a-trillion chance of having a single collision.

The UUID RFC pre-defines four namespaces:

    NameSpace_DNS: {6ba7b810-9dad-11d1-80b4-00c04fd430c8}
    NameSpace_URL: {6ba7b811-9dad-11d1-80b4-00c04fd430c8}
    NameSpace_OID: {6ba7b812-9dad-11d1-80b4-00c04fd430c8}
    NameSpace_X500:{6ba7b814-9dad-11d1-80b4-00c04fd430c8}

**This repository is used to manage names within ISO OID namespace.**

## ISO OID

An OID is a globally unique [ISO](http://www.iso.org/iso/en/ISOOnline.frontpage) identifier.
There are multiple ways that this identifier may be represented, and Firebird Foundation has
chosen to represent OID registered here using a form that consists only of numbers and dots
(e.g., "1.3.6.1.4.1.53446.1"). OIDs are paths in a tree structure, with the left-most number
representing the root and the right-most number representing a leaf.

Each OID is created by a Registration Authority. Each of these authorities may, in turn,
delegate assignment of new OIDs under it to other registration authorities that work under its
auspices, and so on down the line. Eventually, one of these authorities assigns a unique (to it)
number that corresponds to a leaf node on the tree. The leaf may represent a registration authority
(in which case the OID identifies the authority), or an instance of an object. A registration
authority owns the namespace consisting of its sub-tree.

The [Firebird Foundation Incorporated](https://firebirdsql.org/en/firebird-foundation) obtained
a [PEN](https://www.iana.org/assignments/enterprise-numbers/enterprise-numbers) (Private Enterprise
Number) from [IANA](https://www.iana.org), and thus become a registered owner of OID _1.3.6.1.4.1.53446_
(iso.org.dod.internet.private.enterprise.firebird-foundation-inc). This repository is used to manage
sub-tree of OIDs under this namespace, that are used by Firebird Foundation and
the [Firebird Project](https://www.firebirdsql.org).

# How it works

The OID hierarchy is controlled by a set of YAML files, each file describing one level
in the tree hierarchy (that is, the root node of the child tree and all assigned nodes
for children). The [root.oid](https://github.com/FirebirdSQL/firebird-uuid/blob/master/root.oid) file
in this repository describes the OID of highest level (assigned by IANA).

Each file has the following format:

```yaml
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
```

**All fields must be present, and if not specified otherwise, they must have a value.**

Fields `name`,`description`,`contact`,`email` and `site` in `children` record SHOULD have
the same values like fields of the same name in `node` record of the YAML file describing
the child node. If they differ in content, the values present in `children` record (parent)
take precedence over values present in `node` record (child).

# Using OIDs to generate UUIDs

Here are some examples that generate the UUID for OID assigned to the Firebird Foundation.

bash (using `uuid` utility):
```bash
>uuid -v5 ns:OID 1.3.6.1.4.1.53446
6f8c9fea-acfa-5b49-af8a-11aca8d0c4a0

```

python:
```python
>>> import uuid
>>> uuid.uuid5(uuid.NAMESPACE_OID, "1.3.6.1.4.1.53446")
UUID('6f8c9fea-acfa-5b49-af8a-11aca8d0c4a0')
```

# Python package for work with Firebird OID namespace

The Firebird Project provides [firebird-uuid](https://pypi.org/project/firebird-uuid/) Python package
for work with OID hierarchy definitions in format defined above.
