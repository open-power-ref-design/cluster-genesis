"""Library for curses menus.

    Attributes:
        KEY_ESC (int): Unicode code point of ``ESC`` key.
"""
# Copyright 2018 IBM Corp.
#
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import curses

KEY_ESC = 27


class Menu(object):
    """Curses menu class.

    Curses menu consisting of a title, subtitle (optional), and a list of
    selectable items. Items can be a submenu (:obj:`MenuItemSubmenu`), function
    call (:obj:`MenuItemFunction`), or non-selectable text (:obj:`MenuItem`).

    Args:
        log (:obj:`Logger`): Log file object.
        stdscr (:obj:`WindowObject`): `Python curses module`_ window object
            representing the whole screen.
        title (str): Title displayed at top of menu.
        subtitle (str, optional): Subtitle displayed underneath title.
        items (list if :obj:`MenuItem`): Selectable menu items.

    Attributes:
        log (:obj:`Logger`): Log file object.
        stdscr (:obj:`WindowObject`): `Python curses module`_ window object
            representing the whole screen.
        title (str): Title displayed at top of menu.
        subtitle (str): Subtitle displayed underneath title.
        items (list if :obj:`MenuItem`): Selectable menu items.
        num_selects (list of int): List of integers representing the Unicode
            code points of the characters ``0``, ``1``, and so on up to the
            total number of menu selections that can fit on a single page
            (currently limited to 10).
        enter_selects (list of int): List of integers representing the Unicode
            points of ``return`` characters used to detect a menu item
            selection.
        cursor_pos (int): Current menu item cursor position.

    .. _`Python curses module`:
       https://docs.python.org/2/library/curses.html
    .. _`Curses Programming with Python`:
        https://docs.python.org/2/howto/curses.html

    """

    def __init__(self, log, stdscr, title, subtitle=None, items=[]):
        self.log = log
        self.stdscr = stdscr
        self.title = title
        self.subtitle = subtitle
        self.items = items
        self.num_selects = (
            [ord(str(n)) for n in range(len(self.items)) if n < 10])
        self.enter_selects = [curses.KEY_ENTER, ord('\n')]
        curses.curs_set(0)
        self.cursor_pos = 0

    def show_menu(self):
        """Print menu to screen.

        Note:
            There are no arguments or returns. All of the information needed to
            build and display the menu is already stored within attributes.
        """
        while True:
            self.stdscr.clear()
            curses.doupdate()

            self.stdscr.addstr(1, 1, self.title)
            self.stdscr.addstr(3, 3, self.subtitle)

            for index, item in enumerate(self.items):
                if index == self.cursor_pos:
                    highlight = curses.A_REVERSE
                else:
                    highlight = curses.A_NORMAL

                self.stdscr.addstr(
                    index + 4, 2,
                    "%2d) %s" % (index, item.name),
                    highlight)

            key = self.stdscr.getch()

            if key in [curses.KEY_DOWN, ord('j'), curses.KEY_NPAGE]:
                if self.cursor_pos + 1 == len(self.items):
                    self.cursor_pos = 0
                else:
                    self.cursor_pos += 1

            elif key in [curses.KEY_UP, ord('k'), curses.KEY_PPAGE]:
                if self.cursor_pos == 0:
                    self.cursor_pos = len(self.items) - 1
                else:
                    self.cursor_pos += -1

            elif key in [curses.KEY_HOME]:
                self.cursor_pos = 0

            elif key in [curses.KEY_END]:
                self.cursor_pos = len(self.items) - 1

            elif key in [KEY_ESC]:
                break

            elif key in self.enter_selects + self.num_selects:

                if key in self.enter_selects:
                    selection = self.items[self.cursor_pos]
                elif key in self.num_selects:
                    selection = self.items[int(chr(key))]

                if selection.item_type == 'simple':
                    if selection.exit:
                        break
                elif selection.item_type == 'submenu':
                    selection.menu.show_menu()
                    self.refresh_titles()
                elif selection.item_type == 'function':
                    getattr(selection, selection.function)(selection.args)
                    if selection.exit:
                        break

    def refresh_titles(self):
        """Refresh menu titles.

        Note:
            This method provides a way to update objects upon a menu display
            refresh.
        """
        for item in self.items:
            item.refresh_title()


class MenuItem(object):
    """Curses menu item class.

    Menus consist of a list of selectable `MenuItem` objects. Items can be a
    submenu (:obj:`MenuItemSubmenu`), function call (:obj:`MenuItemFunction`),
    or non-selectable text (:obj:`MenuItem`).

    Args:
        name (str): Item name string to be displayed as menu selection.
        item_type (str, optional): Type of menu item. Defined types are
            ``simple`` (not selectable), ``submenu`` (nested menu), or
            ``function`` (function call).
        exit (bool, optional): When ``True`` exit menu after selection.
            Defaults to ``False``.

    Attributes:
        name (str): Item name string to be displayed as menu selection.
        item_type (str): Type of menu item.
        exit (bool): When ``True`` exit menu after selection.
    """

    def __init__(self, name, item_type='simple', exit=False):
        self.name = name
        self.item_type = item_type
        self.exit = exit

    def refresh_title(self):
        """Refresh title.

        Note:
            This method provides a way to update objects upon a menu display
            refresh.
        """
        pass


class MenuItemSubmenu(MenuItem):
    """Curses menu item 'submenu' type class.

    Menu item to select a nested menu.

    Args:
        name (str): Item name string to be displayed as menu selection.

    Attributes:
        name (str): Item name string to be displayed as menu selection.
        menu (:obj:`Menu`): Submenu object.
        item_type (str): ``submenu``.
        exit (bool): ``False``.
    """

    def __init__(self, name, menu, item_type='submenu'):
        self.menu = menu
        super(MenuItemSubmenu, self).__init__(name, item_type)


class MenuItemFunction(MenuItem):
    """Curses menu item 'function' type class.

    Menu item to select a function call (with provided arguments). It is
    assumed that the function defined and accessible.

    Args:
        name (str): Item name string to be displayed as menu selection.
        function (str): Name of function.
        args (*, optional): Arguments to be passed to function. This is passed
            directly and thus can be any type supported by the particular
            function.

    Attributes:
        name (str): Item name string to be displayed as menu selection.
        function (str): Name of function.
        args (*): Arguments to be passed to function.
        item_type (str): ``function``.
        exit (bool): ``False``.
    """

    def __init__(
            self, name, function, args=None, item_type='function', exit=False):
        self.function = function
        self.args = args
        super(MenuItemFunction, self).__init__(name, item_type, exit)


class MenuItemExit(MenuItem):
    """Curses menu item 'exit' type class.

    Menu item to exit current menu. If the current menu is nested it will exit
    into its parent menu. If the current menu is not nested it will exit the
    curses menu entirely.

    Args:
        name (str): Item name string to be displayed as menu selection.

    Attributes:
        name (str): Item name string to be displayed as menu selection.
        item_type (str): ``simple``.
        exit (bool): ``True``.
    """

    def __init__(self, name):
        super(MenuItemExit, self).__init__(name, exit=True)
