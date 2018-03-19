.. _developerguide:

Developer Guide
===============

Cluster Genesis development is overseen by a team of IBM engineers.

Git Repository Model
--------------------

Development and test is orchestrated within the  *master* branch. Stable
*release-x.y* branches are created off *master* and supported with bug fixes.
`Semantic Versioning <http://semver.org/>`_ is used for release tags and branch
names.

Coding Style
------------

Code should be implemented in accordance with
`PEP 8 -- Style Guide for Python Code <https://www.python.org/dev/peps/pep-0008/>`_.

It is requested that modules contain appropriate *__future__* imports to simplify
future migration to Python3.

Commit Message Rules
--------------------

- Subject line
    - First line of commit message provides a short description of change
    - Must not exceed 50 characters
    - First word after tag must be capitalized
    - Must begin with one of the follwoing subject tags::

        feat:      New feature
        fix:       Bug fix
        docs:      Documentation change
        style:     Formatting change
        refactor:  Code change without new feature
        test:      Tests change
        chore:     Miscellaneous no code change
        Revert     Revert previous commit

- Body
    - Single blank line seperates subject line and message body
    - Contains detailed description of change
    - Lines must not exceed 72 characters
    - Periods must be followed by single space

Your Commit message can be validated within the tox environment
(see below for setup of the tox environment)::

    cluster-genesis$ tox -e commit-message-validate

Unit Tests and Linters
----------------------

Tox
~~~

Tox is used to manage python virtual environments used to run unit tests and
various linters.

To run tox first install python dependencies::

    cluster-genesis$ ./scripts/install.sh

Install tox::

    cluster-genesis$ pip install tox

To run all tox test environments::

    cluster-genesis$ tox

List test environments::

    cluster-genesis$ tox -l
    py27
    bashate
    flake8
    ansible-lint
    commit-message-validate
    verify-copyright
    file-format

Run only 'flake8' test environment::

    cluster-genesis$ tox -e flake8

Unit Test
~~~~~~~~~

Unit test scripts reside in the `cluster-genesis/tests/unit/` directory.

Unit tests can be run through tox::

    cluster-genesis$ tox -e py27

Or called directly through python (be mindful of your python environment!)::

    cluster-genesis$ python -m unittest discover

Linters
~~~~~~~

Linters are required to run cleanly before a commit is submitted. The following
linters are used:

- Bash: bashate
- Python: pycodestyle/flake8/pylint
- Ansible: ansible-lint

Linters can be run through tox::

    cluster-genesis$ tox -e bashate
    cluster-genesis$ tox -e flake8
    cluster-genesis$ tox -e ansible-lint

Or called directly (again, be mindful of your python environment!)

*Pylint* and *pycodestyle* validation is not automatically launched when
issuing the *tox* command. They need to be called out explicitly::

    cluster-genesis$ tox -e pycodestyle
    cluster-genesis$ tox -e pylint
    cluster-genesis$ tox -e pylint-errors

File Format Validation
~~~~~~~~~~~~~~~~~~~~~~

Ensure that each text file is in *unix* mode where lines are terminated by a
linefeed::

    cluster-genesis$ tox -e file-format

Copyright Date Validation
~~~~~~~~~~~~~~~~~~~~~~~~~

If any changed files include a copyright header the year must be current. This
rule is enforced within a tox environment::

    cluster-genesis$ tox -e verify-copyright
