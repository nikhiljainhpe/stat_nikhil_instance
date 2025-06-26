# -*- coding: utf-8 -*-
#
#------------------------------------------------------------------------------
# Copyright (c) Jonathan Ashley <trac@ifton.co.uk> 2015-2017
#------------------------------------------------------------------------------
#
# This file is part of the Keep Interface Simple plugin for Trac.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import json
import re

from pkg_resources import resource_filename

from trac.core import *
from trac.config import ConfigurationError
from trac.ticket import ITicketManipulator
from trac.ticket import TicketSystem
from trac.ticket.model import Ticket
from trac.web.api import IRequestFilter, \
                         IRequestHandler, \
                         RequestDone
from trac.web.chrome import add_script, add_script_data, ITemplateProvider

#from genshi.filters.transform import Transformer

###############################################################################

class IConfigFunction(Interface):
    pass

# The following docstring appears on the Trac plugin administration page.

class BuiltInConfigFunctions(Component):
    """ BuiltInConfigFunctions

=== Built-in functions ===
        - `child_open()` - Returns True if the ticket has a child that is not closed. Returns False otherwise. (A "child" ticket is a ticket that has a field named 'parent' that contains the number of the current ticket, prefixed with a '#'. This is the scheme used by !ChildTicketsPlugin.)
        - `has_role(<group_name> [, <user_name>])` - Returns True if the named user is a member of the named permissions group. If no user name is supplied, defaults to the user viewing the page. Returns False otherwise.
        - `is_parent([<ticket>])` - Returns True if any ticket has a field named "parent" that contains "#<n>" where <n> is the number of the given ticket. If no ticket number is given, defaults to the current ticket. Returns False otherwise.
        - `status_of(<ticket>)` - Returns the current status of the named ticket, or None if the named ticket can't be found. The named ticket can be optionally prefixed with '#'.

=== Implementing user-defined functions ===
User-defined functions that can be called from the configuration file can be implemented by adding a Python file to the Trac plugins folder that implements the `IConfigFunction` interface. For example:
{{{
from trac.core import *
from kis2 import IConfigFunction

class MyConfigFunctions(Component):
    ''' Local functions for use by 'kisplugin' configuration files.
    '''
    implements(IConfigFunction)

    # Example: implement named string constants
    def safety(self, req, safety_enum):
        if safety_enum == 'YES':
            return 'Safety related'
        if safety_enum == 'OK':
            return 'Safety related - OK to close'
        if safety_enum == 'NO':
            return 'Not safety related'
}}}
This example would allow `safety('OK')` to return the string `Safety related - OK to close`.
The 'req' parameter is the HTTP request object; the remaining parameters are the parameters of the function call.
    """
    implements(IConfigFunction)

    def child_open(self, req):
        ''' Returns True if the ticket has a child that is not closed,
            otherwise False.
        '''
        if req.path_info.startswith('/newticket') or not req.args['id']:
            return False
        try:
            this_ticket_id = int(req.args['id'])
        except ValueError:
            return False

        for child, parent in self.env.db_query(
                'SELECT ticket, value FROM ticket_custom WHERE name="parent"'):
            parent_match = re.match('#(\d+)', parent or '')
            if parent_match:
                parent_id = int(parent_match.group(1))
                if parent_id == this_ticket_id:
                    child_ticket = Ticket(self.env, int(child))
                    if child_ticket['status'] != 'closed':
                        return True
        return False

    def has_role(self, req, *args):
        # Returns whether a user is a member of a permissions group.
        # If there is only one argument, the current user is assumed.
        # The optional second argument specifies a particular user.
        def expand(group, expanded=set()):
            expanded.add(group)
            with self.env.db_query as db:
                for username in db('SELECT DISTINCT username FROM permission '
                                   'WHERE action = %s', [group]):
                    if db('SELECT COUNT(*) FROM permission '
                          'WHERE action = %s', [username[0]])[0][0]:
                        if username[0] not in expanded:
                            for user in expand(username[0], expanded):
                                yield user
                    else:
                        yield username[0]

        if len(args) < 1 or len(args) > 2:
            raise ConfigurationError('has_role() called with %s arguments' %
                len(args))
        role = args[0]
        if len(args) == 2:
            user = args[1]
        else:
            user = req.authname.encode('utf-8')
        return user in expand(role)

    def is_parent(self, req, *args):
        # Returns True if another ticket has a field named 'parent' that
        # contains '#<n>', where <n> is the number of the current ticket (or
        # the named ticket if an argument is provided).
        # Returns False otherwise.
        if len(args) > 1:
            raise ConfigurationError('is_parent() called with %s arguments' %
                len(args))

        if req.path_info.startswith('/newticket'):
            return False

        if len(args) == 1:
            ticket = args[0]
        else:
            ticket = '#' + req.args['id']
        with self.env.db_query as db:
            return db('SELECT COUNT(*) FROM ticket_custom WHERE '
                'name="parent" AND value = %s', [ticket])[0][0] > 0

    def status_of(self, req, other):
        ''' Returns the status of another ticket. 'other' is expected to
            be a string containing the number of the other ticket, optionally
            prefixed with '#'.
            Returns None if the other ticket can't be found.
        '''
        other_match = re.match('#?(\d+)', other)
        other_ticket = {'status' : None}
        if other_match:
            try:
                other_ticket = Ticket(self.env, int(other_match.group(1)))
            except:
                pass
        return other_ticket['status']

###############################################################################

class Lexer():
    def __init__(self, symbol_table, config_functions, req):
        # Initialise state required for lexer.
        self.symbol_table = symbol_table
        self.config_functions = config_functions
        self.req = req
        self.look = ['', '']

    # 'tokeniser' looks for tokens at the start of 'x' and returns with the
    # token text placed into 'token', and the token type into 'token_type'.
    # There are four types of token, each indicated with a single character:
    #
    #    - N - means that the text in 'token' identifies a Number;
    #    - F - means that the text in 'token' identifies a Field;
    #    - O - means that the text in 'token' is an Operator;
    #    - S - means that the text in 'token' is a String.

    def tokeniser(self, x):
        # Ignoring whitespace, split x on numbers,
        # on words,
        # on tokens ',', '||', '(', ')', '&&', '!', '==', '!=', '~=' or 'in',
        # or on strings delimited by single quotes.

        m = re.search('^([0-9]+(?:\.[0-9]+)?) *(.*)', x)
        if m:
            return 'N', m.group(1), m.group(2)

        m = re.search('^([A-Za-z_]\w*) *(.*)', x)
        if m:
            return 'F', m.group(1), m.group(2)

        m = re.search('^(,|\|\||\(|\)|&&|==|!=|~=|in|!|'
                      '\+|-|\*|\/|<|>|<=|>=|\?|:) *(.*)', x)
        if m:
            return 'O', m.group(1), m.group(2)

        m = re.search("^'([^']*)' *(.*)", x)
        if m:
            return 'S', m.group(1), m.group(2)

        if not x:
            return None, '', 'EOF'

        return None, x, ''

    def match(self, m):
        if self.look[1] == m:
            self.look[0], self.look[1], self.rest = self.tokeniser(self.rest)
        else:
            raise ConfigurationError('Syntax error: %s; expected %s' %
                                     (self.look[1], m))

    def term(self):
        if self.look[0] == 'N':
            v = float(self.look[1])
            self.match(self.look[1])
            text = '%s' % v
        elif self.look[0] == 'S':
            v = self.look[1]
            self.match(v)
            text = "'%s'" % v
        elif self.look[1] == '(':
            self.match('(')
            v, text = self.expression()
            self.match(')')
            text = '(%s)' % text
        elif self.look[0] == 'F':
            text = self.look[1]
            self.match(text)
            if self.look[1] == '(':
                # Function call.
                self.match('(')
                args, text2 = self.param_list()
                self.match(')')
                v = None
                for provider in self.config_functions:
                    funcs = provider.__class__.__dict__
                    if text in funcs:
                        v = funcs[text].__get__(provider)(self.req, *args)
                        break
                else:
                    raise ConfigurationError(
                        "Function '%s' has no implementation" % text,
                         title='Missing plugin or error in trac.ini '
                               '[kis2_warden]',
                         show_traceback=True)
                text = '%s(%s)' % (text, text2)
            else:
                v = self.symbol_table[text]
                if v == None and not text.startswith('_'):
                    raise ConfigurationError(
                        "No field named '%s' is defined" % text,
                        title='Error in trac.ini [kis2_warden]')
        else:
            raise ConfigurationError(
                'Unrecognised token: %s' % self.look[1],
                title='Syntax error in trac.ini [kis2_warden]')
        return v, text

    def membership(self):
        v, text = self.term()
        if self.look[1] == 'in':
            self.match('in')
            i, text2 = self.cmp_list()
            v = v in i
            text = '%s in %s' % (text, text2)
        return v, text

    def param_list(self):
        if self.look[1] == ')':
            v_list = []
            text = ''
        else:
            t, text = self.expression()
            v_list = [t]
            if self.look[1] == ',':
                self.match(',')
                p_list, text2 = self.param_list()
                v_list = v_list + p_list
                text = '%s, %s' % (text, text2)
        return v_list, text

    def cmp_list(self):
        if self.look[1] == '(':
            self.match('(')
            v_list, text = self.cmp_list()
            self.match(')')
            text = '(%s)' % text
        else:
            v, text = self.expression()
            v_list = [v]
            if self.look[1] == ',':
                self.match(',')
                c_list, text2 = self.cmp_list()
                v_list = v_list + c_list
                text = '%s, %s' % (text, text2)
        return v_list, text

    def negation(self):
        if self.look[1] == '-':
            self.match('-')
            v, text = self.negation()
            v = -v
            text = '-%s' % text
        elif self.look[1] == '!':
            self.match('!')
            v, text = self.negation()
            v = not v
            text = '!%s' % text
        else:
            v, text = self.membership()
        return v, text

    def product(self):
        v, text = self.negation()
        if self.look[1] in ('*', '/'):
            op = self.look[1]
            self.match(op)
            e, text2 = self.product()
            v = eval('v %s e' % op)
            text = '%s %s %s' % (text, op, text2)
        return v, text

    def sum(self):
        v, text = self.product()
        if self.look[1] in ('+', '-'):
            op = self.look[1]
            self.match(op)
            e, text2 = self.sum()
            v = eval('v %s e' % op)
            text = '%s %s %s' % (text, op, text2)
        return v, text

    def comparison(self):
        v, text = self.sum()
        if self.look[1] in ('<', '>', '<=', '>='):
            op = self.look[1]
            self.match(op)
            e, text2 = self.comparison()
            v = eval('v %s e' % op)
            text = '%s %s %s' % (text, op, text2)
        return v, text

    def equality(self):
        v, text = self.comparison()
        if self.look[1] in ('==', '!=', '~='):
            op = self.look[1]
            self.match(op)
            e, text2 = self.equality()
            if op == '==' or op == '!=':
                v = eval('v %s e' % op)
            elif op == '~=':
                v = bool(re.search(e, v))
            text = '%s %s %s' % (text, op, text2)
        return v, text

    def and_expression(self):
        v, text = self.equality()
        if self.look[1] == '&&':
            self.match('&&')
            e, text2 = self.and_expression()
            v = v and e
            text = '%s && %s' % (text, text2)
        return v, text

    def or_expression(self):
        v, text = self.and_expression()
        if self.look[1] == '||':
            self.match('||')
            e, text2 = self.or_expression()
            v = v or e
            text = '%s || %s' % (text, text2)
        return v, text

    def expression(self):
        v, text = self.or_expression()
        if self.look[1] == '?':
            self.match('?')
            v_t, text_t= self.expression()
            if self.look[1] != ':':
                raise ConfigurationError(
                    'Unexpected terminal: %s' % self.look[1],
                     title='Syntax error in trac.ini [kis2_warden]',
                     show_traceback=True)
            else:
                self.match(':')
                v_f, text_f= self.expression()
            if v:
                v = v_t
            else:
                v = v_f
            text = '%s ? %s : %s' % (text, text_t, text_f)
        return v, text

    def evaluate(self, predicate):
        self.look[0], self.look[1], self.rest = self.tokeniser(predicate)
        return self.expression()

class KisWarden(Component):
    '''
    Prevents a commit from being accepted if certain conditions are not
    met, as described in the configuration file.

    The configuration file structure is
{{{
[kis2_warden]
<rule name> = <boolean valued expression>
}}}
    Expressions describe the state of the ticket after a change has been
    submitted. If the expression for any rule evaluates to 'true', then the
    change is blocked.

    The grammar of the expressions is the same as defined for the
    '!KisAssistant' component, except that the regular expression syntax is
    Python rather than Javascript.

    For example, take the rules:
{{{
approval required to close = status == 'closed' && approval != 'Approved'

only designated approver can approve = !has_role('approver') && approval != _approval && approval == 'Approved'
}}}
    The first rule means that the ticket cannot be closed if the 'approval'
    field has not been set to the value 'Approved'. The second rule means that
    only a user who is a member of the group 'approver' can change the
    'approval' field to that value.
    '''

    implements(ITicketManipulator)

    config_functions = ExtensionPoint(IConfigFunction)

    # ITicketManipulator methods
    def prepare_ticket(self, req, ticket, fields, actions):
        """ Not currently called, but should be provided for future
            compatibility.
        """
        pass

    def validate_ticket(self, req, ticket):
        """ Make sure required conditions for the next state the ticket will
            be in have been met.
        """

        class Symbol_Table(object):
            def __init__(self, env, req, ticket):
                self.env = env
                self.req = req
                self.ticket = ticket

            def _get_action_controllers(self, action):
                ''' Function modified from 'ticketvalidatorplugin',
                    copyright (C) 2008 Max Stewart <max.e.stewart@gmail.com>
                    and licensed under 3-clause BSD licence.
                '''
                for controller in TicketSystem(self.env).action_controllers:
                    actions = [action for weight, action in
                               controller.get_ticket_actions(self.req,
                                                             self.ticket)]
                    if action in actions:
                        yield controller

            def _get_next_state(self):
                ''' Get the state this ticket is going to be in.
                    Function modified from 'ticketvalidatorplugin',
                    copyright (C) 2008 Max Stewart <max.e.stewart@gmail.com>
                    and licensed under 3-clause BSD licence.
                '''
                if 'action' not in self.req.args:
                    return ''

                action = self.req.args['action']
                action_changes = {}

                for controller in \
                        self._get_action_controllers(action):
                    action_changes.update(
                        controller.get_ticket_changes(self.req,
                                                      self.ticket,
                                                      action))

                return 'status' in action_changes and \
                    action_changes['status'] or self.ticket['status']

            def __getitem__(self, key):
                ''' Look up the value of a field. The field name 'authname' is
                    a special case, returning the name of the user attempting
                    the transition.
                    If the field name is prefixed by '_', this indicates that
                    the original value of a field that is being changed in the
                    current transition should be provided.
                '''

                def __empty_string_if_field_exists__(key):
                    existing_fields = TicketSystem(self.env).get_ticket_fields()
                    if any(x['name'] == key for x in existing_fields):
                        return ''
                    return None

                value = None
                if key == 'authname':
                    value = self.req.authname
                elif key == 'true':
                    value = True
                elif key == 'false':
                    value = False
                elif key.startswith('_'):
                    key = key[1:]
                    if key in self.ticket._old:
                        # _old only has values for fields that are changing.
                        value = self.ticket._old[key] or ''
                elif key == 'status':
                    # This is handled specially, as there may be action
                    # controllers that change or restrict the next status.
                    value = self._get_next_state()

                # Return empty string for fields that exist but have no
                # valid (default) value.
                if value is None:
                    value = self.ticket.get_value_or_default(key)
                if value is None:
                    value = __empty_string_if_field_exists__(key)
                return value

        symbol_table = Symbol_Table(self.env, req, ticket)
        lexer = Lexer(symbol_table, self.config_functions, req)
        errors = []

        warden_rules = self.config.options('kis2_warden')
        for test_value in self.config.options('kis2_warden'):
            break
        else:
            # No rules defined under 'kis2_warden'; try 'kis_warden'.
            warden_rules = self.config.options('kis_warden')

        for rule, predicate in warden_rules:
            e, text = lexer.evaluate(predicate)
            if e:
                errors.append((None, "%s (%s)" % (rule, predicate)))
        return errors

###############################################################################

class KisAssistant(Component):
    '''
    Controls which fields, actions and options are available in the user
    interface. Can automatically update the content of fields. Allows
    templates to be defined for initialising text fields.

=== Configuration file ===
    The configuration file structure is:
{{{
[kis2_assistant]
<field_or_action_name>.visible = <boolean valued expression>
<field_name>.available.<option_set_name> = <boolean valued expression>
<field_name>.options.<option_set_name> = <list of string valued expressions>
<field_name>.available.<template_name> = <boolean valued expression>
<field_name>.template.<template_name> = <string valued expression>
<field_name>.update = <expression>
<field_name>.update.when = <boolean valued expression>
}}}

    The restrictions imposed by '!KisAssistant' are in the user interface
    only. None of the constraints are enforced. Define matching rules using
    the '!KisWarden' component if it's necessary to enforce the restrictions.

=== Hiding and showing fields ===
    The rule attribute 'visible' defines when the associated field will be
    visible in the interface.

    For example, take the rule:
{{{
approval.visible = !status in 'new', 'closed'
}}}
    This requires that a custom field named 'approval' is defined. This rule
    states that the field only appears when the ticket status is other than
    'new' or 'closed'. If no visibility rule is defined for a field, the
    field is visible.

    By default, fields are hidden only in the "Change Properties" box: the
    area where the user modifies the fields. To hide them in the main ticket
    description at the top of the page as well, add the suffix `.all` to the
    rule name. To hide the fields in the main ticket description only, add the
    suffix `.ticket` to the rule name. To use different rules for hiding the
    field in the main ticket description and in the "Change Properties" box,
    give the main ticket description rule the suffix `.ticket` and the "Change
    Properties" rule the suffix `.property`.

=== Controlling the options available in dropdowns (Select fields) and radio button sets (Radio fields) ===
    The options shown in Select and Radio fields can be controlled using the
    attributes 'options' and 'available'. The 'options' attribute is used to
    assign a name to a group of options. Then the matching 'available'
    attribute for that name defines when those options are available.

    For example, take the rules:
{{{
approval.options.basic_set = 'Not assessed', 'Denied'
approval.available.basic_set = true
approval.options.full_set = 'Approved'
approval.available.full_set = has_role('approver') || _approval == 'Approved'
}}}
    This requires that the 'approval' field is either a Select or a Radio
    field, with options 'Not assessed', 'Denied' and 'Approved'. The options
    'Not assessed' or 'Denied' are always available, but the option 'Approved'
    is only available if the user is a member of the 'approver' group or if
    the field already had the value 'Approved' when the page was loaded.

    Options will appear by default unless specifically hidden by a rule. It
    isn't therefore strictly necessary to specify 'Not assessed' and 'Denied'
    here, but it can be clearer to do so. An option will be available if it
    appears in at least one set that is available.

    The ticket actions can be controlled as if they were a custom field of
    Radio type. They are accessed with a pre-defined field named 'action'. The
    available values for the ticket actions are the names defined in the
    configuration file for the state transitions corresponding to the action.

    Note that the options are hidden, not removed. The user will still be able
    to select the option in most browsers by using keyboard shortcuts. Use a
    '!KisWarden' rule to restrict the values accepted when a ticket is
    submitted, if that is what is needed.

=== Automatic updates ===

    The 'update' attribute of a field defines a rule for automatically
    updating the field's content. Normally, it is re-evaluated whenever one of
    the fields used to determine the outcome of the rule is changed.

    For example, take the rule:
{{{
priority.update = (effort > 5) ? 'high' : 'low'
}}}
    This requires that a custom field named 'effort' is defined. If the
    'effort' field is changed to a value greater than 5, then the priority
    field is set to 'high'. Otherwise it is set to low.

    Sometimes it's necessary to update a field only under certain conditions.
    In that case, the optional 'update.when' attribute can be used to define
    those conditions.

    For example:
{{{
priority.update.when = milestone == 'Build 42'
}}}
    Now the rule stated previously will be applied when the milestone is
    changed to 'Build 42', not when the 'effort' field is changed. The
    'update.when' rule is re-evaluated whenever one of the fields used to
    determine the outcome of the rule is changed.

=== Using templates ===
    Templating rules use the attributes 'template' and 'available'. The
    'template' attribute assigns a name to a block of template text that could
    be used to pre-populate a field. The 'available' attribute for that name
    defines the condition under which the field will be populated with that
    text.

    For example:
{{{
evaluation.template.change = '=== Description ===\\nDescribe the change fully...'
evaluation.available.change = evaluation_template == 'Change'
evaluation.template.fault = '=== Description ===\\nDescribe the fault fully...'
evaluation.available.fault = evaluation_template == 'Fault'
evaluation.template.none = ''
evaluation.available.none = evaluation_template == 'None'
}}}

    This requires that a custom field named 'evaluation_template' is defined
    (either a Select or a Radio field) with options 'None', 'Change' and
    'Fault'. Another custom Textarea field named 'evaluation' is defined. When
    'evaluation_template' is set to 'Change', the 'evaluation' field will be
    initialised with the value of the 'evaluation.template.change' option
    (shown here in a cut-down form; it would normally contain template entries
    for all the items of information that might be wanted in a Change
    evaluation). Similarly for 'evaluation_template' values of 'Fault' or
    'None'.

    A field will only be initialised from a template if it is currently either
    empty or unchanged from one of the alternative template values. Template
    fields can be preferred over the use of automatically-updated fields
    because of this behaviour.

=== Expression syntax and semantics ===

    In expressions, field names evaluate to the current value of the
    corresponding field, except for the special names `status`, which
    evaluates to the ticket status (or the empty string if the ticket has not
    yet been created), `authname`, which evaluates to the current username,
    `true` which evaluates True and `false`, which evaluates False.  If the
    field name is prefixed with an underscore, it evaluates to the value of
    the field at the time the page was loaded.

    Text-type fields evaluate to their contents, checkboxes evaluate to true
    if checked or false if not, and Select or Radio fields evaluate to the
    selected item if an item is selected or undefined if no item is selected.

    The grammar of the expressions is:
{{{
                expression ::= or_expression
                             | or_expression "?" expression ":" expression
             or_expression ::= and_expression
                             | and_expression "||" or_expression
            and_expression ::= equality
                             | equality "&&" and_expression
                  equality ::= comparison
                             | comparison "==" | "!=" | "~=" equality
                comparison ::= sum
                             | sum "<" | ">" | "<=" | ">=" comparison
                       sum ::= product
                             | product "+" | "-" sum
                   product ::= negation
                             | negation "*" | "/" product
                  negation ::= membership
                             | "-" | "!" negation
                membership ::= term
                             | term "in" cmp_list
                  cmp_list ::= "(" cmp_list ")"
                             | expression
                             | expression "," cmp_list
                param_list ::= *empty*
                             | expression
                             | expression "," param_list
                      term ::= "(" expression ")"
                             | <number>
                             | <field>
                             | <function_name> "(" param_list ")"
                             | "'" <string> "'"
}}}
    `~=` is an operator that returns True only if the value on the left is
    matched by the Javascript regular expression on the right. `in` is an
    operator that returns True only if the value on the left appears in the
    list on the right. The operators `!`, `==`, `!=`, `||` and `&&` are
    negation, equality, inequality, OR and AND respectively.

    Note that the `&&` and `||` operators evaluate in the same way as the
    Javascript operators (or the Python `and` and `or` operators). So 'x && y'
    evaluates to 'x' if 'x' is false; 'y' if 'x' is true. [[span('x || y')]]
    evaluates to 'x' if 'x' is true; 'y' if 'x' is false.
    '''

    implements(IRequestFilter,
               IRequestHandler,
               ITemplateProvider)

    config_functions = ExtensionPoint(IConfigFunction)

    def __init__(self):
        super(KisAssistant, self).__init__()

        # Construct an object representing the configuration, to be passed to
        # the client-side script.
        items = self.config.options('kis2_assistant')
        for test_value in self.config.options('kis2_assistant'):
            break
        else:
            # No rules defined under 'kis2_assistant'; try 'kis_assistant'.
            items = self.config.options('kis_assistant')
        self.kis_config = {}
        for dotted_name, value in items:
            config_traverse = self.kis_config
            for component in dotted_name.split('.'):
                if not component in config_traverse:
                    if component.startswith('#'):
                        continue
                    config_traverse[component] = {}
                config_traverse = config_traverse[component]
            config_traverse['#'] = \
                re.sub("\s*,\s*", ",", value.strip()).split(",")

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
#        return [('kis2', resource_filename(__name__, 'htdocs'))]
        yield 'kis2', resource_filename(__name__, 'htdocs')

    def get_templates_dirs(self):
        return []

    # IRequestFilter
    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        if req.path_info.startswith('/newticket') or \
                req.path_info.startswith('/ticket/'):
            if 'id' in req.args:
                ticket_id = req.args['id'].lstrip('#')
                ticket = Ticket(self.env, ticket_id)
                status = ticket.get_value_or_default('status')
            else:
                ticket_id = None
                status = ''
            page_data = { 'trac_ini' : self.kis_config,
                          'status'   : status,
                          'id'       : ticket_id,
                          'authname' : req.authname }
            add_script_data(req, {'kis2_page_info' : page_data})

            # Add the client-side support functions.
            if 'rv:11' in req.environ['HTTP_USER_AGENT'] \
                    or 'MSIE' in req.environ['HTTP_USER_AGENT']:
                # Provide Promise support for Internet Explorer.
                add_script(req, 'kis2/bluebird.min.js')
                # This one is only really needed for IE8 and older.
                add_script(req, 'kis2/bind.js')
            add_script(req, 'kis2/kis.js')

        return template, data, content_type

    # IRequestHandler
    def match_request(self, req):
        return req.path_info.endswith('/2kis_function')

    def process_request(self, req):
        if req.args['op'] == 'call_function':
            args = req.args.get('args[]')
            if type(args) == type(None):
                args = []
            if type(args) != type([]):
                args = [args]
            config_func = req.args['config_func']
            for provider in self.config_functions:
                funcs = provider.__class__.__dict__
                if config_func in funcs:
                    result = funcs[config_func].__get__(provider)(req, *args)
                    req.send(json.dumps(result).encode('utf-8'),
                             'application/json')
                    break
            else:
                raise ConfigurationError(
                    "Function '%s' has no implementation" % config_func,
                     title='Missing plugin or error in trac.ini '
                           '[kis2_assistant]',
                     show_traceback=True)
