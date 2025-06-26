# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 The Open Planning Project
#
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import re

from trac.core import *
from trac.resource import ResourceNotFound
from trac.ticket import ITicketChangeListener, Ticket
from trac.util.html import html as tag


try:
    basestring
except NameError:
    basestring = str


class TracBacksPlugin(Component):

    implements(ITicketChangeListener)

    TRACBACK_MAGIC_NUMBER = "{{{\n#!html\n<div class=\"tracback\"></div>\n}}}\n"
    TRACBACK_PREFIX = "This ticket has been referenced in ticket #"

    TICKET_REGEX = r"""
        (?=                    # Don't return '#' character:
          (?!\{\{\{.*)	       # Exclude comment blocks
	  (?<=^\#)            # Look for a TracLink Ticket at the beginning of the string
          |(?<=[\s,.;:!]\#)    # or on a whitespace boundary or some punctuation
          |(?<=ticket:)        # or the "ticket:NNN" format
        )
        (?!.*\}\}\})
        (\d+)                  # Any length ticket number (return the digits)
        (?=
           (?=\b)              # Don't return word boundary at the end
          |$                   # Don't return end of string
        )
        """

    EXCERPT_CHARACTERS = 80
    WEED_BUFFER = 2

    # ITicketChangeListener methods

    def ticket_created(self, ticket):
        # Check for tracbacks on ticket creation.
        self.ticket_changed(ticket, ticket.values.get('description'),
                            ticket.values.get('reporter'), None)

    def ticket_changed(self, ticket, comment, author, old_values):

        pattern = re.compile(self.TICKET_REGEX, re.DOTALL|re.VERBOSE)

        if not isinstance(comment, basestring):
            return

        tickets_referenced = pattern.findall(comment)
        # convert from strings to ints and discard duplicates
        tickets_referenced = set(int(t) for t in tickets_referenced)
        # remove possible self-reference
        tickets_referenced.discard(ticket.id)

        # put trackbacks on the tickets that we found
        if not self.is_tracback(comment): # prevent infinite recursion
            for ticket_to_tracback in tickets_referenced:
                try:
                    t = Ticket(self.env, ticket_to_tracback)
                except ResourceNotFound: # referenced ticket does not exist
                    continue

                tracback = self.create_tracbacks(ticket, t, comment)
                t.save_changes(author, tracback)

    def ticket_deleted(self, ticket):
        pass

    def is_tracback(self, comment):
        return comment.startswith(self.TRACBACK_MAGIC_NUMBER)

    def create_tracbacks(self, ticket, ticket_to_tracback, comment):
        tracback = self.TRACBACK_MAGIC_NUMBER + self.TRACBACK_PREFIX + str(ticket.id) + ":"

        # find all occurrences of ticket_to_tracback. This is error prone.
        # we'll weed the errors out later.
        string_representation = "#" + str(ticket_to_tracback.id)

        excerpts = []

        index = -1
        while comment.find(string_representation, index + 1) > -1:
            # Get two characters in context so we can make sure this is really
            # a reference to a ticket, and not anything else.
            index = comment.find(string_representation, index + 1)

            if not self.is_weed(comment, index, index + len(string_representation)):
                start = index - self.EXCERPT_CHARACTERS
                end = index + len(string_representation) + self.EXCERPT_CHARACTERS

                left_ellipsis = "..."
                right_ellipsis = "..."

                # Make sure we don't go into the negative. Also, make the ellipsis'
                # disappear if we're not actually cutting up the comment.
                if start <= 0:
                    left_ellipsis = ""
                    start = 0

                if end >= len(comment):
                    right_ellipsis = ""

                excerpt = comment[start:end]
                excerpt = excerpt.replace("\n", "")

                # There's probably a better way to say this in python, but Tim doesn't know
                # how to do it. (He's tried """ but something's foobar'ed.)
                excerpts.append("\n> %s%s%s\n" % (left_ellipsis, excerpt, right_ellipsis))

        tracback += ''.join(excerpts)
        return tracback

    def is_weed(self, comment, start, end):
        start -= self.WEED_BUFFER
        end += self.WEED_BUFFER

        # Make sure we don't have a negative starting value.
        if start < 0:
            start = 0

        try:
            match = re.search(self.TICKET_REGEX, comment[start:end])
            return False
        except: # Not a match. This must be a weed.
            return True

