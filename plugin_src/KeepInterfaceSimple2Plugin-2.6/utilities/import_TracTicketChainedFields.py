#!/usr/bin/env python

# This script allows TracTicketChainedFieldsPlugin configurations, which are
# defined as an object in JSON notation, to be converted to a set of
# equivalent KISplugin configuration directives.

# Copyright Jonathan Ashley <trac@ifton.co.uk> 2016.
# Licensed under version 3 of the GPL. See file COPYING for details.

import argparse
import json

guid = 0
def output_kis(field, values, field_values, parents=[]):
    # Walk the JSON tree. At each level, we have keys that are field names.
    # The value of the key is a dictionary. Each key in that dictionary is an
    # available option for the field. The value of that key is another
    # dictionary in which the keys are field names.

    # At any level, the set of options is only available if all the parent
    # fields have the parent values.

    # field is just the name of the field,
    # values is the dictionary of possible values,
    # field_values accumulates the set of possible values for a field, for
    #   creating the 'ticket_custom' section of trac.ini later,
    # parents is a list of pairs (parent name, parent value).

    global guid
    # Looking for output of:
    #   <field>.options.<guid> = values
    #   <field>.available.<guid> = rule that all parents have right value
    value_list = ', '.join(("'%s'" % x for x in sorted(values.keys())))
    parent_rules = ' && '.join(("%s == '%s'" % (p[0], p[1]) for p in parents))
    if parent_rules == '':
        parent_rules = 'true'
    yield ('%s.options.%s' % (field, guid), '%s' % value_list)
    yield ('%s.available.%s' % (field, guid), '%s' % parent_rules)
    guid += 1

    field_values.setdefault(field, set())
    for value in values:
        field_values[field].add(value)
        for chained_field in values[value]:
            for rule in output_kis(chained_field,
                                   values[value][chained_field],
                                   field_values,
                                   parents + [(field, value)]):
                yield rule

def update_trac_ini(trac_file, chained_fields):
    field_values = {}
    rules = {}
    rule_done = set()
    select_done = set()
    option_done = set()
    for field in chained_fields:
        for rule_name, rule_content \
                in output_kis(field, chained_fields[field], field_values):
            rules[rule_name] = rule_content
    # Keep track of the ini file parsing state. Go through the file
    # line-by-line, replacing the existing rules where we need to and
    # adding the remaining ones at the end of the appropriate section.
    state = None
    for line in open(trac_file, 'r'):
        line = line.rstrip()
        if line == '[kis_assistant]':
            state = 'kis'
        elif line == '[ticket-custom]':
            state = 'ticket'
        elif line.startswith('['):
            if state == 'kis':
                # Dump any remaining kis rules now.
                for rule_name in rules:
                    if not rule_name in rule_done:
                        print '%s = %s' % (rule_name, rules[rule_name])
                state = None
            elif state == 'ticket':
                # Dump any remaining ticket-custom directives now.
                for field in field_values:
                    if not field in select_done:
                        print '%s = select' % field
                    if not field in option_done:
                        print '%s.options = %s' % (
                            field, '|'.join(sorted(field_values[field])))
                state = None
        if state == 'kis':
            rule_name = line.split('=')[0].strip()
            if rule_name in rules:
                line = '%s = %s' % (rule_name, rules[rule_name])
                rule_done.add(rule_name)
        elif state == 'ticket':
            left_side = line.split('=')[0].strip()
            field_name = left_side.split('.')[0].strip()
            if field_name in field_values:
                if field_name == left_side:
                    line = '%s = select' % field_name
                    select_done.add(field_name)
                else:
                    field_name, options = left_side.split('.')
                    if options == 'options':
                        line = '%s = %s' % (
                            left_side,
                            '|'.join(sorted(field_values[field_name])))
                        option_done.add(field_name)
        print line

def standalone_output(chained_fields):
    field_values = {}
    print '[kis_assistant]'
    for field in chained_fields:
        for rule_name, rule_content \
                in output_kis(field, chained_fields[field], field_values):
            print '%s = %s' % (rule_name, rule_content)
    print
    print '[ticket_custom]'
    for field in field_values:
        print '%s = select' % field
        print '%s.options = %s' % (field,
                                   '|'.join(sorted(field_values[field])))


parser = argparse.ArgumentParser(
    description='Convert TracTicketChainedFieldsPlugin JSON into '
                'a configuration for KeepInterfaceSimplePlugin')
parser.add_argument('JSON_file_name',
                    help='Path to the TracTicketChainedFieldsPlugin JSON file')
parser.add_argument('-t', '--trac_ini',
                    help='Path to trac.ini. If this option is given, '
                         'output an updated trac.ini.')
args = parser.parse_args()
json_file = vars(args)['JSON_file_name']
trac_file = vars(args)['trac_ini']

chained_fields = json.load(open(json_file, 'r'))

if trac_file:
    update_trac_ini(trac_file, chained_fields)
else:
    standalone_output(chained_fields)
