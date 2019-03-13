.. _developerguide:

Developer Guide
===============

POWER-Up development is overseen by a team of IBM engineers.

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

    power-up$ tox -e commit-message-validate

Unit Tests and Linters
----------------------

Tox
~~~

Tox is used to manage python virtual environments used to run unit tests and
various linters.

To run tox first install python dependencies::

    power-up$ ./scripts/install.sh

Install tox::

    power-up$ pip install tox

To run all tox test environments::

    power-up$ tox

List test environments::

    power-up$ tox -l
    py36
    bashate
    flake8
    ansible-lint
    commit-message-validate
    verify-copyright
    file-format

Run only 'flake8' test environment::

    power-up$ tox -e flake8

Unit Test
~~~~~~~~~

Unit test scripts reside in the `power-up/tests/unit/` directory.

Unit tests can be run through tox::

    power-up$ tox -e py36

Or called directly through python (be mindful of your python environment!)::

    power-up$ python -m unittest discover

Linters
~~~~~~~

Linters are required to run cleanly before a commit is submitted. The following
linters are used:

- Bash: bashate
- Python: pycodestyle/flake8/pylint
- Ansible: ansible-lint

Linters can be run through tox::

    power-up$ tox -e bashate
    power-up$ tox -e flake8
    power-up$ tox -e ansible-lint

Or called directly (again, be mindful of your python environment!)

*Pylint* and *pycodestyle* validation is not automatically launched when
issuing the *tox* command. They need to be called out explicitly::

    power-up$ tox -e pycodestyle
    power-up$ tox -e pylint
    power-up$ tox -e pylint-errors

File Format Validation
~~~~~~~~~~~~~~~~~~~~~~

Ensure that each text file is in *unix* mode where lines are terminated by a
linefeed::

    power-up$ tox -e file-format

Copyright Date Validation
~~~~~~~~~~~~~~~~~~~~~~~~~

If any changed files include a copyright header the year must be current. This
rule is enforced within a tox environment::

    power-up$ tox -e verify-copyright
